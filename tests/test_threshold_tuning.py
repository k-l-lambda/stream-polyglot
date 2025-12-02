#!/usr/bin/env python3
"""
Tune clustering thresholds to find optimal speaker count (~10 speakers)
"""

import sys
import os
from pathlib import Path
import numpy as np
import time
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity

# Set HF token (set your own token via environment variable or replace this)
os.environ['HF_TOKEN'] = os.getenv('HF_TOKEN', 'your_huggingface_token_here')

FRAGMENTS_DIR = str(Path.home() / "work/stream-polyglot/assets/.stream-polyglot-cache/066. 移民第五季 第十三集/fragments")
OUTPUT_BASE_DIR = str(Path.home() / "work/stream-polyglot/assets/.clustering_output")


def test_resemblyzer_thresholds():
    """Test Resemblyzer with different thresholds"""
    print("="*70)
    print("Resemblyzer Threshold Tuning")
    print("="*70 + "\n")

    from resemblyzer import VoiceEncoder, preprocess_wav

    # Get fragment files
    fragments_dir = Path(FRAGMENTS_DIR)
    fragment_files = sorted(fragments_dir.glob("fragment_*.wav"))[:50]

    print(f"Loading {len(fragment_files)} fragments...\n")

    # Initialize encoder
    encoder = VoiceEncoder()

    # Extract embeddings
    embeddings = []
    valid_files = []

    for fpath in fragment_files:
        try:
            wav = preprocess_wav(fpath)
            if len(wav) < 6400:  # Skip < 0.4s
                continue
            embedding = encoder.embed_utterance(wav)
            embeddings.append(embedding)
            valid_files.append(fpath)
        except Exception as e:
            pass

    embeddings = np.array(embeddings)
    print(f"Extracted {len(embeddings)} embeddings\n")

    # Test different thresholds
    print("Testing thresholds:")
    print("-" * 70)
    print(f"{'Threshold':<12} {'Speakers':<12} {'Top 5 Cluster Sizes':<30}")
    print("-" * 70)

    results = []
    for threshold in np.arange(0.35, 0.70, 0.05):
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=1 - threshold,
            metric='cosine',
            linkage='average'
        )
        labels = clustering.fit_predict(embeddings)

        n_clusters = len(set(labels))
        cluster_sizes = [np.sum(labels == i) for i in range(n_clusters)]
        top5 = sorted(cluster_sizes, reverse=True)[:5]

        results.append({
            'method': 'Resemblyzer',
            'threshold': threshold,
            'n_clusters': n_clusters,
            'labels': labels,
            'cluster_sizes': cluster_sizes,
            'valid_files': valid_files
        })

        print(f"{threshold:<12.2f} {n_clusters:<12} {str(top5):<30}")

    print()
    return results


def test_pyannote_thresholds():
    """Test pyannote with different thresholds"""
    print("="*70)
    print("pyannote.audio Threshold Tuning")
    print("="*70 + "\n")

    try:
        from pyannote.audio import Inference
        from pyannote.audio import Model
    except ImportError:
        print("❌ pyannote.audio not available")
        return []

    # Get fragment files
    fragments_dir = Path(FRAGMENTS_DIR)
    fragment_files = sorted(fragments_dir.glob("fragment_*.wav"))[:50]

    print(f"Loading {len(fragment_files)} fragments...\n")

    # Load model with torch.load patching
    import torch
    original_load = torch.load
    def patched_load(*args, **kwargs):
        kwargs['weights_only'] = False
        return original_load(*args, **kwargs)
    torch.load = patched_load

    model = Model.from_pretrained("pyannote/embedding", use_auth_token=True)
    inference = Inference(model, window="whole")
    torch.load = original_load

    # Extract embeddings
    import soundfile as sf
    embeddings = []
    valid_files = []

    for fpath in fragment_files:
        try:
            audio, sr = sf.read(fpath)

            if len(audio) / sr < 0.4:
                continue

            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)

            if sr != 16000:
                import librosa
                audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
                sr = 16000

            audio_tensor = torch.from_numpy(audio).float()
            embedding = inference({"waveform": audio_tensor.unsqueeze(0), "sample_rate": sr})
            embeddings.append(embedding)
            valid_files.append(fpath)

        except Exception as e:
            pass

    embeddings = np.array(embeddings)
    print(f"Extracted {len(embeddings)} embeddings\n")

    # Test different thresholds
    print("Testing thresholds:")
    print("-" * 70)
    print(f"{'Threshold':<12} {'Speakers':<12} {'Top 5 Cluster Sizes':<30}")
    print("-" * 70)

    results = []
    for threshold in np.arange(0.05, 0.35, 0.05):
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=1 - threshold,
            metric='cosine',
            linkage='average'
        )
        labels = clustering.fit_predict(embeddings)

        n_clusters = len(set(labels))
        cluster_sizes = [np.sum(labels == i) for i in range(n_clusters)]
        top5 = sorted(cluster_sizes, reverse=True)[:5]

        results.append({
            'method': 'pyannote',
            'threshold': threshold,
            'n_clusters': n_clusters,
            'labels': labels,
            'cluster_sizes': cluster_sizes,
            'valid_files': valid_files
        })

        print(f"{threshold:<12.2f} {n_clusters:<12} {str(top5):<30}")

    print()
    return results


