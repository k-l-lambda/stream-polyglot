#!/usr/bin/env python3
"""
Compare pyannote.audio vs Resemblyzer on VAD fragments
Test first 50 fragments from 066. 移民第五季 第十三集
"""

import sys
import os
from pathlib import Path
import numpy as np
import time
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics import adjusted_rand_score

# Set HF token (set your own token via environment variable or replace this)
os.environ['HF_TOKEN'] = os.getenv('HF_TOKEN', 'your_huggingface_token_here')

FRAGMENTS_DIR = str(Path.home() / "work/stream-polyglot/assets/.stream-polyglot-cache/066. 移民第五季 第十三集/fragments")
MAX_FRAGMENTS = 50


def test_resemblyzer(fragment_files):
    """Test Resemblyzer clustering"""
    print("="*70)
    print("TEST 1: Resemblyzer")
    print("="*70 + "\n")

    from resemblyzer import VoiceEncoder, preprocess_wav

    # Initialize encoder
    print("Loading Resemblyzer encoder...")
    start_time = time.time()
    encoder = VoiceEncoder()
    load_time = time.time() - start_time
    print(f"✓ Loaded in {load_time:.2f}s\n")

    # Extract embeddings
    print(f"Extracting embeddings from {len(fragment_files)} fragments...")
    embeddings = []
    valid_files = []
    skipped = 0

    start_time = time.time()
    for fpath in fragment_files:
        try:
            wav = preprocess_wav(fpath)
            if len(wav) < 6400:  # 0.4s at 16kHz
                skipped += 1
                continue

            embedding = encoder.embed_utterance(wav)
            embeddings.append(embedding)
            valid_files.append(fpath)

        except Exception as e:
            skipped += 1

    extract_time = time.time() - start_time
    embeddings = np.array(embeddings)

    print(f"✓ Extracted {len(embeddings)} embeddings in {extract_time:.2f}s")
    print(f"  Skipped: {skipped} (too short)")
    print(f"  Embedding dim: {embeddings.shape[1]}\n")

    # Compute similarities
    similarities = cosine_similarity(embeddings)
    triu_indices = np.triu_indices(len(similarities), k=1)
    similarity_values = similarities[triu_indices]

    print("Similarity Statistics:")
    print(f"  Mean:   {similarity_values.mean():.4f}")
    print(f"  Min:    {similarity_values.min():.4f}")
    print(f"  Max:    {similarity_values.max():.4f}")
    print(f"  Std:    {similarity_values.std():.4f}\n")

    # Cluster with threshold 0.5
    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=0.5,
        metric='cosine',
        linkage='average'
    )
    labels = clustering.fit_predict(embeddings)
    n_clusters = len(set(labels))
    cluster_sizes = [np.sum(labels == i) for i in range(n_clusters)]

    print(f"Clustering Results (threshold 0.5):")
    print(f"  Speakers detected: {n_clusters}")
    print(f"  Distribution: {sorted(cluster_sizes, reverse=True)[:5]}")
    if len(cluster_sizes) > 5:
        print(f"  ... and {len(cluster_sizes) - 5} more clusters\n")
    else:
        print()

    return {
        'method': 'Resemblyzer',
        'embeddings': embeddings,
        'labels': labels,
        'n_clusters': n_clusters,
        'similarities': similarities,
        'extract_time': extract_time,
        'valid_files': valid_files,
        'embedding_dim': embeddings.shape[1]
    }


