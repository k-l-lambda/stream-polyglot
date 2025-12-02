#!/usr/bin/env python3
"""
Detailed Resemblyzer speaker clustering analysis

Test with longer audio to see clustering patterns
"""

import sys
import os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import librosa
import time
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity

# Audio file path
AUDIO_PATH = "/home/camus/work/stream-polyglot/assets/066. 移民第五季 第十三集.mp3"


def test_resemblyzer_detailed(segment_duration=10.0, max_segments=60):
    """Detailed Resemblyzer analysis with visualization"""

    from resemblyzer import VoiceEncoder

    print("="*70)
    print("Detailed Resemblyzer Speaker Clustering Analysis")
    print("="*70)
    print(f"\nAudio: {Path(AUDIO_PATH).name}")
    print(f"Segment duration: {segment_duration}s")
    print(f"Max segments: {max_segments} ({max_segments * segment_duration / 60:.1f} minutes)\n")

    # Load audio
    print("Loading audio...")
    audio, sr = librosa.load(AUDIO_PATH, sr=16000)
    total_duration = len(audio) / sr
    print(f"  Total duration: {total_duration:.1f}s ({total_duration / 60:.1f} minutes)")
    print(f"  Sample rate: {sr} Hz\n")

    # Create segments
    print(f"Creating segments...")
    segment_samples = int(segment_duration * sr)
    segments = []
    segment_times = []

    for i in range(max_segments):
        start_sample = i * segment_samples
        end_sample = start_sample + segment_samples

        if end_sample > len(audio):
            break

        segment = audio[start_sample:end_sample]
        segments.append(segment)
        segment_times.append(i * segment_duration)

    print(f"  Created {len(segments)} segments\n")

    # Initialize encoder
    print("Loading Resemblyzer encoder...")
    start_time = time.time()
    encoder = VoiceEncoder()
    load_time = time.time() - start_time
    print(f"  Loaded in {load_time:.2f}s\n")

    # Extract embeddings
    print("Extracting embeddings...")
    start_time = time.time()
    embeddings = []

    for i, seg in enumerate(segments):
        try:
            embedding = encoder.embed_utterance(seg)
            embeddings.append(embedding)
            if (i + 1) % 10 == 0:
                print(f"  Processed {i+1}/{len(segments)} segments")
        except Exception as e:
            print(f"  ⚠ Segment {i}: {e}")

    extract_time = time.time() - start_time
    embeddings = np.array(embeddings)

    print(f"\n  Extracted {len(embeddings)} embeddings in {extract_time:.2f}s")
    print(f"  Embedding shape: {embeddings.shape}")
    print(f"  Average time per segment: {extract_time / len(embeddings):.3f}s\n")

    # Compute similarity matrix
    print("Computing similarity matrix...")
    similarities = cosine_similarity(embeddings)

    # Statistics
    triu_indices = np.triu_indices(len(similarities), k=1)
    similarity_values = similarities[triu_indices]

    print("\nSimilarity Statistics:")
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
    print(f"{'Threshold':<12} {'Speakers':<12} {'Distribution':<30} {'Largest %':<12}")
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
        largest_pct = max(cluster_sizes) / len(labels) * 100

        clustering_results.append({
            'threshold': threshold,
            'n_clusters': n_clusters,
            'labels': labels,
            'cluster_sizes': cluster_sizes
        })

        # Format distribution
        if n_clusters <= 5:
            dist_str = str(cluster_sizes)
        else:
            top3 = sorted(cluster_sizes, reverse=True)[:3]
            dist_str = f"{top3} + {n_clusters - 3} more"

        print(f"{threshold:<12.1f} {n_clusters:<12} {dist_str:<30} {largest_pct:<12.1f}")

    print()

    # Create visualizations
    output_dir = Path("/home/camus/work/stream-polyglot/assets/.clustering_analysis")
    output_dir.mkdir(exist_ok=True)

    # 1. Similarity matrix heatmap
    print("Generating similarity matrix heatmap...")
    plt.figure(figsize=(12, 10))
    plt.imshow(similarities, cmap='viridis', aspect='auto')
    plt.colorbar(label='Cosine Similarity')
    plt.title(f'Speaker Similarity Matrix\n{Path(AUDIO_PATH).name}', fontsize=12)
    plt.xlabel('Segment Index')
    plt.ylabel('Segment Index')
    plt.tight_layout()
    heatmap_path = output_dir / 'similarity_heatmap.png'
    plt.savefig(heatmap_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {heatmap_path}\n")

    # 2. Similarity distribution histogram
    print("Generating similarity distribution...")
    plt.figure(figsize=(10, 6))
    plt.hist(similarity_values, bins=50, edgecolor='black', alpha=0.7)
    plt.axvline(similarity_values.mean(), color='red', linestyle='--', label=f'Mean: {similarity_values.mean():.3f}')
    plt.axvline(np.median(similarity_values), color='green', linestyle='--', label=f'Median: {np.median(similarity_values):.3f}')
    plt.xlabel('Cosine Similarity')
    plt.ylabel('Frequency')
    plt.title('Distribution of Pairwise Similarities')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    hist_path = output_dir / 'similarity_distribution.png'
    plt.savefig(hist_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {hist_path}\n")

    # 3. Timeline clustering visualization (threshold 0.5)
    print("Generating timeline clustering visualization...")
    result_05 = [r for r in clustering_results if r['threshold'] == 0.5][0]
    labels_05 = result_05['labels']

    plt.figure(figsize=(14, 4))
    colors = plt.cm.Set3(np.linspace(0, 1, max(labels_05) + 1))

    for i, label in enumerate(labels_05):
        start_time = segment_times[i]
        end_time = start_time + segment_duration
        plt.barh(0, segment_duration, left=start_time, height=0.8,
                color=colors[label], edgecolor='black', linewidth=0.5)

    plt.ylim(-0.5, 0.5)
    plt.xlim(0, segment_times[-1] + segment_duration)
    plt.xlabel('Time (seconds)')
    plt.yticks([])
    plt.title(f'Speaker Clustering Timeline (Threshold 0.5, {result_05["n_clusters"]} speaker(s))')
    plt.grid(True, axis='x', alpha=0.3)
    plt.tight_layout()
    timeline_path = output_dir / 'clustering_timeline_0.5.png'
    plt.savefig(timeline_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {timeline_path}\n")

    # Summary
    print("="*70)
    print("ANALYSIS SUMMARY")
    print("="*70)
    print(f"\n📊 Audio Analysis:")
    print(f"  - Duration: {total_duration:.1f}s ({total_duration / 60:.1f} minutes)")
    print(f"  - Segments analyzed: {len(embeddings)}")
    print(f"  - Coverage: {len(embeddings) * segment_duration:.1f}s ({len(embeddings) * segment_duration / 60:.1f} minutes)")

    print(f"\n🔍 Similarity Analysis:")
    print(f"  - Mean similarity: {similarity_values.mean():.4f}")
    print(f"  - Similarity range: [{similarity_values.min():.4f}, {similarity_values.max():.4f}]")
    print(f"  - Standard deviation: {similarity_values.std():.4f}")

    print(f"\n👥 Speaker Detection:")
    result_05 = [r for r in clustering_results if r['threshold'] == 0.5][0]
    print(f"  - With threshold 0.5: {result_05['n_clusters']} speaker(s) detected")
    print(f"  - Distribution: {result_05['cluster_sizes']}")

    if result_05['n_clusters'] == 1:
        print(f"\n✅ Conclusion: This appears to be a **SINGLE-SPEAKER** recording")
        print(f"   All {len(embeddings)} segments cluster together consistently")
    else:
        print(f"\n✅ Conclusion: This appears to be a **MULTI-SPEAKER** recording")
        print(f"   Detected {result_05['n_clusters']} distinct speakers")

    print(f"\n📁 Visualizations saved to:")
    print(f"  {output_dir}/")
    print(f"  - similarity_heatmap.png")
    print(f"  - similarity_distribution.png")
    print(f"  - clustering_timeline_0.5.png")

    print("\n" + "="*70)
    print("Analysis completed!")
    print("="*70 + "\n")


if __name__ == '__main__':
    test_resemblyzer_detailed(segment_duration=10.0, max_segments=60)
