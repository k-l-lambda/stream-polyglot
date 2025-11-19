#!/usr/bin/env python3
"""
Generate audio samples for all speaker IDs in SeamlessM4T

This script generates TTS audio for all 200 speaker voices (IDs 0-199)
using a specific text and language, allowing you to compare and select
your preferred voice.

Usage:
    python generate_all_speakers.py [options]

Examples:
    # Generate English speech samples
    python generate_all_speakers.py --lang eng --text "Hello, how are you?"

    # Generate Chinese samples
    python generate_all_speakers.py --lang cmn --text "你好，今天天气怎么样？"

    # Generate Japanese samples with custom output directory
    python generate_all_speakers.py --lang jpn --text "こんにちは、元気ですか？" --output ./speaker_samples
"""

import argparse
import os
import sys
import time
from pathlib import Path
import requests
import numpy as np
import soundfile as sf
from typing import Optional

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Print formatted header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{text}{Colors.END}")


def print_info(text):
    """Print info message"""
    print(f"{Colors.CYAN}ℹ {text}{Colors.END}")


def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def check_m4t_server(api_url: str) -> bool:
    """Check if m4t server is running"""
    try:
        response = requests.get(f"{api_url}/health", timeout=5)
        if response.status_code == 200:
            return True
        else:
            print_error(f"m4t server unhealthy: {response.status_code}")
            return False
    except requests.RequestException as e:
        print_error(f"Cannot connect to m4t server at {api_url}")
        print_error(f"Error: {e}")
        print_info("Make sure the m4t server is running:")
        print_info("  cd /home/camus/work/m4t")
        print_info("  ./env/bin/python server.py")
        return False


def generate_speaker_audio(
    text: str,
    language: str,
    speaker_id: int,
    api_url: str,
    output_dir: str,
    verbose: bool = False
) -> Optional[str]:
    """
    Generate audio for a specific speaker ID

    Args:
        text: Text to synthesize
        language: Language code (e.g., 'eng', 'cmn', 'jpn')
        speaker_id: Speaker voice ID (0-199)
        api_url: m4t API URL
        output_dir: Output directory for audio files
        verbose: Print detailed progress

    Returns:
        Path to generated audio file, or None if failed
    """
    try:
        # Call TTS API
        response = requests.post(
            f"{api_url}/v1/text-to-speech",
            json={
                "text": text,
                "source_lang": language,
                "speaker_id": speaker_id
            },
            timeout=60
        )

        if response.status_code != 200:
            if verbose:
                print_error(f"Speaker {speaker_id}: API error {response.status_code}")
            return None

        result = response.json()

        # Save audio file
        audio_array = np.array(result['output_audio'], dtype=np.float32)
        sample_rate = result['output_sample_rate']

        # Create filename: speaker_<id>_<lang>.wav
        filename = f"speaker_{speaker_id:03d}_{language}.wav"
        filepath = os.path.join(output_dir, filename)

        sf.write(filepath, audio_array, sample_rate)

        if verbose:
            duration = len(audio_array) / sample_rate
            print_success(f"Speaker {speaker_id:3d}: {filepath} ({duration:.2f}s)")

        return filepath

    except Exception as e:
        if verbose:
            print_error(f"Speaker {speaker_id}: {e}")
        return None


def generate_all_speakers(
    text: str,
    language: str,
    output_dir: str,
    api_url: str = "http://localhost:8000",
    start_id: int = 0,
    end_id: int = 199,
    batch_size: int = 10
):
    """
    Generate audio samples for all speaker IDs

    Args:
        text: Text to synthesize
        language: Language code
        output_dir: Output directory
        api_url: m4t API URL
        start_id: Starting speaker ID (default: 0)
        end_id: Ending speaker ID (default: 199)
        batch_size: Progress update frequency
    """
    print_header("SeamlessM4T Speaker Voice Generator")

    print_info(f"Text: {text}")
    print_info(f"Language: {language}")
    print_info(f"Speaker ID range: {start_id}-{end_id}")
    print_info(f"Output directory: {output_dir}")
    print_info(f"API URL: {api_url}")

    # Check m4t server
    print_info("\nChecking m4t server...")
    if not check_m4t_server(api_url):
        return 1
    print_success("m4t server is healthy")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    print_success(f"Output directory ready: {output_dir}")

    # Generate audio for each speaker
    print_header(f"\nGenerating Audio Samples ({end_id - start_id + 1} speakers)")

    success_count = 0
    failed_count = 0
    start_time = time.time()

    for speaker_id in range(start_id, end_id + 1):
        # Show progress
        if speaker_id % batch_size == 0 or speaker_id == end_id:
            progress = ((speaker_id - start_id + 1) / (end_id - start_id + 1)) * 100
            elapsed = time.time() - start_time
            avg_time = elapsed / (speaker_id - start_id + 1) if speaker_id > start_id else 0
            remaining = avg_time * (end_id - speaker_id)

            print(f"\r{Colors.CYAN}Progress: {progress:5.1f}% ({speaker_id - start_id + 1}/{end_id - start_id + 1}) "
                  f"| Success: {success_count} | Failed: {failed_count} "
                  f"| ETA: {remaining:.0f}s{Colors.END}", end='', flush=True)

        # Generate audio
        result = generate_speaker_audio(
            text, language, speaker_id, api_url, output_dir, verbose=False
        )

        if result:
            success_count += 1
        else:
            failed_count += 1

    print()  # New line after progress bar

    # Summary
    total_time = time.time() - start_time
    print_header("\nGeneration Complete!")
    print_success(f"Successfully generated: {success_count} audio files")
    if failed_count > 0:
        print_warning(f"Failed: {failed_count} speakers")
    print_info(f"Total time: {total_time:.1f}s ({total_time / (end_id - start_id + 1):.2f}s per speaker)")
    print_info(f"Output directory: {output_dir}")

    # Generate index HTML for easy listening
    generate_index_html(text, language, output_dir, start_id, end_id)

    return 0


