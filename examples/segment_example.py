#!/usr/bin/env python3
"""
Example script demonstrating audio timeline segmentation

This script shows how to:
1. Segment a long audio file into speech fragments
2. Generate a timeline with timestamps
3. Save fragments to disk for further processing
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from audio_timeline import segment_with_timeline


def main():
    """Demonstrate audio segmentation with timeline"""

    # Example audio file (use any of the existing test audio)
    audio_file = "../assets/japanese_speech.wav"  # Short test file
    output_dir = "./segmented_output"
    chunk_duration = 30.0  # 30 seconds per chunk

    print("=" * 60)
    print("Audio Timeline Segmentation Example")
    print("=" * 60)
    print(f"\nInput audio: {audio_file}")
    print(f"Output directory: {output_dir}")
    print(f"Chunk duration: {chunk_duration}s")
    print(f"M4T API: http://localhost:8000")
    print("\nStarting segmentation...\n")

    # Segment the audio
    try:
        timeline, metadata = segment_with_timeline(
            audio_path=audio_file,
            output_dir=output_dir,
            chunk_duration=chunk_duration,
            m4t_api_url="http://localhost:8000",
            save_timeline=True
        )

        # Display results
        print("\n" + "=" * 60)
        print("Segmentation Complete!")
        print("=" * 60)
        print(f"\nTotal duration: {metadata['total_duration']:.2f}s")
        print(f"Fragments created: {metadata['fragment_count']}")
        print(f"Sample rate: {metadata['sample_rate']}Hz")

        print("\n--- Timeline ---")
        for frag in timeline:
            duration = frag['end'] - frag['start']
            print(f"  [{frag['id']:2d}] {frag['start']:7.2f}s - {frag['end']:7.2f}s "
                  f"({duration:5.2f}s)  {frag['file']}")

        print(f"\nOutput files:")
        print(f"  - Timeline: {output_dir}/timeline.json")
        print(f"  - Fragments: {output_dir}/fragment_*.wav")

        # Example: How to use fragments with translation
        print("\n--- Next Steps ---")
        print("You can now process each fragment individually:")
        print("\nFor example, to translate all fragments:")
        print(f"""
import json
from pathlib import Path

# Load timeline
with open("{output_dir}/timeline.json") as f:
    data = json.load(f)

# Process each fragment
for fragment in data['fragments']:
    audio_path = Path("{output_dir}") / fragment['file']
    start_time = fragment['start']
    end_time = fragment['end']

    # Your translation logic here
    translated_text = translate_audio(audio_path)

    # Store with timeline
    subtitles.append({{
        "start": start_time,
        "end": end_time,
        "text": translated_text
    }})
""")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure:")
        print("  1. M4T API server is running (python server.py in m4t directory)")
        print("  2. Audio file exists")
        print("  3. Dependencies are installed (pip install -r requirements.txt)")
        sys.exit(1)


if __name__ == "__main__":
    main()