def create_speaker_directories(result, output_dir):
    """Create speaker directories with symlinks to audio files"""
    method = result['method']
    threshold = result['threshold']
    labels = result['labels']
    valid_files = result['valid_files']
    n_clusters = result['n_clusters']

    # Create output directory
    dir_name = f"{method}_threshold_{threshold:.2f}_speakers_{n_clusters}"
    full_output_dir = Path(output_dir) / dir_name
    full_output_dir.mkdir(parents=True, exist_ok=True)

    # Create speaker subdirectories and symlinks
    for i in range(n_clusters):
        speaker_dir = full_output_dir / f"speaker_{i:02d}"
        speaker_dir.mkdir(exist_ok=True)

    # Create symlinks
    for file_idx, label in enumerate(labels):
        source_file = valid_files[file_idx]
        speaker_dir = full_output_dir / f"speaker_{label:02d}"
        link_path = speaker_dir / source_file.name

        # Create symlink (remove if exists)
        if link_path.exists():
            link_path.unlink()
        link_path.symlink_to(source_file.resolve())

    # Create summary file
    summary_path = full_output_dir / "summary.txt"
    with open(summary_path, 'w') as f:
        f.write(f"Method: {method}\n")
        f.write(f"Threshold: {threshold:.2f}\n")
        f.write(f"Total Speakers: {n_clusters}\n")
        f.write(f"Total Fragments: {len(valid_files)}\n\n")
        f.write("Speaker Distribution:\n")

        cluster_sizes = result['cluster_sizes']
        for i in range(n_clusters):
            count = cluster_sizes[i]
            percentage = count / len(valid_files) * 100
            f.write(f"  Speaker {i:02d}: {count} fragments ({percentage:.1f}%)\n")

    print(f"✓ Created: {full_output_dir}")
    print(f"  Speakers: {n_clusters}")
    print(f"  Files: {len(valid_files)}")
    print()

    return full_output_dir


def main():
    print("="*70)
    print("Speaker Clustering Threshold Tuning & Organization")
    print("="*70)
    print(f"\nFragments: {FRAGMENTS_DIR}")
    print(f"Output: {OUTPUT_BASE_DIR}\n")

    # Test Resemblyzer
    resemblyzer_results = test_resemblyzer_thresholds()

    # Test pyannote
    pyannote_results = test_pyannote_thresholds()

    # Find best results (closest to 10 speakers)
    print("="*70)
    print("Creating Speaker Directories")
    print("="*70 + "\n")

    all_results = resemblyzer_results + pyannote_results

    # Find results closest to 10 speakers
    target_speakers = 10

    for result in all_results:
        diff = abs(result['n_clusters'] - target_speakers)
        if diff <= 3:  # Within 3 of target
            create_speaker_directories(result, OUTPUT_BASE_DIR)

    print("="*70)
    print("Summary")
    print("="*70)
    print(f"\nOutput directory: {OUTPUT_BASE_DIR}")
    print(f"\nRecommendations for ~{target_speakers} speakers:")

    # Find best match for each method
    for method in ['Resemblyzer', 'pyannote']:
        method_results = [r for r in all_results if r['method'] == method]
        if method_results:
            best = min(method_results, key=lambda r: abs(r['n_clusters'] - target_speakers))
            print(f"\n{method}:")
            print(f"  Threshold: {best['threshold']:.2f}")
            print(f"  Speakers: {best['n_clusters']}")
            print(f"  Top 5 sizes: {sorted(best['cluster_sizes'], reverse=True)[:5]}")


if __name__ == '__main__':
    main()
