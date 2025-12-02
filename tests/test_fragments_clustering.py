#!/usr/bin/env python3
"""
Test speaker clustering on VAD-segmented fragments
"""

import sys
import os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity
import time

# Fragments directory
FRAGMENTS_DIR = "/home/camus/work/stream-polyglot/assets/.stream-polyglot-cache/066. 移民第五季 第十三集/fragments"


def test_fragments_clustering(max_fragments=100):
    """Test speaker clustering on VAD-segmented fragments"""

    from resemblyzer import VoiceEncoder, preprocess_wav

    print("="*70)
    print("Speaker Clustering Test on VAD Fragments")
    print("="*70)
    print(f"\nFragments directory: {FRAGMENTS_DIR}")

    # Get all fragment files
    fragments_dir = Path(FRAGMENTS_DIR)
    fragment_files = sorted(fragments_dir.glob("fragment_*.wav"))

    print(f"Total fragments found: {len(fragment_files)}")
    print(f"Testing first {max_fragments} fragments\n")

    # Limit to max_fragments
    fragment_files = fragment_files[:max_fragments]

    # Initialize encoder
    print("Loading Resemblyzer encoder...")
    start_time = time.time()
    encoder = VoiceEncoder()
    load_time = time.time() - start_time
    print(f"✓ Encoder loaded in {load_time:.2f}s\n")

    # Extract embeddings
    print("Extracting embeddings from fragments...")
    embeddings = []
    valid_files = []
    skipped = 0

    start_time = time.time()
    for i, fpath in enumerate(fragment_files):
        try:
            # Load and preprocess
            wav = preprocess_wav(fpath)

            # Skip very short audio (< 0.4 seconds)
            if len(wav) < 6400:  # 0.4s at 16kHz
                skipped += 1
                continue

            # Extract embedding
            embedding = encoder.embed_utterance(wav)
            embeddings.append(embedding)
            valid_files.append(fpath)

            if (i + 1) % 20 == 0:
                print(f"  Processed {i+1}/{len(fragment_files)} fragments ({len(embeddings)} valid)")

        except Exception as e:
            skipped += 1
            if "too short" in str(e).lower():
                continue
            print(f"  ⚠ Fragment {fpath.name}: {e}")

    extract_time = time.time() - start_time
    embeddings = np.array(embeddings)

    print(f"\n✓ Extracted {len(embeddings)} embeddings in {extract_time:.2f}s")
    print(f"  Skipped: {skipped} fragments (too short)")
    print(f"  Embedding shape: {embeddings.shape}\n")

    if len(embeddings) < 2:
        print("❌ Not enough valid embeddings for clustering")
        return

    # Compute similarity matrix
    print("Computing pairwise similarities...")
    similarities = cosine_similarity(embeddings)

    # Statistics
    triu_indices = np.triu_indices(len(similarities), k=1)
    similarity_values = similarities[triu_indices]

    print(f"\nSimilarity Statistics:")
    print(f"  Min:        {similarity_values.min():.4f}")
    print(f"  Max:        {similarity_values.max():.4f}")
    print(f"  Mean:       {similarity_values.mean():.4f}")
    print(f"  Median:     {np.median(similarity_values):.4f}")
    print(f"  Std Dev:    {similarity_values.std():.4f}")
    print(f"  25th %ile:  {np.percentile(similarity_values, 25):.4f}")
    print(f"  75th %ile:  {np.percentile(similarity_values, 75):.4f}\n")

    # Clustering with different thresholds
    print("Clustering Results:")
    print("-" * 70)
    print(f"{'Threshold':<12} {'Speakers':<12} {'Largest Cluster':<20} {'Smallest Cluster':<20}")
    print("-" * 70)

    clustering_results = []
    for threshold in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=1 - threshold,
            metric='cosine',
            linkage='average'
        )
        labels = clustering.fit_predict(embeddings)

        n_clusters = len(set(labels))
        cluster_sizes = [np.sum(labels == i) for i in range(n_clusters)]

        largest = max(cluster_sizes)
        smallest = min(cluster_sizes)

        clustering_results.append({
            'threshold': threshold,
            'n_clusters': n_clusters,
            'labels': labels,
            'cluster_sizes': cluster_sizes
        })

        print(f"{threshold:<12.1f} {n_clusters:<12} {largest:<20} {smallest:<20}")

    print()

    # Show detailed distribution for threshold 0.5
    result_05 = [r for r in clustering_results if r['threshold'] == 0.5][0]
    print(f"Detailed distribution at threshold 0.5 ({result_05['n_clusters']} speakers):")
    cluster_sizes_sorted = sorted(enumerate(result_05['cluster_sizes']), key=lambda x: x[1], reverse=True)
    for i, (cluster_id, size) in enumerate(cluster_sizes_sorted[:10]):
        print(f"  Speaker {cluster_id}: {size} fragments ({size/len(embeddings)*100:.1f}%)")
        if i == 9 and len(cluster_sizes_sorted) > 10:
            print(f"  ... and {len(cluster_sizes_sorted) - 10} more speakers")
    print()

    # Create visualizations
    output_dir = Path("/home/camus/work/stream-polyglot/assets/.clustering_analysis")
    output_dir.mkdir(exist_ok=True)

    # 1. Similarity matrix heatmap (sample if too large)
    print("Generating similarity matrix heatmap...")
    sample_size = min(100, len(similarities))
    sample_indices = np.linspace(0, len(similarities)-1, sample_size, dtype=int)

    plt.figure(figsize=(12, 10))
    plt.imshow(similarities[np.ix_(sample_indices, sample_indices)], cmap='viridis', aspect='auto')
    plt.colorbar(label='Cosine Similarity')
    plt.title(f'Speaker Similarity Matrix (sampled {sample_size} fragments)\n066. 移民第五季 第十三集', fontsize=12)
    plt.xlabel('Fragment Index (sampled)')
    plt.ylabel('Fragment Index (sampled)')
    plt.tight_layout()
    heatmap_path = output_dir / 'similarity_heatmap_fragments.png'
    plt.savefig(heatmap_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {heatmap_path}\n")

    # 2. Similarity distribution
    print("Generating similarity distribution...")
    plt.figure(figsize=(10, 6))
    plt.hist(similarity_values, bins=50, edgecolor='black', alpha=0.7)
    plt.axvline(similarity_values.mean(), color='red', linestyle='--',
                label=f'Mean: {similarity_values.mean():.3f}')
    plt.axvline(np.median(similarity_values), color='green', linestyle='--',
                label=f'Median: {np.median(similarity_values):.3f}')
    plt.xlabel('Cosine Similarity')
    plt.ylabel('Frequency')
    plt.title('Distribution of Pairwise Similarities (VAD Fragments)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    hist_path = output_dir / 'similarity_distribution_fragments.png'
    plt.savefig(hist_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {hist_path}\n")

    # 3. Cluster size distribution
    print("Generating cluster size distribution...")
    result_05 = [r for r in clustering_results if r['threshold'] == 0.5][0]
    cluster_sizes = sorted(result_05['cluster_sizes'], reverse=True)

    plt.figure(figsize=(12, 6))
    plt.bar(range(len(cluster_sizes)), cluster_sizes)
    plt.xlabel('Speaker (ranked by cluster size)')
    plt.ylabel('Number of fragments')
    plt.title(f'Speaker Distribution (Threshold 0.5, {len(cluster_sizes)} speakers detected)')
    plt.grid(True, axis='y', alpha=0.3)
    plt.tight_layout()
    dist_path = output_dir / 'cluster_distribution_fragments.png'
    plt.savefig(dist_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {dist_path}\n")

    # Summary
    print("="*70)
    print("ANALYSIS SUMMARY")
    print("="*70)
    print(f"\n📊 Data:")
    print(f"  - Total fragments: {len(fragment_files)}")
    print(f"  - Valid embeddings: {len(embeddings)}")
    print(f"  - Skipped (too short): {skipped}")

    print(f"\n🔍 Similarity Analysis:")
    print(f"  - Mean: {similarity_values.mean():.4f}")
    print(f"  - Range: [{similarity_values.min():.4f}, {similarity_values.max():.4f}]")
    print(f"  - Std Dev: {similarity_values.std():.4f}")

    print(f"\n👥 Speaker Detection (Threshold 0.5):")
    result_05 = [r for r in clustering_results if r['threshold'] == 0.5][0]
    print(f"  - Detected: {result_05['n_clusters']} speaker(s)")
    print(f"  - Largest cluster: {max(result_05['cluster_sizes'])} fragments ({max(result_05['cluster_sizes'])/len(embeddings)*100:.1f}%)")
    print(f"  - Smallest cluster: {min(result_05['cluster_sizes'])} fragments ({min(result_05['cluster_sizes'])/len(embeddings)*100:.1f}%)")

    if result_05['n_clusters'] == 1:
        print(f"\n✅ Result: SINGLE-SPEAKER recording")
    elif result_05['n_clusters'] <= 3:
        print(f"\n✅ Result: MULTI-SPEAKER recording ({result_05['n_clusters']} speakers)")
        print(f"   This appears to be a conversation or interview format")
    else:
        print(f"\n⚠️  Result: {result_05['n_clusters']} speakers detected")
        print(f"   This might indicate:")
        print(f"   - Multiple speakers (podcast with many guests)")
        print(f"   - Voice variation being over-split")
        print(f"   - Background noise/music being detected as separate speakers")

    print(f"\n📁 Visualizations saved to: {output_dir}/")
    print("="*70 + "\n")


if __name__ == '__main__':
    test_fragments_clustering(max_fragments=100)
