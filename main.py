#!/usr/bin/env python3
"""
Stream-Polyglot CLI
Multilingual video/audio translation and subtitle generation tool

Usage:
    python -m main video.mp4 --lang eng:cmn --audio --subtitle [--output path/to/out/]
"""

import argparse
import sys
import os
import requests
from pathlib import Path
from dotenv import load_dotenv


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Print colored header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{text}{Colors.END}")


def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.END}", file=sys.stderr)


def print_info(text):
    """Print info message"""
    print(f"{Colors.CYAN}ℹ {text}{Colors.END}")


def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def check_file_exists(file_path):
    """Check if input file exists"""
    path = Path(file_path)
    if not path.exists():
        print_error(f"File not found: {file_path}")
        return False
    if not path.is_file():
        print_error(f"Not a file: {file_path}")
        return False
    return True


def check_m4t_server(api_url):
    """Check if m4t API server is accessible"""
    try:
        response = requests.get(f"{api_url}/health", timeout=5)
        if response.status_code == 200:
            print_success(f"m4t API server is accessible at {api_url}")
            return True
        else:
            print_error(f"m4t API server returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_error(f"Cannot connect to m4t API server at {api_url}")
        print_info("Make sure the m4t server is running (cd ~/work/m4t && ./start_dev.sh)")
        return False
    except requests.exceptions.Timeout:
        print_error(f"Connection timeout to m4t API server at {api_url}")
        return False
    except Exception as e:
        print_error(f"Error connecting to m4t API server: {e}")
        return False


def parse_language_pair(lang_pair):
    """Parse language pair string like 'eng:cmn' into (source, target)"""
    if ':' not in lang_pair:
        print_error(f"Invalid language pair format: '{lang_pair}'")
        print_info("Expected format: 'source:target' (e.g., 'eng:cmn', 'jpn:eng')")
        return None, None

    parts = lang_pair.split(':')
    if len(parts) != 2:
        print_error(f"Invalid language pair format: '{lang_pair}'")
        print_info("Expected format: 'source:target' (e.g., 'eng:cmn', 'jpn:eng')")
        return None, None

    source_lang, target_lang = parts[0].strip(), parts[1].strip()

    if not source_lang or not target_lang:
        print_error(f"Invalid language pair format: '{lang_pair}'")
        print_info("Both source and target languages must be specified")
        return None, None

    return source_lang, target_lang


def get_video_info(video_path):
    """Get basic video file information"""
    path = Path(video_path)
    size_mb = path.stat().st_size / (1024 * 1024)

    print_header("Video File Information")
    print_info(f"File: {path.name}")
    print_info(f"Path: {path.absolute()}")
    print_info(f"Size: {size_mb:.2f} MB")
    print_info(f"Extension: {path.suffix}")


def process_video(input_file, source_lang, target_lang, generate_audio, generate_subtitle, subtitle_source_lang, output_dir, api_url):
    """Process video file for translation"""

    print_header("Stream-Polyglot Video Translation")

    # Check input file
    if not check_file_exists(input_file):
        return 1

    # Show video info
    get_video_info(input_file)

    # Check m4t server
    if not check_m4t_server(api_url):
        return 1

    # Determine output settings
    print_header("Translation Configuration")
    print_info(f"Source language: {source_lang}")
    print_info(f"Target language: {target_lang}")
    if subtitle_source_lang:
        print_info(f"Subtitle source language: {subtitle_source_lang}")
    print_info(f"Generate subtitles: {'Yes' if generate_subtitle else 'No'}")
    print_info(f"Generate audio dubbing: {'Yes' if generate_audio else 'No'}")

    if output_dir:
        print_info(f"Output directory: {output_dir}")
    else:
        # Default output same directory as input
        input_path = Path(input_file)
        output_dir = input_path.parent
        print_info(f"Output directory: {output_dir} (default)")

    # Check if at least one output is requested
    if not generate_audio and not generate_subtitle:
        print_warning("Neither --audio nor --subtitle specified")
        print_info("Nothing to generate. Please specify at least one output option:")
        print_info("  --subtitle    Generate subtitle file")
        print_info("  --audio       Generate audio dubbing")
        return 1

    print_header("Processing Pipeline")
    if generate_subtitle:
        print_info("Step 1: Extract audio from video (FFmpeg)")
        print_info("Step 2: Translate speech to text (m4t S2TT)")
        print_info("Step 3: Generate subtitle file (.srt)")

    if generate_audio:
        print_info("Step 1: Extract audio from video (FFmpeg)")
        print_info("Step 2: Translate speech to text (m4t S2TT)")
        print_info("Step 3: Generate translated speech (m4t TTS)")
        print_info("Step 4: Replace audio track in video")

    print_error("\n⚠ Translation pipeline not yet implemented")
    print_info("This CLI interface is ready - implementation coming in v0.1.0")
    print_info("\nFor now, you can test the m4t API directly:")
    print_info(f"  curl -X POST '{api_url}/v1/text-to-text-translation' \\")
    print_info(f"    -H 'Content-Type: application/json' \\")
    print_info(f"    -d '{{\"text\": \"Hello\", \"source_lang\": \"{source_lang}\", \"target_lang\": \"{target_lang}\"}}'")

    return 0


def main():
    """Main CLI entry point"""
    # Load environment variables from .env file
    load_dotenv()

    # Get API URL from environment variable or use default
    default_api_url = os.getenv('M4T_API_URL', 'http://localhost:8000')

    parser = argparse.ArgumentParser(
        prog='python -m main',
        description='Stream-Polyglot: Multilingual video/audio translation and subtitle generation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate Chinese subtitles for English video
  python -m main video.mp4 --lang eng:cmn --subtitle

  # Generate Japanese audio dubbing for English video
  python -m main video.mp4 --lang eng:jpn --audio

  # Generate both subtitles and audio dubbing
  python -m main video.mp4 --lang eng:cmn --subtitle --audio

  # Specify output directory
  python -m main video.mp4 --lang jpn:eng --subtitle --output ./translated/

  # Use custom API server
  python -m main video.mp4 --lang eng:cmn --subtitle --api-url http://192.168.1.100:8000

Common language codes:
  eng - English      jpn - Japanese     cmn - Chinese (Simplified)
  kor - Korean       fra - French       deu - German
  spa - Spanish      rus - Russian      arb - Arabic

Environment Variables:
  M4T_API_URL    m4t API server URL (default: http://localhost:8000)

See http://localhost:8000/languages for full list of supported languages.
        """
    )

    # Positional argument for input video
    parser.add_argument(
        'input',
        help='Input video or audio file path'
    )

    # Language pair argument
    parser.add_argument(
        '--lang',
        required=True,
        metavar='SOURCE:TARGET',
        help='Language pair in format source:target (e.g., eng:cmn, jpn:eng)'
    )

    # Output type flags
    parser.add_argument(
        '--subtitle',
        action='store_true',
        help='Generate subtitle file (.srt)'
    )

    parser.add_argument(
        '--audio',
        action='store_true',
        help='Generate audio dubbing (replace audio track with translated speech)'
    )

    # Optional subtitle source language
    parser.add_argument(
        '--subtitle-source-lang',
        metavar='LANG',
        help='Source language for subtitle generation (default: same as --lang source language)'
    )

    # Optional output directory
    parser.add_argument(
        '--output',
        metavar='DIR',
        help='Output directory for generated files (default: same as input file directory)'
    )

    # API URL (with env var default)
    parser.add_argument(
        '--api-url',
        default=default_api_url,
        metavar='URL',
        help=f'm4t API server URL (default from env: {default_api_url})'
    )

    args = parser.parse_args()

    # Parse language pair
    source_lang, target_lang = parse_language_pair(args.lang)
    if not source_lang or not target_lang:
        return 1

    # Process video
    try:
        return process_video(
            args.input,
            source_lang,
            target_lang,
            args.audio,
            args.subtitle,
            args.subtitle_source_lang,
            args.output,
            args.api_url
        )
    except KeyboardInterrupt:
        print_error("\n\nInterrupted by user")
        return 130
    except Exception as e:
        print_error(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
