#!/usr/bin/env python3
"""
Compare pyannote.audio vs Resemblyzer for speaker clustering

Test audio: 066. 移民第五季 第十三集.mp3
Expected: Multi-speaker audio (podcast/interview style)
"""

import sys
import os
from pathlib import Path
import numpy as np
import soundfile as sf
import librosa
import time
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity

# Audio file path
AUDIO_PATH = "/home/camus/work/stream-polyglot/assets/066. 移民第五季 第十三集.mp3"
SEGMENT_DURATION = 10.0  # 10 seconds per segment for testing
MAX_SEGMENTS = 30  # Test with first 30 segments (5 minutes)


def prepare_audio_segments(audio_path, segment_duration=10.0, max_segments=30):
    """Split audio into fixed-length segments for clustering"""
    print(f"Loading audio: {Path(audio_path).name}")

    # Load audio
    audio, sr = librosa.load(audio_path, sr=16000)
    total_duration = len(audio) / sr

    print(f"  Duration: {total_duration:.1f}s")
    print(f"  Sample rate: {sr} Hz")
    print(f"  Creating {segment_duration}s segments...\n")

    # Create segments
    segment_samples = int(segment_duration * sr)
    segments = []

    for i in range(max_segments):
        start_sample = i * segment_samples
        end_sample = start_sample + segment_samples

        if end_sample > len(audio):
            break

        segment = audio[start_sample:end_sample]
        segments.append({
            'audio': segment,
            'sr': sr,
            'start': i * segment_duration,
            'end': (i + 1) * segment_duration,
            'index': i
        })

    print(f"✓ Created {len(segments)} segments ({len(segments) * segment_duration:.1f}s total)\n")
    return segments


def test_resemblyzer(segments):
    """Test Resemblyzer speaker clustering"""
    print("="*70)
    print("TEST 1: Resemblyzer")
    print("="*70 + "\n")

    try:
        from resemblyzer import VoiceEncoder, preprocess_wav
    except ImportError:
        print("❌ Resemblyzer not available")
        return None

    # Initialize encoder
    print("Loading Resemblyzer encoder...")
    start_time = time.time()
    encoder = VoiceEncoder()
    load_time = time.time() - start_time
    print(f"✓ Encoder loaded in {load_time:.2f}s\n")

    # Extract embeddings
    print(f"Extracting embeddings from {len(segments)} segments...")
    embeddings = []
    valid_indices = []

    start_time = time.time()
    for seg in segments:
        try:
            # Resemblyzer expects 16kHz audio
            embedding = encoder.embed_utterance(seg['audio'])
            embeddings.append(embedding)
            valid_indices.append(seg['index'])
        except Exception as e:
            print(f"  ⚠ Segment {seg['index']}: {e}")

    extract_time = time.time() - start_time
    embeddings = np.array(embeddings)

    print(f"✓ Extracted {len(embeddings)} embeddings in {extract_time:.2f}s")
    print(f"  Embedding shape: {embeddings.shape}\n")

    # Compute similarities
    print("Computing pairwise similarities...")
    similarities = cosine_similarity(embeddings)

    # Get statistics
    triu_indices = np.triu_indices(len(similarities), k=1)
    similarity_values = similarities[triu_indices]

    print(f"  Min:    {similarity_values.min():.4f}")
    print(f"  Max:    {similarity_values.max():.4f}")
    print(f"  Mean:   {similarity_values.mean():.4f}")
    print(f"  Median: {np.median(similarity_values):.4f}\n")

    # Cluster with multiple thresholds
    print("Clustering with different thresholds:\n")

    best_result = None
    for threshold in [0.4, 0.5, 0.6, 0.7]:
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=1 - threshold,
            metric='cosine',
            linkage='average'
        )
        labels = clustering.fit_predict(embeddings)

        n_clusters = len(set(labels))
        cluster_sizes = [np.sum(labels == i) for i in range(n_clusters)]

        print(f"Threshold {threshold:.1f}:")
        print(f"  Speakers: {n_clusters}")
        print(f"  Distribution: {cluster_sizes}")

        # Use threshold 0.5 as default result
        if threshold == 0.5:
            best_result = {
                'method': 'Resemblyzer',
                'embeddings': embeddings,
                'labels': labels,
                'n_clusters': n_clusters,
                'threshold': threshold,
                'similarities': similarities,
                'extract_time': extract_time,
                'valid_indices': valid_indices
            }

    return best_result