def test_pyannote(fragment_files):
    """Test pyannote.audio clustering"""
    print("="*70)
    print("TEST 2: pyannote.audio")
    print("="*70 + "\n")

    try:
        from pyannote.audio import Inference
        from pyannote.audio import Model
    except ImportError:
        print("❌ pyannote.audio not available")
        return None

    # Load model
    print("Loading pyannote.audio embedding model...")
    try:
        # Set environment variable to allow unsafe pickle loading for PyTorch 2.6+
        # This is needed for pytorch_lightning checkpoints
        import os
        os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'

        start_time = time.time()
        # Use weights_only=False for compatibility with pytorch_lightning models
        import torch
        original_load = torch.load
        def patched_load(*args, **kwargs):
            kwargs['weights_only'] = False
            return original_load(*args, **kwargs)
        torch.load = patched_load

        model = Model.from_pretrained("pyannote/embedding", use_auth_token=True)
        inference = Inference(model, window="whole")

        # Restore original torch.load
        torch.load = original_load

        load_time = time.time() - start_time
        print(f"✓ Loaded in {load_time:.2f}s\n")

    except Exception as e:
        print(f"❌ Error loading model: {e}\n")
        return None

    # Extract embeddings
    print(f"Extracting embeddings from {len(fragment_files)} fragments...")
    import soundfile as sf
    embeddings = []
    valid_files = []
    skipped = 0

    start_time = time.time()
    for fpath in fragment_files:
        try:
            audio, sr = sf.read(fpath)

            # Skip very short
            if len(audio) / sr < 0.4:
                skipped += 1
                continue

            # Convert to proper format for pyannote
            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)

            # Resample if needed
            if sr != 16000:
                import librosa
                audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
                sr = 16000

            # Extract embedding
            # Convert numpy array to torch tensor
            import torch
            audio_tensor = torch.from_numpy(audio).float()
            embedding = inference({"waveform": audio_tensor.unsqueeze(0), "sample_rate": sr})
            embeddings.append(embedding)
            valid_files.append(fpath)

        except Exception as e:
            skipped += 1
            print(f"  ⚠ {fpath.name}: {e}")

    extract_time = time.time() - start_time
    embeddings = np.array(embeddings)

    print(f"✓ Extracted {len(embeddings)} embeddings in {extract_time:.2f}s")
    print(f"  Skipped: {skipped} (too short)")
    print(f"  Embedding dim: {embeddings.shape[1]}\n")

    # Compute similarities
    similarities = cosine_similarity(embeddings)
    triu_indices = np.triu_indices(len(similarities), k=1)
    similarity_values = similarities[triu_indices]

    print("Similarity Statistics:")
    print(f"  Mean:   {similarity_values.mean():.4f}")
    print(f"  Min:    {similarity_values.min():.4f}")
    print(f"  Max:    {similarity_values.max():.4f}")
    print(f"  Std:    {similarity_values.std():.4f}\n")

    # Cluster with threshold 0.5
    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=0.5,
        metric='cosine',
        linkage='average'
    )
    labels = clustering.fit_predict(embeddings)
    n_clusters = len(set(labels))
    cluster_sizes = [np.sum(labels == i) for i in range(n_clusters)]

    print(f"Clustering Results (threshold 0.5):")
    print(f"  Speakers detected: {n_clusters}")
    print(f"  Distribution: {sorted(cluster_sizes, reverse=True)[:5]}")
    if len(cluster_sizes) > 5:
        print(f"  ... and {len(cluster_sizes) - 5} more clusters\n")
    else:
        print()

    return {
        'method': 'pyannote.audio',
        'embeddings': embeddings,
        'labels': labels,
        'n_clusters': n_clusters,
        'similarities': similarities,
        'extract_time': extract_time,
        'valid_files': valid_files,
        'embedding_dim': embeddings.shape[1]
    }


def compare_results(res_result, pya_result):
    """Compare clustering results"""
    print("="*70)
    print("COMPARISON")
    print("="*70 + "\n")

    if not res_result or not pya_result:
        print("❌ Cannot compare - one or both methods failed\n")
        return

    print(f"{'Metric':<30} {'Resemblyzer':<20} {'pyannote.audio':<20}")
    print("-" * 70)
    print(f"{'Speakers detected':<30} {res_result['n_clusters']:<20} {pya_result['n_clusters']:<20}")
    print(f"{'Embedding dimension':<30} {res_result['embedding_dim']:<20} {pya_result['embedding_dim']:<20}")

    res_time_str = f"{res_result['extract_time']:.2f}s"
    pya_time_str = f"{pya_result['extract_time']:.2f}s"
    print(f"{'Extraction time':<30} {res_time_str:<20} {pya_time_str:<20}")

    # Speed comparison
    speedup = res_result['extract_time'] / pya_result['extract_time']
    faster = "Resemblyzer" if speedup < 1 else "pyannote"
    percent_str = f"{abs(1-speedup)*100:.1f}% faster"
    print(f"{'Faster method':<30} {faster:<20} {percent_str:<20}")
    print()

    # Agreement analysis
    if res_result['n_clusters'] == pya_result['n_clusters']:
        print(f"✓ Both methods detected {res_result['n_clusters']} speaker(s)")
    else:
        print(f"⚠ Disagreement: Resemblyzer={res_result['n_clusters']}, pyannote={pya_result['n_clusters']}")

    # Compute agreement on assignments
    ari = adjusted_rand_score(res_result['labels'], pya_result['labels'])
    print(f"  Adjusted Rand Index: {ari:.4f}")
    if ari > 0.9:
        print(f"  → Very high agreement (almost identical clustering)")
    elif ari > 0.7:
        print(f"  → High agreement (similar clustering)")
    elif ari > 0.5:
        print(f"  → Moderate agreement")
    else:
        print(f"  → Low agreement (different clustering strategies)")
    print()


def main():
    print("="*70)
    print("Speaker Clustering Comparison on VAD Fragments")
    print("="*70)
    print(f"\nAudio: 066. 移民第五季 第十三集")
    print(f"Testing: First {MAX_FRAGMENTS} fragments\n")

    # Get fragment files
    fragments_dir = Path(FRAGMENTS_DIR)
    fragment_files = sorted(fragments_dir.glob("fragment_*.wav"))[:MAX_FRAGMENTS]

    print(f"Found {len(fragment_files)} fragment files\n")

    # Test Resemblyzer
    res_result = test_resemblyzer(fragment_files)

    # Test pyannote
    pya_result = test_pyannote(fragment_files)

    # Compare
    compare_results(res_result, pya_result)

    print("="*70)
    print("Test completed!")
    print("="*70)


if __name__ == '__main__':
    main()
