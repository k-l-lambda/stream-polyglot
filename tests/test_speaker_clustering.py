#!/usr/bin/env python3
"""
Test speaker clustering with Resemblyzer

This script tests speaker identification and clustering on audio fragments
to evaluate if clustering can improve voice cloning reference quality.
"""

import sys
import os
from pathlib import Path
import numpy as np
import soundfile as sf

def test_resemblyzer_clustering():
    """Test Resemblyzer speaker clustering on sample audio files"""

    try:
        from resemblyzer import VoiceEncoder, preprocess_wav
    except ImportError:
        print("❌ Resemblyzer not installed")
        print("Install with: pip install resemblyzer")
        return False

    print("✓ Resemblyzer imported successfully\n")

    # Initialize encoder
    print("Loading voice encoder...")
    encoder = VoiceEncoder()
    print("✓ Voice encoder loaded\n")

    # Find test audio directory
    cache_dir = Path("/home/camus/work/stream-polyglot/assets/.stream-polyglot-cache")

    # List available videos
    video_dirs = list(cache_dir.glob("*/fragments"))
    if not video_dirs:
        print("❌ No audio fragments found in cache")
        return False

    print("Available video fragments:")
    for i, vdir in enumerate(video_dirs[:5]):
        print(f"  {i+1}. {vdir.parent.name}")

    # Use first video with fragments
    fragments_dir = video_dirs[0]
    print(f"\n📁 Using: {fragments_dir.parent.name}")

    # Load all fragment files
    fragment_files = sorted(fragments_dir.glob("fragment_*.wav"))[:10]  # Test with first 10

    if len(fragment_files) < 2:
        print("❌ Need at least 2 fragments for clustering test")
        return False

    print(f"✓ Found {len(fragment_files)} fragments\n")

    # Extract embeddings
    print("Extracting speaker embeddings...")
    embeddings = []
    valid_files = []

    for i, fpath in enumerate(fragment_files):
        try:
            # Load and preprocess audio
            wav = preprocess_wav(fpath)

            # Skip very short audio (< 0.3 seconds)
            if len(wav) < 4800:  # 0.3s at 16kHz
                print(f"  ⊘ Fragment {i}: Too short, skipped")
                continue

            # Extract embedding
            embedding = encoder.embed_utterance(wav)
            embeddings.append(embedding)
            valid_files.append(fpath)

            print(f"  ✓ Fragment {i}: {fpath.name} -> embedding shape {embedding.shape}")

        except Exception as e:
            print(f"  ✗ Fragment {i}: Error - {e}")

    if len(embeddings) < 2:
        print("\n❌ Need at least 2 valid embeddings for clustering")
        return False

    embeddings = np.array(embeddings)
    print(f"\n✓ Extracted {len(embeddings)} embeddings, shape: {embeddings.shape}\n")

    # Compute pairwise cosine similarities
    print("Computing pairwise similarities...")
    from sklearn.metrics.pairwise import cosine_similarity

    similarities = cosine_similarity(embeddings)
    print("Similarity matrix:")
    print(similarities)
    print()

    # Analyze similarity distribution
    # Get upper triangle (exclude diagonal)
    triu_indices = np.triu_indices(len(similarities), k=1)
    similarity_values = similarities[triu_indices]

    print("Similarity statistics:")
    print(f"  Min:    {similarity_values.min():.4f}")
    print(f"  Max:    {similarity_values.max():.4f}")
    print(f"  Mean:   {similarity_values.mean():.4f}")
    print(f"  Median: {np.median(similarity_values):.4f}")
    print()

    # Try clustering with different thresholds
    from sklearn.cluster import AgglomerativeClustering

    print("Testing clustering with different thresholds:\n")

    for threshold in [0.3, 0.4, 0.5, 0.6, 0.7]:
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=1 - threshold,  # Convert similarity to distance
            metric='cosine',
            linkage='average'
        )
        labels = clustering.fit_predict(embeddings)

        n_clusters = len(set(labels))
        print(f"Threshold {threshold:.1f} (similarity >= {threshold:.1f}):")
        print(f"  Clusters: {n_clusters}")

        # Show cluster distribution
        for cluster_id in range(n_clusters):
            cluster_files = [valid_files[i].name for i, label in enumerate(labels) if label == cluster_id]
            print(f"  Cluster {cluster_id}: {len(cluster_files)} fragments")
            for fname in cluster_files[:3]:  # Show first 3
                print(f"    - {fname}")
            if len(cluster_files) > 3:
                print(f"    ... and {len(cluster_files) - 3} more")
        print()

    # Test concatenating audio from same cluster
    print("Testing audio concatenation for reference:")

    # Use threshold 0.5 for final clustering
    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=0.5,
        metric='cosine',
        linkage='average'
    )
    labels = clustering.fit_predict(embeddings)

    # Find largest cluster
    cluster_counts = np.bincount(labels)
    main_cluster = np.argmax(cluster_counts)

    print(f"Main speaker cluster: {main_cluster} ({cluster_counts[main_cluster]} fragments)")

    # Concatenate audio from main cluster
    cluster_audio = []
    cluster_sr = None

    for i, label in enumerate(labels):
        if label == main_cluster:
            audio, sr = sf.read(valid_files[i])
            if cluster_sr is None:
                cluster_sr = sr
            cluster_audio.append(audio)
            print(f"  + {valid_files[i].name} ({len(audio)/sr:.2f}s)")

    concatenated = np.concatenate(cluster_audio)
    total_duration = len(concatenated) / cluster_sr

    print(f"\n✓ Concatenated reference audio:")
    print(f"  Duration: {total_duration:.2f} seconds")
    print(f"  Sample rate: {cluster_sr} Hz")
    print(f"  Shape: {concatenated.shape}")

    # Save concatenated audio for testing
    output_path = fragments_dir.parent / "speaker_reference_concatenated.wav"
    sf.write(output_path, concatenated, cluster_sr)
    print(f"  Saved to: {output_path}")

    return True


