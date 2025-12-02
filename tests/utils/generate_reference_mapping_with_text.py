#!/usr/bin/env python3
"""Generate complete segment-to-reference mapping file with speech text"""

import sys
import json
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from speaker_clustering import SpeakerClusterer

# Setup paths
cache_dir = Path.home() / "work/stream-polyglot/assets/.stream-polyglot-cache/066. 移民第五季 第十三集"
fragments_dir = cache_dir / "fragments"
timeline_file = cache_dir / "timeline.json"
output_file = cache_dir / "speaker_reference_mapping.txt"

# m4t API settings
M4T_API_URL = "http://localhost:8000"
SOURCE_LANG = "cmn"  # Chinese

def transcribe_fragment(fragment_path, language):
    """Transcribe a fragment using m4t API"""
    try:
        with open(fragment_path, 'rb') as f:
            audio_data = f.read()
        
        files = {'audio': ('audio.wav', audio_data, 'audio/wav')}
        data = {'language': language}
        
        response = requests.post(
            f"{M4T_API_URL}/v1/transcribe",
            files=files,
            data=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get('output_text', '').strip()
        else:
            return None
    except Exception as e:
        print(f"  Warning: Transcription failed: {e}")
        return None

print(f"Loading timeline from {timeline_file}...")

# Load timeline
with open(timeline_file, 'r') as f:
    cache_data = json.load(f)
    timeline = cache_data.get('timeline', [])

print(f"Loaded {len(timeline)} fragments")

# Add duration
fragments_with_duration = []
for frag in timeline:
    frag_copy = frag.copy()
    frag_copy['duration'] = frag['end'] - frag['start']
    fragments_with_duration.append(frag_copy)

print("Initializing speaker clusterer...")

# Initialize clusterer
clusterer = SpeakerClusterer(method='resemblyzer', threshold=0.65)

print("Performing clustering...")
speaker_clusters = clusterer.cluster_fragments(fragments_dir, timeline)

print(f"Detected {len(speaker_clusters)} speakers")
print(f"Generating reference mapping with speech text for all {len(timeline)} fragments...")
print("This will take longer as we transcribe each reference fragment...\n")

# Generate mapping for all fragments
output_lines = []
output_lines.append("="*100)
output_lines.append("SPEAKER REFERENCE AUDIO MAPPING WITH SPEECH TEXT")
output_lines.append("="*100)
output_lines.append("")
output_lines.append(f"Total fragments: {len(timeline)}")
output_lines.append(f"Total speakers: {len(speaker_clusters)}")
output_lines.append("")
output_lines.append("Dynamic Reference Strategy:")
output_lines.append("  - Segments >= 10s: Use itself as reference")
output_lines.append("  - Segments 5-10s: Use itself as reference")
output_lines.append("  - Segments < 5s: Concatenate nearby fragments from same speaker to reach 5-10s")
output_lines.append("")
output_lines.append("="*100)
output_lines.append("")

# Statistics
strategy_counts = {'self_long': 0, 'self_medium': 0, 'concat': 0, 'self_short': 0}
ref_durations = []
failed_count = 0

# Cache for transcribed texts to avoid re-transcribing same fragments
transcription_cache = {}

for i, frag in enumerate(fragments_with_duration):
    if (i + 1) % 20 == 0:
        print(f"Progress: {i+1}/{len(timeline)} fragments processed...")
    
    speaker_id, ref_files, ref_duration = clusterer.select_reference_for_segment(
        {'start': frag['start'], 'end': frag['end']},
        speaker_clusters,
        fragments_dir,
        min_duration=5.0,
        target_duration=10.0
    )
    
    if not speaker_id:
        failed_count += 1
        continue
    
    # Determine strategy
    if frag['duration'] >= 10.0:
        strategy = "Use itself"
        strategy_counts['self_long'] += 1
    elif frag['duration'] >= 5.0:
        strategy = "Use itself"
        strategy_counts['self_medium'] += 1
    elif len(ref_files) > 1:
        strategy = f"Concat {len(ref_files)} fragments"
        strategy_counts['concat'] += 1
    else:
        strategy = "Use itself (no nearby)"
        strategy_counts['self_short'] += 1
    
    ref_durations.append(ref_duration)
    
    # Format output
    output_lines.append(f"[{i+1}/{len(timeline)}] Segment: {frag['file']}")
    output_lines.append(f"  Time: {frag['start']:.1f}s - {frag['end']:.1f}s (duration: {frag['duration']:.1f}s)")
    output_lines.append(f"  Speaker: {speaker_id}")
    output_lines.append(f"  Strategy: {strategy}")
    output_lines.append(f"  Reference duration: {ref_duration:.1f}s")
    output_lines.append(f"  Reference files ({len(ref_files)} files):")
    
    # Transcribe reference fragments
    ref_texts = []
    for j, ref_file in enumerate(ref_files, 1):
        ref_frag = next((f for f in fragments_with_duration if f['file'] == ref_file), None)
        if ref_frag:
            is_self = " ⭐" if ref_file == frag['file'] else ""
            
            # Get or cache transcription
            if ref_file not in transcription_cache:
                ref_path = fragments_dir / ref_file
                text = transcribe_fragment(ref_path, SOURCE_LANG)
                transcription_cache[ref_file] = text if text else "[transcription failed]"
            
            ref_text = transcription_cache[ref_file]
            ref_texts.append(ref_text)
            
            output_lines.append(f"    {j}. {ref_file}{is_self}")
            output_lines.append(f"       Time: {ref_frag['start']:.1f}s - {ref_frag['end']:.1f}s ({ref_frag['duration']:.1f}s)")
            output_lines.append(f"       Text: {ref_text}")
    
    # Combined reference text
    combined_text = " ".join(ref_texts)
    output_lines.append(f"  Combined reference text: {combined_text}")
    output_lines.append("")

# Summary
output_lines.append("="*100)
output_lines.append("SUMMARY")
output_lines.append("="*100)
output_lines.append("")
output_lines.append(f"Total segments processed: {len(timeline) - failed_count}")
output_lines.append(f"Failed to match: {failed_count}")
output_lines.append(f"Unique fragments transcribed: {len(transcription_cache)}")
output_lines.append("")
output_lines.append("Strategy Distribution:")
output_lines.append(f"  Long segments (>=10s) using itself: {strategy_counts['self_long']}")
output_lines.append(f"  Medium segments (5-10s) using itself: {strategy_counts['self_medium']}")
output_lines.append(f"  Short segments (<5s) concatenating: {strategy_counts['concat']}")
output_lines.append(f"  Short segments (<5s) using itself: {strategy_counts['self_short']}")
output_lines.append("")

if ref_durations:
    avg_ref = sum(ref_durations) / len(ref_durations)
    min_ref = min(ref_durations)
    max_ref = max(ref_durations)
    
    output_lines.append("Reference Audio Duration Statistics:")
    output_lines.append(f"  Average: {avg_ref:.1f}s")
    output_lines.append(f"  Minimum: {min_ref:.1f}s")
    output_lines.append(f"  Maximum: {max_ref:.1f}s")
    output_lines.append("")
    
    # Duration distribution
    below_5 = sum(1 for d in ref_durations if d < 5.0)
    range_5_10 = sum(1 for d in ref_durations if 5.0 <= d < 10.0)
    range_10_15 = sum(1 for d in ref_durations if 10.0 <= d < 15.0)
    above_15 = sum(1 for d in ref_durations if d >= 15.0)
    
    output_lines.append("Reference Duration Distribution:")
    output_lines.append(f"  < 5s: {below_5} ({below_5*100/len(ref_durations):.1f}%)")
    output_lines.append(f"  5-10s: {range_5_10} ({range_5_10*100/len(ref_durations):.1f}%)")
    output_lines.append(f"  10-15s: {range_10_15} ({range_10_15*100/len(ref_durations):.1f}%)")
    output_lines.append(f"  >= 15s: {above_15} ({above_15*100/len(ref_durations):.1f}%)")

output_lines.append("")
output_lines.append("="*100)

# Write to file
print(f"\nWriting to {output_file}...")
with open(output_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(output_lines))

print(f"✓ Complete! Mapping with speech text saved to: {output_file}")
print(f"  File size: {output_file.stat().st_size / 1024:.1f} KB")
print(f"  Transcribed {len(transcription_cache)} unique fragments")
