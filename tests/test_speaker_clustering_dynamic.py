#!/usr/bin/env python3
"""
Test dynamic reference audio selection strategy

This test shows how the new strategy works:
- Segments >= 10s: use itself as reference
- Segments < 5s: find nearby fragments to reach 5-10s reference
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from speaker_clustering import SpeakerClusterer


def test_dynamic_reference_selection():
    """Test dynamic reference audio selection for segments"""

    print("="*80)
    print("Speaker Clustering Test - Dynamic Reference Audio Selection")
    print("="*80 + "\n")

    # Setup paths
    audio_file = Path.home() / "work/stream-polyglot/assets/066. 移民第五季 第十三集.mp3"
    cache_dir = Path.home() / "work/stream-polyglot/assets/.stream-polyglot-cache/066. 移民第五季 第十三集"
    fragments_dir = cache_dir / "fragments"
    timeline_file = cache_dir / "timeline.json"

    # Check files exist
    if not timeline_file.exists():
        print(f"❌ Timeline file not found: {timeline_file}")
        print("   Please run audio segmentation first")
        return False

    print(f"Audio: {audio_file.name}")
    print(f"Cache: {cache_dir}\n")

    # Load timeline
    print("Loading timeline...")
    with open(timeline_file, 'r') as f:
        cache_data = json.load(f)
        timeline = cache_data.get('timeline', [])

    print(f"✓ Loaded {len(timeline)} fragments\n")

    # Initialize clusterer
    print("Initializing speaker clusterer (threshold=0.65)...")
    clusterer = SpeakerClusterer(method='resemblyzer', threshold=0.65)
    print("✓ Clusterer ready\n")

    # Perform clustering
    print(f"Clustering all {len(timeline)} fragments...")
    print("This may take ~30 seconds...\n")

    speaker_clusters = clusterer.cluster_fragments(fragments_dir, timeline)

    print("="*80)
    print("CLUSTERING RESULTS")
    print("="*80 + "\n")

    print(f"Detected {len(speaker_clusters)} speakers\n")

    # Show speaker statistics (brief)
    print("Speaker Statistics (brief):")
    print("-" * 80)
    for speaker_id in sorted(speaker_clusters.keys()):
        cluster = speaker_clusters[speaker_id]
        total_duration = sum(f['duration'] for f in cluster)
        print(f"{speaker_id}: {len(cluster)} fragments, {total_duration:.1f}s total")
    print()

    # Test dynamic reference selection with sample segments
    print("="*80)
    print("DYNAMIC REFERENCE AUDIO SELECTION TEST")
    print("="*80 + "\n")

    # Create sample segments covering different fragment durations
    # We'll pick some actual fragments from timeline to simulate
    sample_segments = []

    # Calculate duration for each fragment
    fragments_with_duration = []
    for frag in timeline:
        frag_copy = frag.copy()
        frag_copy['duration'] = frag['end'] - frag['start']
        fragments_with_duration.append(frag_copy)

    # Get some fragments of different durations
    fragments_sorted = sorted(fragments_with_duration, key=lambda f: f['duration'], reverse=True)

    # Pick fragments with different duration ranges
    duration_ranges = [
        ("Long (>10s)", lambda d: d >= 10.0),
        ("Medium (5-10s)", lambda d: 5.0 <= d < 10.0),
        ("Short (2-5s)", lambda d: 2.0 <= d < 5.0),
        ("Very short (<2s)", lambda d: d < 2.0),
    ]

    for range_name, duration_filter in duration_ranges:
        matching = [f for f in fragments_sorted if duration_filter(f['duration'])]
        if matching:
            # Take first 2-3 from each range
            for frag in matching[:3]:
                sample_segments.append({
                    'start': frag['start'],
                    'end': frag['end'],
                    'duration': frag['duration'],
                    'range': range_name,
                    'text': f"Segment at {frag['start']:.1f}s"
                })

    print(f"Testing with {len(sample_segments)} sample segments:\n")

    # Test each segment
    print("-" * 80)
    print(f"{'Segment':<20} {'Duration':<12} {'Speaker':<12} {'Reference Strategy':<40}")
    print("-" * 80)

    detailed_results = []

    for seg in sample_segments:
        # Get dynamic reference
        speaker_id, ref_files, ref_duration = clusterer.select_reference_for_segment(
            {'start': seg['start'], 'end': seg['end']},
            speaker_clusters,
            fragments_dir,
            min_duration=5.0,
            target_duration=10.0
        )

        if speaker_id:
            # Determine strategy used
            if seg['duration'] >= 10.0:
                strategy = f"Use itself ({seg['duration']:.1f}s)"
            elif seg['duration'] < 5.0:
                if len(ref_files) > 1:
                    strategy = f"Concat {len(ref_files)} frags → {ref_duration:.1f}s"
                else:
                    strategy = f"Use itself ({seg['duration']:.1f}s, no nearby)"
            else:
                strategy = f"Use itself ({seg['duration']:.1f}s)"

            segment_name = f"{seg['start']:.1f}s [{seg['range']}]"
            duration_str = f"{seg['duration']:.1f}s"

            print(f"{segment_name:<20} {duration_str:<12} {speaker_id:<12} {strategy:<40}")

            detailed_results.append({
                'segment': segment_name,
                'segment_duration': seg['duration'],
                'speaker': speaker_id,
                'ref_files': ref_files,
                'ref_duration': ref_duration,
                'strategy': strategy
            })
        else:
            print(f"{seg['start']:.1f}s [{seg['range']}]    ❌ NO MATCH")

    print("-" * 80)
    print()

    # Show detailed reference file information for a few examples
    print("="*80)
    print("DETAILED REFERENCE MAPPING (First 5 Examples)")
    print("="*80 + "\n")

    for i, result in enumerate(detailed_results[:5], 1):
        print(f"{i}. Segment: {result['segment']}")
        print(f"   Segment duration: {result['segment_duration']:.1f}s")
        print(f"   Speaker: {result['speaker']}")
        print(f"   Strategy: {result['strategy']}")
        print(f"   Reference files ({len(result['ref_files'])} files, {result['ref_duration']:.1f}s total):")

        for j, ref_file in enumerate(result['ref_files'], 1):
            # Find fragment info
            frag_info = next((f for f in fragments_with_duration if f['file'] == ref_file), None)
            if frag_info:
                print(f"      {j}. {ref_file}")
                print(f"         Time: {frag_info['start']:.1f}s - {frag_info['end']:.1f}s ({frag_info['duration']:.1f}s)")
            else:
                print(f"      {j}. {ref_file}")

        print()

    # Summary
    print("="*80)
    print("SUMMARY")
    print("="*80 + "\n")

    # Count strategies
    strategy_counts = {
        'self_long': 0,  # >= 10s use itself
        'self_medium': 0,  # 5-10s use itself
        'concat': 0,  # < 5s concat multiple
        'self_short': 0,  # < 5s use itself (no nearby)
    }

    for result in detailed_results:
        if result['segment_duration'] >= 10.0:
            strategy_counts['self_long'] += 1
        elif result['segment_duration'] >= 5.0:
            strategy_counts['self_medium'] += 1
        elif len(result['ref_files']) > 1:
            strategy_counts['concat'] += 1
        else:
            strategy_counts['self_short'] += 1

    print(f"✓ Total speakers detected: {len(speaker_clusters)}")
    print(f"✓ Total fragments: {len(timeline)}")
    print(f"✓ Test segments: {len(detailed_results)}")
    print()

    print("Strategy Distribution:")
    print(f"  Long segments (>=10s) using itself: {strategy_counts['self_long']}")
    print(f"  Medium segments (5-10s) using itself: {strategy_counts['self_medium']}")
    print(f"  Short segments (<5s) concatenating: {strategy_counts['concat']}")
    print(f"  Short segments (<5s) using itself: {strategy_counts['self_short']}")
    print()

    # Reference duration distribution
    ref_durations = [r['ref_duration'] for r in detailed_results]
    if ref_durations:
        avg_ref_duration = sum(ref_durations) / len(ref_durations)
        min_ref_duration = min(ref_durations)
        max_ref_duration = max(ref_durations)

        print("Reference Audio Duration Statistics:")
        print(f"  Average: {avg_ref_duration:.1f}s")
        print(f"  Min: {min_ref_duration:.1f}s")
        print(f"  Max: {max_ref_duration:.1f}s")
        print()

    print("="*80)
    print("✅ Test completed successfully!")
    print("="*80)

    return True


if __name__ == '__main__':
    success = test_dynamic_reference_selection()
    sys.exit(0 if success else 1)
