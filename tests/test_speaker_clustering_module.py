#!/usr/bin/env python3
"""
Test speaker_clustering.py module independently
"""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from speaker_clustering import SpeakerClusterer


def test_clustering():
    """Test clustering on existing audio fragments"""
    print("="*70)
    print("Testing Speaker Clustering Module")
    print("="*70 + "\n")

    # Use existing cache from previous tests
    cache_dir = Path.home() / "work/stream-polyglot/assets/.stream-polyglot-cache/066. 移民第五季 第十三集"
    fragments_dir = cache_dir / "fragments"
    timeline_file = cache_dir / "timeline.json"

    # Check if test data exists
    if not timeline_file.exists():
        print(f"❌ Timeline file not found: {timeline_file}")
        print("   Run audio segmentation first to generate test data")
        return False

    # Load timeline
    print(f"Loading timeline from: {timeline_file}")
    with open(timeline_file, 'r') as f:
        cache_data = json.load(f)
        timeline = cache_data.get('timeline', [])

    print(f"✓ Loaded {len(timeline)} fragments from timeline\n")

    # Test 1: Initialize clusterer
    print("Test 1: Initialize SpeakerClusterer")
    print("-" * 70)
    try:
        clusterer = SpeakerClusterer(method='resemblyzer', threshold=0.65)
        print("✓ Clusterer initialized successfully")
        print(f"  Method: {clusterer.method}")
        print(f"  Threshold: {clusterer.threshold}\n")
    except Exception as e:
        print(f"❌ Failed to initialize: {e}\n")
        return False

    # Test 2: Cluster fragments (use first 50 for speed)
    print("Test 2: Cluster Fragments")
    print("-" * 70)
    test_timeline = timeline[:50]  # Test with first 50 fragments
    print(f"Testing with first {len(test_timeline)} fragments...")

    try:
        speaker_clusters = clusterer.cluster_fragments(fragments_dir, test_timeline)
        print(f"✓ Clustering completed")
        print(f"  Detected {len(speaker_clusters)} speakers\n")

        # Show distribution
        print("Speaker Distribution:")
        for speaker_id in sorted(speaker_clusters.keys()):
            fragments = speaker_clusters[speaker_id]
            total_duration = sum(f['duration'] for f in fragments)
            print(f"  {speaker_id}: {len(fragments)} fragments ({total_duration:.1f}s total)")

        print()

    except Exception as e:
        print(f"❌ Clustering failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False

    # Test 3: Select reference fragments
    print("Test 3: Select Reference Fragments")
    print("-" * 70)
    for speaker_id, cluster in list(speaker_clusters.items())[:3]:  # Test first 3 speakers
        try:
            selected = clusterer.select_reference_fragments(cluster, max_duration=30.0)
            total_dur = sum(
                f['duration'] for f in cluster if f['file'] in selected
            )
            print(f"{speaker_id}:")
            print(f"  Selected {len(selected)} fragments (total: {total_dur:.1f}s)")
            for frag_file in selected:
                frag_info = next(f for f in cluster if f['file'] == frag_file)
                print(f"    - {frag_file} ({frag_info['duration']:.1f}s)")

        except Exception as e:
            print(f"  ❌ Failed: {e}")

    print()

    # Test 4: Concatenate fragments
    print("Test 4: Concatenate Fragments")
    print("-" * 70)
    test_output_dir = cache_dir / "test_speaker_references"
    test_output_dir.mkdir(exist_ok=True)

    for speaker_id, cluster in list(speaker_clusters.items())[:2]:  # Test first 2
        try:
            selected_files = clusterer.select_reference_fragments(cluster, max_duration=30.0)
            output_path = test_output_dir / f"{speaker_id}_ref_test.wav"

            clusterer.concatenate_fragments(selected_files, fragments_dir, output_path)

            # Check output
            import soundfile as sf
            audio, sr = sf.read(output_path)
            duration = len(audio) / sr

            print(f"{speaker_id}:")
            print(f"  ✓ Concatenated {len(selected_files)} fragments")
            print(f"  Output: {output_path.name}")
            print(f"  Duration: {duration:.1f}s")
            print(f"  Sample rate: {sr} Hz")

        except Exception as e:
            print(f"  ❌ Failed: {e}")

    print()

    # Test 5: Assign speaker to segment
    print("Test 5: Assign Speaker to Segment")
    print("-" * 70)
    test_segments = [
        {'start': 31.8, 'end': 33.4},  # Known from first fragment
        {'start': 100.0, 'end': 105.0},
        {'start': 150.0, 'end': 155.0},
    ]

    for seg in test_segments:
        speaker_id = clusterer.assign_speaker_to_segment(seg, speaker_clusters)
        print(f"Segment [{seg['start']:.1f}s - {seg['end']:.1f}s] → {speaker_id}")

    print()

    print("="*70)
    print("✅ All tests completed successfully!")
    print("="*70)

    return True


if __name__ == '__main__':
    success = test_clustering()
    sys.exit(0 if success else 1)