def generate_index_html(text: str, language: str, output_dir: str, start_id: int, end_id: int):
    """Generate an HTML index file for easy audio playback"""

    html_path = os.path.join(output_dir, "index.html")

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>SeamlessM4T Speaker Voices - {language}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #333;
            text-align: center;
        }}
        .info {{
            background-color: #e3f2fd;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }}
        .speaker-card {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .speaker-card h3 {{
            margin-top: 0;
            color: #1976d2;
        }}
        audio {{
            width: 100%;
            margin-top: 10px;
        }}
        .text {{
            font-style: italic;
            color: #666;
            margin-top: 10px;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <h1>SeamlessM4T Speaker Voices</h1>

    <div class="info">
        <strong>Language:</strong> {language}<br>
        <strong>Text:</strong> "{text}"<br>
        <strong>Total Speakers:</strong> {end_id - start_id + 1} (ID {start_id}-{end_id})
    </div>

    <div class="grid">
"""

    for speaker_id in range(start_id, end_id + 1):
        filename = f"speaker_{speaker_id:03d}_{language}.wav"
        filepath = os.path.join(output_dir, filename)

        if os.path.exists(filepath):
            html_content += f"""
        <div class="speaker-card">
            <h3>Speaker {speaker_id}</h3>
            <audio controls preload="none">
                <source src="{filename}" type="audio/wav">
                Your browser does not support audio playback.
            </audio>
        </div>
"""

    html_content += """
    </div>
</body>
</html>
"""

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print_success(f"Generated HTML index: {html_path}")
    print_info(f"Open in browser: file://{os.path.abspath(html_path)}")


def main():
    """Main entry point"""

    # Default API URL
    default_api_url = os.getenv('M4T_API_URL', 'http://localhost:8000')

    parser = argparse.ArgumentParser(
        description='Generate audio samples for all SeamlessM4T speaker voices',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate English samples
  python generate_all_speakers.py --lang eng --text "Hello, how are you?"

  # Generate Chinese samples
  python generate_all_speakers.py --lang cmn --text "你好，今天天气怎么样？"

  # Generate specific range of speakers
  python generate_all_speakers.py --lang jpn --text "こんにちは" --start 0 --end 50

  # Use custom API URL
  python generate_all_speakers.py --lang eng --text "Test" --api-url http://192.168.1.100:8000
        """
    )

    parser.add_argument(
        '--lang',
        required=True,
        metavar='LANG',
        help='Language code (e.g., eng, cmn, jpn, fra, spa)'
    )

    parser.add_argument(
        '--text',
        required=True,
        metavar='TEXT',
        help='Text to synthesize for all speakers'
    )

    parser.add_argument(
        '--output',
        default='./speaker_samples',
        metavar='DIR',
        help='Output directory for audio files (default: ./speaker_samples)'
    )

    parser.add_argument(
        '--start',
        type=int,
        default=0,
        metavar='ID',
        help='Starting speaker ID (default: 0)'
    )

    parser.add_argument(
        '--end',
        type=int,
        default=199,
        metavar='ID',
        help='Ending speaker ID (default: 199)'
    )

    parser.add_argument(
        '--api-url',
        default=default_api_url,
        metavar='URL',
        help=f'm4t API server URL (default: {default_api_url})'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        metavar='N',
        help='Progress update frequency (default: 10)'
    )

    args = parser.parse_args()

    # Validate speaker ID range
    if args.start < 0 or args.start > 199:
        print_error("Start speaker ID must be between 0 and 199")
        return 1

    if args.end < 0 or args.end > 199:
        print_error("End speaker ID must be between 0 and 199")
        return 1

    if args.start > args.end:
        print_error("Start speaker ID must be less than or equal to end speaker ID")
        return 1

    # Generate audio samples
    try:
        return generate_all_speakers(
            text=args.text,
            language=args.lang,
            output_dir=args.output,
            api_url=args.api_url,
            start_id=args.start,
            end_id=args.end,
            batch_size=args.batch_size
        )
    except KeyboardInterrupt:
        print_error("\n\nInterrupted by user")
        return 130
    except Exception as e:
        print_error(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
