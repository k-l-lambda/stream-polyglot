#!/usr/bin/env python3
"""
Test speaker clustering with real audio and show reference audio mapping
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from speaker_clustering import SpeakerClusterer


def test_speaker_clustering_workflow():
    """Test full speaker clustering workflow and show reference audio mapping"""

    print("="*80)
    print("Speaker Clustering Test - Reference Audio Mapping")
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

    # Perform clustering on all fragments (not just 50)
    print(f"Clustering all {len(timeline)} fragments...")
    print("This may take ~30 seconds...\n")

    speaker_clusters = clusterer.cluster_fragments(fragments_dir, timeline)

    print("="*80)
    print("CLUSTERING RESULTS")
    print("="*80 + "\n")

    print(f"Detected {len(speaker_clusters)} speakers\n")

    # Show speaker statistics
    print("Speaker Statistics:")
    print("-" * 80)
    for speaker_id in sorted(speaker_clusters.keys()):
        cluster = speaker_clusters[speaker_id]
        total_duration = sum(f['duration'] for f in cluster)
        avg_duration = total_duration / len(cluster)

        print(f"{speaker_id}:")
        print(f"  Fragments: {len(cluster)}")
        print(f"  Total duration: {total_duration:.1f}s")
        print(f"  Average fragment: {avg_duration:.1f}s")

        # Show fragment duration distribution
        durations = [f['duration'] for f in cluster]
        durations.sort(reverse=True)
        if len(durations) <= 5:
            print(f"  Durations: {[f'{d:.1f}s' for d in durations]}")
        else:
            print(f"  Top 5 longest: {[f'{d:.1f}s' for d in durations[:5]]}")
        print()

    # Generate reference audio for each speaker
    print("="*80)
    print("REFERENCE AUDIO GENERATION")
    print("="*80 + "\n")

    ref_dir = cache_dir / "test_speaker_references_full"
    ref_dir.mkdir(exist_ok=True)

    speaker_references = {}

    for speaker_id in sorted(speaker_clusters.keys()):
        cluster = speaker_clusters[speaker_id]

        # Select reference fragments (longest 2-3, max 30s)
        selected_files = clusterer.select_reference_fragments(cluster, max_duration=30.0)

        print(f"{speaker_id}:")
        print(f"  Selected {len(selected_files)} fragments from {len(cluster)} total:")

        # Show which fragments were selected
        for i, frag_file in enumerate(selected_files, 1):
            frag_info = next(f for f in cluster if f['file'] == frag_file)
            print(f"    {i}. {frag_file} ({frag_info['duration']:.1f}s)")

        # Concatenate
        ref_path = ref_dir / f"{speaker_id}_ref.wav"
        clusterer.concatenate_fragments(selected_files, fragments_dir, ref_path)

        # Verify output
        import soundfile as sf
        audio, sr = sf.read(ref_path)
        duration = len(audio) / sr

        speaker_references[speaker_id] = ref_path

        print(f"  → Reference audio: {ref_path.name} ({duration:.1f}s, {sr}Hz)")
        print()

    # Now simulate subtitle matching and show reference audio mapping
    print("="*80)
    print("SIMULATED VOICE-CLONE REFERENCE MAPPING")
    print("="*80 + "\n")

    print("Simulating subtitle segments at different time points...\n")

    # Create sample subtitle segments at different times
    sample_segments = [
        {'start': 31.0, 'end': 35.0, 'text': 'Subtitle 1'},
        {'start': 62.0, 'end': 68.0, 'text': 'Subtitle 2'},
        {'start': 100.0, 'end': 105.0, 'text': 'Subtitle 3'},
        {'start': 150.0, 'end': 155.0, 'text': 'Subtitle 4'},
        {'start': 200.0, 'end': 205.0, 'text': 'Subtitle 5'},
        {'start': 300.0, 'end': 305.0, 'text': 'Subtitle 6'},
        {'start': 500.0, 'end': 510.0, 'text': 'Subtitle 7'},
        {'start': 800.0, 'end': 810.0, 'text': 'Subtitle 8'},
        {'start': 1200.0, 'end': 1210.0, 'text': 'Subtitle 9'},
        {'start': 1500.0, 'end': 1510.0, 'text': 'Subtitle 10'},
    ]

    print(f"Testing {len(sample_segments)} sample subtitle segments:\n")
    print("-" * 80)
    print(f"{'Segment':<12} {'Time Range':<20} {'Speaker':<15} {'Reference Audio':<30}")
    print("-" * 80)

    for seg in sample_segments:
        # Assign speaker
        speaker_id = clusterer.assign_speaker_to_segment(seg, speaker_clusters)

        if speaker_id and speaker_id in speaker_references:
            ref_path = speaker_references[speaker_id]
            ref_name = ref_path.name

            # Get reference duration
            audio, sr = sf.read(ref_path)
            ref_duration = len(audio) / sr

            time_range = f"{seg['start']:.1f}s - {seg['end']:.1f}s"
            ref_info = f"{ref_name} ({ref_duration:.1f}s)"

            print(f"{seg['text']:<12} {time_range:<20} {speaker_id:<15} {ref_info:<30}")
        else:
            print(f"{seg['text']:<12} {seg['start']:.1f}s - {seg['end']:.1f}s    ❌ NO MATCH")

    print("-" * 80)
    print()

    # Summary
    print("="*80)
    print("SUMMARY")
    print("="*80 + "\n")

    print(f"✓ Total speakers detected: {len(speaker_clusters)}")
    print(f"✓ Total fragments: {len(timeline)}")
    print(f"✓ Reference audio files generated: {len(speaker_references)}")
    print()

    print("Reference Audio Details:")
    for speaker_id in sorted(speaker_references.keys()):
        ref_path = speaker_references[speaker_id]
        audio, sr = sf.read(ref_path)
        duration = len(audio) / sr
        cluster_size = len(speaker_clusters[speaker_id])
        print(f"  {speaker_id}: {ref_path.name} ({duration:.1f}s) from {cluster_size} fragments")

    print()
    print("="*80)
    print("✅ Test completed successfully!")
    print("="*80)

    return True


if __name__ == '__main__':
    success = test_speaker_clustering_workflow()
    sys.exit(0 if success else 1)
