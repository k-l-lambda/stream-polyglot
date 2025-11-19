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
import subprocess
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from tqdm import tqdm

# Import audio timeline segmentation
from audio_timeline import segment_with_timeline

# Import SRT utilities
from srt_utils import generate_srt_content, save_srt_file


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


def extract_audio(video_path, output_audio_path):
    """Extract audio from video file using FFmpeg"""
    try:
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vn',  # No video
            '-acodec', 'pcm_s16le',  # PCM 16-bit little-endian
            '-ar', '16000',  # Sample rate 16kHz (required by m4t)
            '-ac', '1',  # Mono
            '-y',  # Overwrite output file
            output_audio_path
        ]

        print_info(f"Extracting audio from video...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print_error(f"FFmpeg error: {result.stderr}")
            return False

        print_success(f"Audio extracted to: {output_audio_path}")
        return True
    except FileNotFoundError:
        print_error("FFmpeg not found. Please install FFmpeg.")
        return False
    except Exception as e:
        print_error(f"Error extracting audio: {e}")
        return False


def speech_to_text_translation(audio_path, source_lang, target_lang, api_url, verbose=True):
    """Call m4t API for speech-to-text translation"""
    try:
        if verbose:
            print_info(f"Translating speech from {source_lang} to {target_lang}...")

        # Read audio file
        with open(audio_path, 'rb') as f:
            audio_data = f.read()

        # Prepare multipart form data
        files = {
            'audio': ('audio.wav', audio_data, 'audio/wav')
        }
        data = {
            'source_lang': source_lang,
            'target_lang': target_lang
        }

        # Call m4t S2TT API
        response = requests.post(
            f"{api_url}/v1/speech-to-text-translation",
            files=files,
            data=data,
            timeout=300  # 5 minutes timeout for long audio
        )

        if response.status_code == 200:
            result = response.json()
            return result
        else:
            print_error(f"API error: {response.status_code}")
            print_error(f"Response: {response.text}")
            return None

    except requests.exceptions.Timeout:
        print_error("Request timeout. Audio file might be too long.")
        return None
    except Exception as e:
        print_error(f"Error calling m4t API: {e}")
        return None


def speech_to_speech_translation(audio_path, source_lang, target_lang, api_url, speaker_id=0):
    """Call m4t API for speech-to-speech translation"""
    try:
        print_info(f"Translating speech from {source_lang} to {target_lang}...")
        if speaker_id != 0:
            print_info(f"Using speaker voice ID: {speaker_id}")

        # Read audio file
        with open(audio_path, 'rb') as f:
            audio_data = f.read()

        # Prepare multipart form data
        files = {
            'audio': ('audio.wav', audio_data, 'audio/wav')
        }
        data = {
            'source_lang': source_lang,
            'target_lang': target_lang,
            'response_format': 'json',  # Get JSON with base64 audio
            'speaker_id': speaker_id
        }

        # Call m4t S2ST API
        response = requests.post(
            f"{api_url}/v1/speech-to-speech-translation",
            files=files,
            data=data,
            timeout=300  # 5 minutes timeout for long audio
        )

        if response.status_code == 200:
            result = response.json()
            return result
        else:
            print_error(f"API error: {response.status_code}")
            print_error(f"Response: {response.text}")
            return None

    except requests.exceptions.Timeout:
        print_error("Request timeout. Audio file might be too long.")
        return None
    except Exception as e:
        print_error(f"Error calling m4t S2ST API: {e}")
        return None


def save_audio_to_file(audio_data, sample_rate, output_path):
    """Save audio array to WAV file"""
    try:
        import numpy as np
        import soundfile as sf

        # Convert list to numpy array
        audio_array = np.array(audio_data, dtype=np.float32)

        # Save to WAV file
        sf.write(output_path, audio_array, sample_rate)
        print_success(f"Audio saved to: {output_path}")
        return True

    except ImportError as e:
        print_error(f"Missing required library: {e}")
        print_info("Please install: pip install numpy soundfile")
        return False
    except Exception as e:
        print_error(f"Error saving audio file: {e}")
        return False


def save_base64_audio_to_file(audio_base64, output_path):
    """Decode base64 audio and save to WAV file"""
    try:
        import base64

        # Decode base64 audio
        audio_bytes = base64.b64decode(audio_base64)

        # Write to file
        with open(output_path, 'wb') as f:
            f.write(audio_bytes)

        print_success(f"Audio saved to: {output_path}")
        return True

    except Exception as e:
        print_error(f"Error saving audio file: {e}")
        return False


def process_video(input_file, source_lang, target_lang, generate_audio, generate_subtitle, subtitle_source_lang, output_dir, api_url, speaker_id=0):
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

    # Process subtitle generation with timeline
    if generate_subtitle:
        print_header("Subtitle Generation with Timeline")

        print_info(f"Audio language: {source_lang}")
        print_info(f"Subtitle language: {target_lang}")

        # Create temporary directories
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_audio_path = os.path.join(temp_dir, 'extracted_audio.wav')
            fragments_dir = os.path.join(temp_dir, 'fragments')

            try:
                # Step 1: Extract audio from video
                print_info("Step 1/4: Extracting audio from video...")
                if not extract_audio(input_file, tmp_audio_path):
                    return 1

                # Step 2: Segment audio with timeline
                print_info("Step 2/4: Segmenting audio with VAD-based timeline...")
                timeline, metadata = segment_with_timeline(
                    audio_path=tmp_audio_path,
                    output_dir=fragments_dir,
                    chunk_duration=30.0,
                    m4t_api_url=api_url,
                    save_timeline=False
                )

                fragment_count = len(timeline)
                total_duration = metadata.get('total_duration', 0)
                print_success(f"Segmented into {fragment_count} speech fragments")
                print_info(f"Total audio duration: {total_duration:.2f}s")

                # Step 3: Translate each fragment
                print_info(f"Step 3/4: Translating {fragment_count} fragments...")
                subtitles = []
                source_subtitles = []

                # Use tqdm progress bar
                with tqdm(total=fragment_count, desc="Translating", unit="fragment",
                         bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                         ncols=80) as pbar:
                    for i, fragment in enumerate(timeline):
                        fragment_path = os.path.join(fragments_dir, fragment['file'])

                        # If subtitle_source_lang is set, transcribe source language first
                        if subtitle_source_lang:
                            try:
                                with open(fragment_path, 'rb') as f:
                                    audio_data = f.read()

                                files = {'audio': ('audio.wav', audio_data, 'audio/wav')}
                                data = {'language': source_lang}

                                response = requests.post(
                                    f"{api_url}/v1/transcribe",
                                    files=files,
                                    data=data,
                                    timeout=60
                                )

                                if response.status_code == 200:
                                    asr_result = response.json()
                                    source_text = asr_result.get('output_text', '').strip()
                                    if source_text:
                                        source_subtitles.append({
                                            'start': fragment['start'],
                                            'end': fragment['end'],
                                            'text': source_text
                                        })
                            except Exception as e:
                                tqdm.write(f"{Colors.RED}✗ Fragment {i}: Source transcription failed: {e}{Colors.END}")

                        # Translate fragment to target language
                        result = speech_to_text_translation(fragment_path, source_lang, target_lang, api_url, verbose=False)

                        if result and result.get('output_text'):
                            translated_text = result['output_text'].strip()
                            if translated_text:
                                subtitles.append({
                                    'start': fragment['start'],
                                    'end': fragment['end'],
                                    'text': translated_text
                                })
                        else:
                            tqdm.write(f"{Colors.YELLOW}⚠ Fragment {i}: Translation failed, skipping{Colors.END}")

                        # Update progress bar
                        pbar.update(1)

                # Step 4: Generate and save SRT files
                print_info(f"Step 4/4: Generating SRT subtitle files...")

                if not subtitles:
                    print_error("No subtitles generated")
                    return 1

                # Ensure output directory exists
                os.makedirs(output_dir, exist_ok=True)

                # Generate output filename
                input_path = Path(input_file)
                output_srt_filename = f"{input_path.stem}.{target_lang}.srt"
                output_srt_path = Path(output_dir) / output_srt_filename

                # Generate and save target language SRT
                srt_content = generate_srt_content(subtitles, merge_short=True)
                if save_srt_file(srt_content, str(output_srt_path)):
                    print_success(f"Target language subtitle saved: {output_srt_path}")
                else:
                    print_error("Failed to save target language subtitle")
                    return 1

                # Generate source language SRT if requested
                if subtitle_source_lang and source_subtitles:
                    source_srt_filename = f"{input_path.stem}.{source_lang}.srt"
                    source_srt_path = Path(output_dir) / source_srt_filename

                    source_srt_content = generate_srt_content(source_subtitles, merge_short=True)
                    if save_srt_file(source_srt_content, str(source_srt_path)):
                        print_success(f"Source language subtitle saved: {source_srt_path}")

                # Print summary
                print_header("Subtitle Generation Result")
                print_success(f"Generated {len(subtitles)} subtitle entries")
                print_info(f"Target language SRT: {output_srt_path}")
                if subtitle_source_lang and source_subtitles:
                    print_info(f"Source language SRT: {source_srt_path}")
                    print_info(f"Source entries: {len(source_subtitles)}")

            except Exception as e:
                print_error(f"Error during subtitle generation: {e}")
                import traceback
                traceback.print_exc()
                return 1

    # Process audio dubbing
    if generate_audio:
        print_header("Audio Dubbing Generation")

        print_info(f"Source language: {source_lang}")
        print_info(f"Target language: {target_lang}")

        # Create temporary audio file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_audio:
            tmp_audio_path = tmp_audio.name

        try:
            # Step 1: Extract audio from video
            print_info("Step 1/2: Extracting audio from video...")
            if not extract_audio(input_file, tmp_audio_path):
                return 1

            # Step 2: Try Speech-to-speech translation first (more efficient)
            print_info("Step 2/2: Translating speech to speech...")
            s2st_result = speech_to_speech_translation(tmp_audio_path, source_lang, target_lang, api_url, speaker_id)

            if s2st_result and s2st_result.get('output_audio_base64'):
                # S2ST succeeded
                translated_text = s2st_result.get('output_text', '')
                print_success(f"Speech translation completed!")
                if translated_text:
                    print_info(f"Translated text: {translated_text[:100]}{'...' if len(translated_text) > 100 else ''}")

                # Get audio data from result
                audio_base64 = s2st_result['output_audio_base64']

                # Generate output filename
                input_path = Path(input_file)
                output_filename = f"{input_path.stem}.{target_lang}.wav"
                output_path = Path(output_dir) / output_filename

                # Save base64 audio to file
                print_info(f"Saving audio to: {output_path}")
                if not save_base64_audio_to_file(audio_base64, str(output_path)):
                    return 1

                # Get file size for result display
                file_size = os.path.getsize(output_path) / 1024  # KB

                # Print result summary
                print_header("Audio Dubbing Result")
                print_success("Audio dubbing completed!")
                print_info(f"Output file: {output_path}")
                print_info(f"File size: {file_size:.1f} KB")
                print_info(f"Sample rate: {s2st_result.get('output_sample_rate', 16000)} Hz")
            else:
                # S2ST failed, fallback to S2TT + TTS
                print_warning("Direct S2ST failed, falling back to S2TT + TTS approach...")

                # Get translated text first
                s2tt_result = speech_to_text_translation(tmp_audio_path, source_lang, target_lang, api_url)

                if s2tt_result is None:
                    print_error("Failed to translate speech to text")
                    return 1

                translated_text = s2tt_result.get('output_text', '')
                if not translated_text:
                    print_error("No translated text received")
                    return 1

                print_success(f"Translation completed: {translated_text[:100]}{'...' if len(translated_text) > 100 else ''}")

                # Now generate speech from translated text
                print_info("Generating speech from translated text...")
                import requests as req_lib

                try:
                    tts_response = req_lib.post(
                        f"{api_url}/v1/text-to-speech",
                        json={'text': translated_text, 'source_lang': target_lang},
                        timeout=300
                    )

                    if tts_response.status_code == 200:
                        tts_result = tts_response.json()
                        output_audio = tts_result.get('output_audio', [])
                        sample_rate = tts_result.get('output_sample_rate', 16000)

                        if output_audio:
                            # Generate output filename
                            input_path = Path(input_file)
                            output_filename = f"{input_path.stem}.{target_lang}.wav"
                            output_path = Path(output_dir) / output_filename

                            # Save audio file
                            print_info(f"Saving audio to: {output_path}")
                            if not save_audio_to_file(output_audio, sample_rate, str(output_path)):
                                return 1

                            # Print result summary
                            print_header("Audio Dubbing Result")
                            print_success("Audio dubbing completed!")
                            print_info(f"Output file: {output_path}")
                            print_info(f"Sample rate: {sample_rate} Hz")
                            print_info(f"Duration: ~{len(output_audio) / sample_rate:.2f} seconds")
                        else:
                            print_error("No audio data received from TTS")
                            return 1
                    else:
                        print_error(f"TTS API error: {tts_response.status_code}")
                        return 1
                except Exception as e:
                    print_error(f"TTS generation failed: {e}")
                    return 1

        finally:
            # Clean up temporary audio file
            if os.path.exists(tmp_audio_path):
                os.unlink(tmp_audio_path)
                print_info(f"Cleaned up temporary audio file")

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
        action='store_true',
        help='Source language for subtitle generation (default: same as --lang source language)'
    )

    # Optional speaker ID for audio generation
    parser.add_argument(
        '--speaker-id',
        type=int,
        default=0,
        metavar='ID',
        help='Speaker voice ID for audio generation (0-199, default: 0)'
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
            args.api_url,
            args.speaker_id
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
