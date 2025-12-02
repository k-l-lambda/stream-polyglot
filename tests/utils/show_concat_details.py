#!/usr/bin/env python3
"""Show detailed concatenation examples from dynamic reference selection"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from speaker_clustering import SpeakerClusterer

# Setup paths
cache_dir = Path.home() / "work/stream-polyglot/assets/.stream-polyglot-cache/066. 移民第五季 第十三集"
fragments_dir = cache_dir / "fragments"
timeline_file = cache_dir / "timeline.json"

# Load timeline
with open(timeline_file, 'r') as f:
    cache_data = json.load(f)
    timeline = cache_data.get('timeline', [])

# Add duration
fragments_with_duration = []
for frag in timeline:
    frag_copy = frag.copy()
    frag_copy['duration'] = frag['end'] - frag['start']
    fragments_with_duration.append(frag_copy)

# Initialize clusterer
clusterer = SpeakerClusterer(method='resemblyzer', threshold=0.65)
speaker_clusters = clusterer.cluster_fragments(fragments_dir, timeline)

# Find some short fragments to test
short_frags = [f for f in fragments_with_duration if f['duration'] < 3.0][:5]

print("="*80)
print("CONCATENATION EXAMPLES FOR SHORT FRAGMENTS")
print("="*80 + "\n")

for i, frag in enumerate(short_frags, 1):
    speaker_id, ref_files, ref_duration = clusterer.select_reference_for_segment(
        {'start': frag['start'], 'end': frag['end']},
        speaker_clusters,
        fragments_dir,
        min_duration=5.0,
        target_duration=10.0
    )

    print(f"Example {i}:")
    print(f"  Original fragment: {frag['file']}")
    print(f"  Time: {frag['start']:.1f}s - {frag['end']:.1f}s")
    print(f"  Duration: {frag['duration']:.1f}s (too short!)")
    print(f"  Speaker: {speaker_id}")
    print(f"  Reference strategy: Concatenate {len(ref_files)} fragments → {ref_duration:.1f}s")
    print(f"\n  Selected fragments for reference:")
    
    for j, ref_file in enumerate(ref_files, 1):
        ref_frag = next((f for f in fragments_with_duration if f['file'] == ref_file), None)
        if ref_frag:
            is_self = " ⭐ (itself)" if ref_file == frag['file'] else ""
            print(f"    {j}. {ref_file}{is_self}")
            print(f"       Time: {ref_frag['start']:.1f}s - {ref_frag['end']:.1f}s ({ref_frag['duration']:.1f}s)")
    
    print()

print("="*80)