def test_pyannote_availability():
    """Check if pyannote.audio is available"""
    print("\n" + "="*60)
    print("Testing pyannote.audio availability:")
    print("="*60 + "\n")

    try:
        import pyannote.audio
        print("✓ pyannote.audio is installed")
        print(f"  Version: {pyannote.audio.__version__}")

        # Check for HuggingFace token
        try:
            from huggingface_hub import HfFolder
            token = HfFolder.get_token()
            if token:
                print("✓ HuggingFace token found")
            else:
                print("⚠ HuggingFace token not found (required for pre-trained models)")
                print("  Set with: huggingface-cli login")
        except ImportError:
            print("⚠ huggingface_hub not installed")

        return True

    except ImportError:
        print("❌ pyannote.audio not installed")
        print("Install with: pip install pyannote.audio")
        return False


if __name__ == '__main__':
    print("="*60)
    print("Speaker Clustering Test")
    print("="*60 + "\n")

    # Test Resemblyzer
    success = test_resemblyzer_clustering()

    if success:
        print("\n✅ Resemblyzer clustering test completed successfully!")
    else:
        print("\n❌ Resemblyzer clustering test failed")
        sys.exit(1)

    # Check pyannote availability
    test_pyannote_availability()

    print("\n" + "="*60)
    print("Recommendations:")
    print("="*60)
    print("""
1. Resemblyzer is lightweight and works well for speaker clustering
2. Threshold 0.5-0.6 seems reasonable for grouping same speaker
3. Concatenating audio from same cluster provides longer reference
4. Consider pyannote.audio for production (higher accuracy)

Next steps:
- Integrate speaker clustering into process_trans_voice()
- Add --speaker-clustering CLI argument
- Test voice clone quality improvement with concatenated references
""")