def test_pyannote(segments):
    """Test pyannote.audio speaker clustering"""
    print("\n" + "="*70)
    print("TEST 2: pyannote.audio")
    print("="*70 + "\n")

    try:
        from pyannote.audio import Model
        from pyannote.audio.pipelines import SpeakerDiarization
    except ImportError:
        print("❌ pyannote.audio not available")
        print("Install with: pip install pyannote.audio")
        return None

    # Try to load embedding model
    print("Loading pyannote.audio embedding model...")

    try:
        # Try to use embedding model directly
        from pyannote.audio import Inference

        start_time = time.time()
        model = Model.from_pretrained("pyannote/embedding")
        inference = Inference(model, window="whole")
        load_time = time.time() - start_time

        print(f"✓ Model loaded in {load_time:.2f}s\n")

        # Extract embeddings
        print(f"Extracting embeddings from {len(segments)} segments...")
        embeddings = []
        valid_indices = []

        start_time = time.time()
        for seg in segments:
            try:
                # pyannote expects numpy array
                embedding = inference({"waveform": seg['audio'][np.newaxis, :], "sample_rate": seg['sr']})
                embeddings.append(embedding)
                valid_indices.append(seg['index'])
            except Exception as e:
                print(f"  ⚠ Segment {seg['index']}: {e}")

        extract_time = time.time() - start_time
        embeddings = np.array(embeddings)

        print(f"✓ Extracted {len(embeddings)} embeddings in {extract_time:.2f}s")
        print(f"  Embedding shape: {embeddings.shape}\n")

        # Compute similarities
        print("Computing pairwise similarities...")
        similarities = cosine_similarity(embeddings)

        # Get statistics
        triu_indices = np.triu_indices(len(similarities), k=1)
        similarity_values = similarities[triu_indices]

        print(f"  Min:    {similarity_values.min():.4f}")
        print(f"  Max:    {similarity_values.max():.4f}")
        print(f"  Mean:   {similarity_values.mean():.4f}")
        print(f"  Median: {np.median(similarity_values):.4f}\n")

        # Cluster with multiple thresholds
        print("Clustering with different thresholds:\n")

        best_result = None
        for threshold in [0.4, 0.5, 0.6, 0.7]:
            clustering = AgglomerativeClustering(
                n_clusters=None,
                distance_threshold=1 - threshold,
                metric='cosine',
                linkage='average'
            )
            labels = clustering.fit_predict(embeddings)

            n_clusters = len(set(labels))
            cluster_sizes = [np.sum(labels == i) for i in range(n_clusters)]

            print(f"Threshold {threshold:.1f}:")
            print(f"  Speakers: {n_clusters}")
            print(f"  Distribution: {cluster_sizes}")

            # Use threshold 0.5 as default result
            if threshold == 0.5:
                best_result = {
                    'method': 'pyannote.audio',
                    'embeddings': embeddings,
                    'labels': labels,
                    'n_clusters': n_clusters,
                    'threshold': threshold,
                    'similarities': similarities,
                    'extract_time': extract_time,
                    'valid_indices': valid_indices
                }

        return best_result

    except Exception as e:
        print(f"❌ Error loading pyannote model: {e}")
        print("\nNote: pyannote.audio requires HuggingFace authentication:")
        print("  1. Visit https://huggingface.co/pyannote/embedding")
        print("  2. Accept the user conditions")
        print("  3. Run: huggingface-cli login")
        return None


def compare_results(resemblyzer_result, pyannote_result):
    """Compare clustering results from both methods"""
    print("\n" + "="*70)
    print("COMPARISON")
    print("="*70 + "\n")

    if resemblyzer_result is None and pyannote_result is None:
        print("❌ No results to compare")
        return

    # Create comparison table
    print(f"{'Metric':<30} {'Resemblyzer':<20} {'pyannote.audio':<20}")
    print("-" * 70)

    if resemblyzer_result:
        res_clusters = resemblyzer_result['n_clusters']
        res_time = resemblyzer_result['extract_time']
        res_dim = resemblyzer_result['embeddings'].shape[1]
    else:
        res_clusters = "N/A"
        res_time = "N/A"
        res_dim = "N/A"

    if pyannote_result:
        pya_clusters = pyannote_result['n_clusters']
        pya_time = pyannote_result['extract_time']
        pya_dim = pyannote_result['embeddings'].shape[1]
    else:
        pya_clusters = "N/A"
        pya_time = "N/A"
        pya_dim = "N/A"

    print(f"{'Number of speakers':<30} {str(res_clusters):<20} {str(pya_clusters):<20}")
    print(f"{'Embedding dimension':<30} {str(res_dim):<20} {str(pya_dim):<20}")

    if isinstance(res_time, float) and isinstance(pya_time, float):
        print(f"{'Extraction time':<30} {f'{res_time:.2f}s':<20} {f'{pya_time:.2f}s':<20}")
        speedup = res_time / pya_time if pya_time > 0 else 0
        print(f"{'Speed comparison':<30} {'baseline':<20} {f'{speedup:.2f}x':<20}")
    else:
        print(f"{'Extraction time':<30} {str(res_time):<20} {str(pya_time):<20}")

    print()

    # Agreement analysis
    if resemblyzer_result and pyannote_result:
        print("Cluster Agreement Analysis:")

        res_labels = resemblyzer_result['labels']
        pya_labels = pyannote_result['labels']

        # Check if they agree on number of speakers
        if res_clusters == pya_clusters:
            print(f"  ✓ Both methods detected {res_clusters} speaker(s)")
        else:
            print(f"  ⚠ Disagreement: Resemblyzer={res_clusters}, pyannote={pya_clusters}")

        # Compute agreement on segment assignments
        # This is approximate since cluster IDs may be different
        from sklearn.metrics import adjusted_rand_score
        ari = adjusted_rand_score(res_labels, pya_labels)
        print(f"  Adjusted Rand Index: {ari:.4f} (1.0 = perfect agreement)")


def main():
    print("="*70)
    print("Speaker Clustering Comparison: pyannote.audio vs Resemblyzer")
    print("="*70)
    print(f"\nAudio: {Path(AUDIO_PATH).name}")
    print(f"Segment duration: {SEGMENT_DURATION}s")
    print(f"Max segments: {MAX_SEGMENTS}\n")

    # Prepare audio segments
    segments = prepare_audio_segments(AUDIO_PATH, SEGMENT_DURATION, MAX_SEGMENTS)

    # Test Resemblyzer
    resemblyzer_result = test_resemblyzer(segments)

    # Test pyannote
    pyannote_result = test_pyannote(segments)

    # Compare results
    compare_results(resemblyzer_result, pyannote_result)

    print("\n" + "="*70)
    print("Test completed!")
    print("="*70)


if __name__ == '__main__':
    main()
