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
import threading
from pathlib import Path
from dotenv import load_dotenv
from tqdm import tqdm

# Import audio timeline segmentation
from audio_timeline import segment_with_timeline

# Import SRT utilities
from srt_utils import generate_srt_content, save_srt_file, parse_srt_file, extract_bilingual_text


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


def infer_language_from_srt_filename(srt_path):
    """
    Infer source and target language from SRT filename

    Expected format: xxx.source-target.srt (e.g., video.eng-cmn.srt)

    Returns:
        Tuple of (source_lang, target_lang) or (None, None) if not found
    """
    import re
    filename = Path(srt_path).stem

    # Pattern: filename.source-target (e.g., video.eng-cmn)
    # Match 2-3 letter language codes before .srt extension
    match = re.search(r'\.([a-z]{2,3})-([a-z]{2,3})$', filename)

    if match:
        source_lang = match.group(1)
        target_lang = match.group(2)
        return source_lang, target_lang

    return None, None


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


def speech_to_speech_translation(audio_path, source_lang, target_lang, api_url, speaker_id=0, verbose=True):
    """Call m4t API for speech-to-speech translation"""
    try:
        if verbose:
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


def audio_split(audio_path, api_url, verbose=True, max_chunk_duration=300.0):
    """
    Call m4t API for audio splitting (vocals + accompaniment)

    For long audio files, splits into chunks on client side to avoid network timeout.

    Args:
        audio_path: Path to audio file
        api_url: m4t API server URL
        verbose: Print info messages
        max_chunk_duration: Maximum chunk duration in seconds (default: 300s = 5 minutes)

    Returns:
        Tuple of (vocals_bytes, accompaniment_bytes, sample_rate) or (None, None, None) on error
    """
    try:
        import soundfile as sf

        # Load audio to check duration
        audio_array, sr = sf.read(audio_path, dtype='float32')
        total_duration = len(audio_array) / sr

        if verbose:
            print_info(f"Audio duration: {total_duration:.2f}s")

        # If audio is short enough, process directly
        if total_duration <= max_chunk_duration:
            return _audio_split_direct(audio_path, api_url, verbose)

        # For long audio, process in chunks
        if verbose:
            print_info(f"Audio exceeds {max_chunk_duration}s, processing in chunks...")

        return _audio_split_chunked(audio_array, sr, api_url, max_chunk_duration, verbose)

    except Exception as e:
        print_error(f"Error in audio split: {e}")
        return None, None, None


def _audio_split_direct(audio_path, api_url, verbose=True):
    """
    Direct audio split for short audio files (<= 5 minutes)
    """
    try:
        if verbose:
            print_info(f"Splitting audio into vocals and accompaniment...")

        # Read audio file
        with open(audio_path, 'rb') as f:
            audio_data = f.read()

        # Prepare multipart form data
        files = {
            'audio': ('audio.wav', audio_data, 'audio/wav')
        }

        # Call m4t audio-split API
        response = requests.post(
            f"{api_url}/v1/audio-split",
            files=files,
            timeout=300  # 5 minutes timeout
        )

        if response.status_code == 200:
            result = response.json()

            # Decode base64 audio streams
            import base64
            vocals_base64 = result.get('vocals_audio_base64', '')
            accompaniment_base64 = result.get('accompaniment_audio_base64', '')
            sample_rate = result.get('sample_rate', 16000)

            vocals_bytes = base64.b64decode(vocals_base64)
            accompaniment_bytes = base64.b64decode(accompaniment_base64)

            if verbose:
                print_success(f"Audio split completed (sample rate: {sample_rate} Hz)")

            return vocals_bytes, accompaniment_bytes, sample_rate
        else:
            print_error(f"Audio split API error: {response.status_code}")
            print_error(f"Response: {response.text}")
            return None, None, None

    except requests.exceptions.Timeout:
        print_error("Request timeout during audio split.")
        return None, None, None
    except Exception as e:
        print_error(f"Error calling audio-split API: {e}")
        return None, None, None


def _audio_split_chunked(audio_array, sr, api_url, chunk_duration, verbose=True):
    """
    Split long audio into chunks, process each chunk via API, then concatenate results

    Args:
        audio_array: Full audio array
        sr: Sample rate
        api_url: m4t API server URL
        chunk_duration: Duration of each chunk in seconds
        verbose: Print info messages

    Returns:
        Tuple of (vocals_bytes, accompaniment_bytes, sample_rate)
    """
    import soundfile as sf
    import base64
    import io
    import numpy as np

    total_duration = len(audio_array) / sr
    chunk_samples = int(chunk_duration * sr)
    num_chunks = int(np.ceil(total_duration / chunk_duration))

    if verbose:
        print_info(f"Processing {num_chunks} chunks of {chunk_duration}s each...")

    vocals_chunks = []
    accompaniment_chunks = []
    result_sr = 16000  # Default sample rate

    for i in range(num_chunks):
        start_sample = i * chunk_samples
        end_sample = min((i + 1) * chunk_samples, len(audio_array))
        chunk_array = audio_array[start_sample:end_sample]

        chunk_start_time = start_sample / sr
        chunk_end_time = end_sample / sr

        if verbose:
            print_info(f"Processing chunk {i+1}/{num_chunks}: {chunk_start_time:.1f}s - {chunk_end_time:.1f}s")

        # Save chunk to temporary WAV in memory
        chunk_buffer = io.BytesIO()
        sf.write(chunk_buffer, chunk_array, sr, format='WAV')
        chunk_buffer.seek(0)
        chunk_bytes = chunk_buffer.read()

        # Send chunk to API
        try:
            files = {
                'audio': (f'chunk_{i}.wav', chunk_bytes, 'audio/wav')
            }

            response = requests.post(
                f"{api_url}/v1/audio-split",
                files=files,
                timeout=300
            )

            if response.status_code != 200:
                print_error(f"Chunk {i+1}/{num_chunks} failed: {response.status_code}")
                return None, None, None

            result = response.json()
            result_sr = result.get('sample_rate', 16000)

            # Decode base64 audio streams
            vocals_base64 = result.get('vocals_audio_base64', '')
            accompaniment_base64 = result.get('accompaniment_audio_base64', '')

            vocals_chunk_bytes = base64.b64decode(vocals_base64)
            accompaniment_chunk_bytes = base64.b64decode(accompaniment_base64)

            # Load as arrays for concatenation
            vocals_chunk_array, _ = sf.read(io.BytesIO(vocals_chunk_bytes), dtype='float32')
            accompaniment_chunk_array, _ = sf.read(io.BytesIO(accompaniment_chunk_bytes), dtype='float32')

            vocals_chunks.append(vocals_chunk_array)
            accompaniment_chunks.append(accompaniment_chunk_array)

        except Exception as e:
            print_error(f"Error processing chunk {i+1}/{num_chunks}: {e}")
            return None, None, None

    # Concatenate all chunks
    if verbose:
        print_info("Concatenating processed chunks...")

    vocals_array = np.concatenate(vocals_chunks)
    accompaniment_array = np.concatenate(accompaniment_chunks)

    # Convert concatenated arrays back to bytes
    vocals_buffer = io.BytesIO()
    accompaniment_buffer = io.BytesIO()

    sf.write(vocals_buffer, vocals_array, result_sr, format='WAV')
    sf.write(accompaniment_buffer, accompaniment_array, result_sr, format='WAV')

    vocals_buffer.seek(0)
    accompaniment_buffer.seek(0)

    vocals_bytes = vocals_buffer.read()
    accompaniment_bytes = accompaniment_buffer.read()

    if verbose:
        print_success(f"Audio split completed: {len(vocals_array)/result_sr:.2f}s processed")

    return vocals_bytes, accompaniment_bytes, result_sr


def audio_split_background(audio_path, api_url, cache_dir):
    """
    Run audio splitting in background thread and save results when ready

    Args:
        audio_path: Path to audio file
        api_url: m4t API server URL
        cache_dir: Cache directory to save split audio
    """
    try:
        print_info("Starting audio split in background...")

        vocals_bytes, accompaniment_bytes, _ = audio_split(audio_path, api_url, verbose=False)

        if vocals_bytes and accompaniment_bytes:
            # Save vocals and accompaniment to cache directory
            split_cache_dir = cache_dir / 'split'
            os.makedirs(split_cache_dir, exist_ok=True)

            vocals_cache_path = split_cache_dir / 'vocals.wav'
            accompaniment_cache_path = split_cache_dir / 'accompaniment.wav'

            with open(vocals_cache_path, 'wb') as f:
                f.write(vocals_bytes)
            with open(accompaniment_cache_path, 'wb') as f:
                f.write(accompaniment_bytes)

            print_success(f"✓ Audio split completed")
            print_success(f"  Vocals: {vocals_cache_path}")
            print_success(f"  Accompaniment: {accompaniment_cache_path}")
        else:
            print_warning("Audio split failed in background")
    except Exception as e:
        print_error(f"Background audio split error: {e}")


def voice_clone_translation(ref_audio_path, text, text_language, prompt_text, prompt_language, api_url, seed=-1, verbose=True):
    """
    Call m4t API for voice cloning

    Args:
        ref_audio_path: Path to reference audio file
        text: Text to synthesize in target language
        text_language: Language code for text (SeamlessM4T or GPT-SoVITS code)
        prompt_text: Transcription of reference audio (source language)
        prompt_language: Language code for reference audio
        api_url: m4t API server URL
        seed: Random seed for reproducibility (-1 for random)
        verbose: Print info messages

    Returns:
        Audio bytes or None on error
    """
    try:
        if verbose:
            print_info(f"Voice cloning: {text_language} text with {prompt_language} reference...")

        # Read reference audio file
        with open(ref_audio_path, 'rb') as f:
            audio_data = f.read()

        # Prepare multipart form data
        files = {
            'audio': ('reference.wav', audio_data, 'audio/wav')
        }
        data = {
            'text': text,
            'text_language': text_language,
            'prompt_text': prompt_text,
            'prompt_language': prompt_language,
            'seed': str(seed)
        }

        # Call m4t voice-clone API
        response = requests.post(
            f"{api_url}/v1/voice-clone",
            files=files,
            data=data,
            timeout=120  # 2 minutes timeout
        )

        if response.status_code == 200:
            result = response.json()
            # Decode base64 audio
            import base64
            audio_base64 = result.get('output_audio_base64', '')
            audio_bytes = base64.b64decode(audio_base64)
            return audio_bytes
        else:
            print_error(f"Voice clone API error: {response.status_code}")
            print_error(f"Response: {response.text}")
            return None

    except requests.exceptions.Timeout:
        print_error("Request timeout during voice cloning")
        return None
    except Exception as e:
        print_error(f"Error calling voice-clone API: {e}")
        return None


def load_timeline_cache(cache_dir):
    """Load cached timeline data if available"""
    import json

    timeline_json_path = os.path.join(cache_dir, 'timeline.json')
    if not os.path.exists(timeline_json_path):
        return None, None

    try:
        with open(timeline_json_path, 'r') as f:
            cache_data = json.load(f)

        timeline = cache_data.get('timeline', [])
        metadata = cache_data.get('metadata', {})

        # Verify all fragment files exist
        fragments_dir = cache_data.get('fragments_dir', '')
        if not fragments_dir or not os.path.exists(fragments_dir):
            return None, None

        for fragment in timeline:
            fragment_path = os.path.join(fragments_dir, fragment['file'])
            if not os.path.exists(fragment_path):
                return None, None

        return timeline, metadata
    except Exception as e:
        print_warning(f"Failed to load timeline cache: {e}")
        return None, None


def save_timeline_cache(timeline, metadata, cache_dir, fragments_dir):
    """Save timeline data to cache file"""
    import json

    os.makedirs(cache_dir, exist_ok=True)
    timeline_json_path = os.path.join(cache_dir, 'timeline.json')

    cache_data = {
        'timeline': timeline,
        'metadata': metadata,
        'fragments_dir': fragments_dir
    }

    try:
        with open(timeline_json_path, 'w') as f:
            json.dump(cache_data, f, indent=2)
        return True
    except Exception as e:
        print_warning(f"Failed to save timeline cache: {e}")
        return False


def process_video(input_file, source_lang, target_lang, generate_audio, generate_subtitle, subtitle_source_lang, output_dir, api_url, speaker_id=0, split_audio=False, run_subtitle_refiner=False):
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
    if split_audio:
        print_info(f"Audio splitting: Yes (vocals for segmentation)")

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

    # Prepare cache directory for timeline data
    input_path = Path(input_file)
    cache_dir = output_dir / '.stream-polyglot-cache' / input_path.stem
    os.makedirs(cache_dir, exist_ok=True)

    # Process subtitle generation with timeline
    if generate_subtitle:
        print_header("Subtitle Generation with Timeline")

        print_info(f"Audio language: {source_lang}")
        print_info(f"Subtitle language: {target_lang}")

        # Try to load cached timeline first
        cached_timeline, cached_metadata = load_timeline_cache(cache_dir)

        if cached_timeline and cached_metadata:
            print_success("Found cached timeline data, skipping segmentation")
            timeline = cached_timeline
            metadata = cached_metadata
            fragments_dir = cached_metadata.get('fragments_dir', '')

            fragment_count = len(timeline)
            total_duration = metadata.get('total_duration', 0)
            print_info(f"Using {fragment_count} cached speech fragments")
            print_info(f"Total audio duration: {total_duration:.2f}s")

            # If split_audio is requested, extract audio and run splitting in background
            if split_audio:
                # Use cache directory for temporary audio (won't be auto-deleted)
                split_audio_dir = cache_dir / 'temp_audio'
                os.makedirs(split_audio_dir, exist_ok=True)
                tmp_audio_path = str(split_audio_dir / 'extracted_audio.wav')

                print_info("Extracting audio for splitting...")
                if extract_audio(input_file, tmp_audio_path):
                    # Start audio splitting in background thread
                    split_thread = threading.Thread(
                        target=audio_split_background,
                        args=(tmp_audio_path, api_url, cache_dir),
                        daemon=True
                    )
                    split_thread.start()
                    print_info("Audio splitting started in background (processing continues...)")
        else:
            # Need to segment audio - create persistent cache directory for fragments
            print_info("No cached timeline found, performing segmentation...")
            fragments_dir = str(cache_dir / 'fragments')
            os.makedirs(fragments_dir, exist_ok=True)

            with tempfile.TemporaryDirectory() as temp_dir:
                tmp_audio_path = os.path.join(temp_dir, 'extracted_audio.wav')

                try:
                    # Step 1: Extract audio from video
                    print_info("Step 1/4: Extracting audio from video...")
                    if not extract_audio(input_file, tmp_audio_path):
                        return 1

                    # Step 1.5: Split audio if --split flag is set (run in background)
                    audio_for_segmentation = tmp_audio_path
                    if split_audio:
                        # Start audio splitting in background thread
                        split_thread = threading.Thread(
                            target=audio_split_background,
                            args=(tmp_audio_path, api_url, cache_dir),
                            daemon=True
                        )
                        split_thread.start()
                        print_info("Audio splitting started in background (processing continues...)")

                    # Step 2: Segment audio with timeline
                    print_info("Step 2/4: Segmenting audio with VAD-based timeline...")
                    timeline, metadata = segment_with_timeline(
                        audio_path=audio_for_segmentation,
                        output_dir=fragments_dir,
                        chunk_duration=30.0,
                        m4t_api_url=api_url,
                        save_timeline=False
                    )

                    fragment_count = len(timeline)
                    total_duration = metadata.get('total_duration', 0)
                    print_success(f"Segmented into {fragment_count} speech fragments")
                    print_info(f"Total audio duration: {total_duration:.2f}s")

                    # Save timeline to cache with fragments_dir
                    metadata['fragments_dir'] = fragments_dir
                    if split_audio:
                        metadata['split_audio'] = True
                    save_timeline_cache(timeline, metadata, cache_dir, fragments_dir)
                    print_success("Timeline cached for future use")

                except Exception as e:
                    print_error(f"Error during audio extraction/segmentation: {e}")
                    import traceback
                    traceback.print_exc()
                    return 1

        try:
            # Step 3: Translate each fragment
            print_info(f"Step 3/4: Translating {fragment_count} fragments...")
            subtitles = []

            # Use tqdm progress bar
            with tqdm(total=fragment_count, desc="Translating", unit="fragment",
                     bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                     ncols=80) as pbar:
                    for i, fragment in enumerate(timeline):
                        fragment_path = os.path.join(fragments_dir, fragment['file'])

                        source_text = None
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
                            except Exception as e:
                                tqdm.write(f"{Colors.RED}✗ Fragment {i}: Source transcription failed: {e}{Colors.END}")

                        # Translate fragment to target language
                        result = speech_to_text_translation(fragment_path, source_lang, target_lang, api_url, verbose=False)

                        if result and result.get('output_text'):
                            translated_text = result['output_text'].strip()
                            if translated_text:
                                # If bilingual mode, combine source and target text
                                if subtitle_source_lang and source_text:
                                    # Bilingual format: target language on first line, source language on second line
                                    combined_text = f"{translated_text}\n{source_text}"
                                else:
                                    combined_text = translated_text

                                subtitles.append({
                                    'start': fragment['start'],
                                    'end': fragment['end'],
                                    'text': combined_text
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

            # If bilingual mode, use format like "video.eng-cmn.srt"
            if subtitle_source_lang:
                output_srt_filename = f"{input_path.stem}.{source_lang}-{target_lang}.srt"
                subtitle_type = "Bilingual"
            else:
                output_srt_filename = f"{input_path.stem}.{target_lang}.srt"
                subtitle_type = "Target language"

            output_srt_path = Path(output_dir) / output_srt_filename

            # Generate and save SRT
            srt_content = generate_srt_content(subtitles, merge_short=True)
            if save_srt_file(srt_content, str(output_srt_path)):
                print_success(f"{subtitle_type} subtitle saved: {output_srt_path}")

                # Run subtitle-refiner if requested
                if run_subtitle_refiner:
                    print_header("Running Subtitle Refiner")
                    print_info("Refining subtitle translations with LLM...")

                    refiner_path = Path(__file__).parent.parent / 'stream-polyglot-refiner' / 'subtitle-refiner'

                    try:
                        # Use Popen with cwd parameter (cross-platform compatible)
                        process = subprocess.Popen(
                            ['node', 'dist/index.js', str(output_srt_path)],
                            cwd=str(refiner_path),  # Change directory using cwd parameter
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                            bufsize=1,
                            universal_newlines=True,
                            encoding='utf-8',  # Explicitly use UTF-8 encoding for Windows compatibility
                            errors='replace'  # Replace invalid characters instead of crashing
                        )

                        # Stream output line by line
                        for line in process.stdout:
                            print(line, end='')

                        # Wait for process to complete
                        return_code = process.wait()

                        if return_code == 0:
                            print_success("Subtitle refinement completed")
                        else:
                            print_error(f"Subtitle refiner failed with exit code {return_code}")
                            print_warning("Continuing with unrefined subtitle...")
                    except Exception as e:
                        print_error(f"Error running subtitle refiner: {e}")
                        print_warning("Continuing with unrefined subtitle...")
            else:
                print_error(f"Failed to save {subtitle_type.lower()} subtitle")
                return 1

            # Print summary
            print_header("Subtitle Generation Result")
            print_success(f"Generated {len(subtitles)} subtitle entries")
            print_info(f"Subtitle file: {output_srt_path}")
            if subtitle_source_lang:
                print_info(f"Format: Bilingual ({source_lang} + {target_lang})")

        except Exception as e:
            print_error(f"Error during subtitle generation: {e}")
            import traceback
            traceback.print_exc()
            return 1

    # Process audio dubbing with timeline-based translation
    if generate_audio:
        print_header("Audio Dubbing Generation with Timeline")

        print_info(f"Audio language: {source_lang}")
        print_info(f"Dubbed language: {target_lang}")

        # Try to load cached timeline first
        cached_timeline, cached_metadata = load_timeline_cache(cache_dir)

        if cached_timeline and cached_timeline and cached_metadata:
            print_success("Found cached timeline data, skipping segmentation")
            timeline = cached_timeline
            metadata = cached_metadata
            fragments_dir = cached_metadata.get('fragments_dir', '')

            fragment_count = len(timeline)
            total_duration = metadata.get('total_duration', 0)
            sample_rate = metadata.get('sample_rate', 16000)
            print_info(f"Using {fragment_count} cached speech fragments")
            print_info(f"Total audio duration: {total_duration:.2f}s")

            # If split_audio is requested, extract audio and run splitting in background
            if split_audio:
                # Use cache directory for temporary audio (won't be auto-deleted)
                split_audio_dir = cache_dir / 'temp_audio'
                os.makedirs(split_audio_dir, exist_ok=True)
                tmp_audio_path = str(split_audio_dir / 'extracted_audio.wav')

                print_info("Extracting audio for splitting...")
                if extract_audio(input_file, tmp_audio_path):
                    # Start audio splitting in background thread
                    split_thread = threading.Thread(
                        target=audio_split_background,
                        args=(tmp_audio_path, api_url, cache_dir),
                        daemon=True
                    )
                    split_thread.start()
                    print_info("Audio splitting started in background (processing continues...)")
        else:
            # Need to segment audio - create persistent cache directory for fragments
            print_info("No cached timeline found, performing segmentation...")
            fragments_dir = str(cache_dir / 'fragments')
            os.makedirs(fragments_dir, exist_ok=True)

            with tempfile.TemporaryDirectory() as temp_dir:
                tmp_audio_path = os.path.join(temp_dir, 'extracted_audio.wav')

                try:
                    # Step 1: Extract audio from video
                    print_info("Step 1/4: Extracting audio from video...")
                    if not extract_audio(input_file, tmp_audio_path):
                        return 1

                    # Step 1.5: Split audio if --split flag is set (run in background)
                    audio_for_segmentation = tmp_audio_path
                    if split_audio:
                        # Start audio splitting in background thread
                        split_thread = threading.Thread(
                            target=audio_split_background,
                            args=(tmp_audio_path, api_url, cache_dir),
                            daemon=True
                        )
                        split_thread.start()
                        print_info("Audio splitting started in background (processing continues...)")

                    # Step 2: Segment audio with timeline
                    print_info("Step 2/4: Segmenting audio with VAD-based timeline...")
                    timeline, metadata = segment_with_timeline(
                        audio_path=audio_for_segmentation,
                        output_dir=fragments_dir,
                        chunk_duration=30.0,
                        m4t_api_url=api_url,
                        save_timeline=False
                    )

                    fragment_count = len(timeline)
                    total_duration = metadata.get('total_duration', 0)
                    sample_rate = metadata.get('sample_rate', 16000)
                    print_success(f"Segmented into {fragment_count} speech fragments")
                    print_info(f"Total audio duration: {total_duration:.2f}s")

                    # Save timeline to cache with fragments_dir
                    metadata['fragments_dir'] = fragments_dir
                    if split_audio:
                        metadata['split_audio'] = True
                    save_timeline_cache(timeline, metadata, cache_dir, fragments_dir)
                    print_success("Timeline cached for future use")

                except Exception as e:
                    print_error(f"Error during audio extraction/segmentation: {e}")
                    import traceback
                    traceback.print_exc()
                    return 1

        try:
            # Step 3: Translate each fragment to audio
            print_info(f"Step 3/4: Translating {fragment_count} fragments to speech...")

            import numpy as np
            import soundfile as sf
            import base64

            translated_fragments = []

            # Use tqdm progress bar
            with tqdm(total=fragment_count, desc="Translating", unit="fragment",
                     bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                     ncols=80) as pbar:
                    for i, fragment in enumerate(timeline):
                        fragment_path = os.path.join(fragments_dir, fragment['file'])

                        # Translate fragment to target language speech
                        s2st_result = speech_to_speech_translation(
                            fragment_path, source_lang, target_lang, api_url, speaker_id, verbose=False
                        )

                        if s2st_result and s2st_result.get('output_audio_base64'):
                            # Decode base64 audio to numpy array
                            audio_base64 = s2st_result['output_audio_base64']
                            audio_bytes = base64.b64decode(audio_base64)

                            # Load audio from bytes
                            import io
                            audio_array, sr = sf.read(io.BytesIO(audio_bytes))

                            # Store translated fragment with timing
                            translated_fragments.append({
                                'start': fragment['start'],
                                'end': fragment['end'],
                                'audio': audio_array,
                                'sample_rate': sr
                            })
                        else:
                            tqdm.write(f"{Colors.YELLOW}⚠ Fragment {i}: Translation failed, skipping{Colors.END}")

                        # Update progress bar
                        pbar.update(1)

            # Step 4: Concatenate fragments with timeline alignment
            print_info(f"Step 4/4: Concatenating {len(translated_fragments)} translated fragments...")

            if not translated_fragments:
                print_error("No audio fragments translated")
                return 1

            # Create final audio array with silence gaps
            final_duration_samples = int(total_duration * sample_rate)
            final_audio = np.zeros(final_duration_samples, dtype=np.float32)

            for fragment_data in translated_fragments:
                start_sample = int(fragment_data['start'] * sample_rate)
                audio_data = fragment_data['audio']

                # Convert to mono if stereo
                if len(audio_data.shape) > 1:
                    audio_data = np.mean(audio_data, axis=1)

                # Insert audio at correct position
                end_sample = start_sample + len(audio_data)
                if end_sample <= final_duration_samples:
                    final_audio[start_sample:end_sample] = audio_data
                else:
                    # Truncate if exceeds total duration
                    available = final_duration_samples - start_sample
                    final_audio[start_sample:] = audio_data[:available]

            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)

            # Generate output filename
            input_path = Path(input_file)
            output_filename = f"{input_path.stem}.{target_lang}.wav"
            output_path = Path(output_dir) / output_filename

            # Save final audio
            print_info(f"Saving audio to: {output_path}")
            sf.write(str(output_path), final_audio, sample_rate)
            print_success(f"Audio saved to: {output_path}")

            # Get file size for result display
            file_size = os.path.getsize(output_path) / 1024  # KB

            # Print result summary
            print_header("Audio Dubbing Result")
            print_success("Audio dubbing completed!")
            print_success(f"Translated {len(translated_fragments)} speech fragments")
            print_info(f"Output file: {output_path}")
            print_info(f"File size: {file_size:.1f} KB")
            print_info(f"Sample rate: {sample_rate} Hz")
            print_info(f"Duration: {total_duration:.2f} seconds")

        except Exception as e:
            print_error(f"Error during audio dubbing: {e}")
            import traceback
            traceback.print_exc()
            return 1

    return 0


def process_trans_voice(input_file, srt_file, source_lang, target_lang, output_dir, api_url, seed=None):
    """
    Process voice cloning translation from bilingual SRT file

    Args:
        input_file: Input video file (for extracting cache directory)
        srt_file: Bilingual SRT subtitle file path
        source_lang: Source language code
        target_lang: Target language code
        output_dir: Output directory for generated audio
        api_url: m4t API server URL
        seed: Random seed for reproducibility (None for random-but-fixed, >=0 for specific seed)

    Returns:
        Exit code (0 for success, 1 for error)
    """
    import random

    # Generate random seed once for this generation process if not specified
    if seed is None:
        seed = random.randint(0, 1000000)
        print_info(f"Generated random seed: {seed}")
    else:
        print_info(f"Using fixed seed: {seed}")

    print_header("Stream-Polyglot Voice Cloning from Subtitle")

    # Check SRT file exists
    if not check_file_exists(srt_file):
        return 1

    # Check m4t server
    if not check_m4t_server(api_url):
        return 1

    # Configuration
    print_header("Voice Cloning Configuration")
    print_info(f"SRT file: {srt_file}")
    print_info(f"Source language (reference audio): {source_lang}")
    print_info(f"Target language (synthesized speech): {target_lang}")

    if output_dir:
        print_info(f"Output directory: {output_dir}")
    else:
        # Default output same directory as SRT file
        srt_path = Path(srt_file)
        output_dir = srt_path.parent
        print_info(f"Output directory: {output_dir} (default)")

    # Prepare cache directory to access timeline fragments
    input_path = Path(input_file) if input_file else None
    if input_path and input_path.exists():
        cache_dir = output_dir / '.stream-polyglot-cache' / input_path.stem
    else:
        # If no input file or doesn't exist, derive from SRT filename
        srt_stem = Path(srt_file).stem.split('.')[0]  # Remove .lang-lang part
        cache_dir = output_dir / '.stream-polyglot-cache' / srt_stem

    # Try to load cached timeline first
    cached_timeline, cached_metadata = load_timeline_cache(cache_dir)

    if cached_timeline and cached_metadata:
        fragments_dir = cached_metadata.get('fragments_dir', '')
        if fragments_dir and os.path.exists(fragments_dir):
            # Cache is valid, use it
            print_success(f"Found {len(cached_timeline)} cached audio fragments")
            print_info(f"Fragments directory: {fragments_dir}")
            timeline = cached_timeline
            metadata = cached_metadata
        else:
            # Cache exists but fragments directory is missing, need to re-segment
            print_warning("Cached timeline exists but fragments directory not found")
            cached_timeline = None
            cached_metadata = None

    if not cached_timeline or not cached_metadata:
        # No valid cache, need to segment audio
        # Require input file for segmentation
        if not input_file or not check_file_exists(input_file):
            print_error("Input video file is required when cached timeline is not available")
            print_info(f"Expected cache directory: {cache_dir}")
            print_info("Please provide input video file or run subtitle/audio generation first")
            return 1

        print_info("No cached timeline found, performing audio segmentation...")
        fragments_dir = str(cache_dir / 'fragments')
        os.makedirs(fragments_dir, exist_ok=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_audio_path = os.path.join(temp_dir, 'extracted_audio.wav')

            try:
                # Step 0a: Extract audio from video
                print_info("Extracting audio from video...")
                if not extract_audio(input_file, tmp_audio_path):
                    return 1

                # Step 0b: Segment audio with timeline
                print_info("Segmenting audio with VAD-based timeline...")
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

                # Save timeline to cache
                metadata['fragments_dir'] = fragments_dir
                save_timeline_cache(timeline, metadata, cache_dir, fragments_dir)
                print_success("Timeline cached for future use")

            except Exception as e:
                print_error(f"Error during audio extraction/segmentation: {e}")
                import traceback
                traceback.print_exc()
                return 1
    else:
        timeline = cached_timeline
        metadata = cached_metadata

    try:
        # Step 1: Parse bilingual SRT file
        print_header("Step 1/4: Parsing Bilingual SRT File")
        print_info(f"Parsing SRT file: {srt_file}")
        subtitles = parse_srt_file(srt_file)

        if not subtitles:
            print_error("No subtitles found in SRT file")
            return 1

        print_success(f"Parsed {len(subtitles)} subtitle entries")

        # Step 2: Match SRT timing with cached fragments
        print_header("Step 2/4: Matching Subtitles with Audio Fragments")
        print_info("Matching subtitle timing with cached audio fragments...")

        timing_tolerance = 0.5  # 0.5 second tolerance for timing match
        matched_segments = []

        for i, subtitle in enumerate(subtitles):
            sub_start = subtitle['start']
            sub_end = subtitle['end']
            sub_text = subtitle['text']

            # Extract bilingual text (target, source)
            target_text, source_text = extract_bilingual_text(sub_text)

            if not target_text or not source_text:
                print_warning(f"Subtitle {i}: Empty text, skipping")
                continue

            # Find matching cached fragment by timing
            best_match = None
            best_diff = float('inf')

            for fragment in cached_timeline:
                frag_start = fragment['start']
                frag_end = fragment['end']

                # Calculate timing difference (use start time as primary match)
                start_diff = abs(sub_start - frag_start)
                end_diff = abs(sub_end - frag_end)
                total_diff = start_diff + end_diff

                if start_diff <= timing_tolerance and total_diff < best_diff:
                    best_match = fragment
                    best_diff = total_diff

            if best_match:
                fragment_path = os.path.join(fragments_dir, best_match['file'])

                if os.path.exists(fragment_path):
                    matched_segments.append({
                        'subtitle_index': i,
                        'start': sub_start,
                        'end': sub_end,
                        'target_text': target_text,
                        'source_text': source_text,
                        'ref_audio_path': fragment_path,
                        'fragment_info': best_match
                    })
                else:
                    print_warning(f"Subtitle {i}: Fragment file not found: {fragment_path}")
            else:
                print_warning(f"Subtitle {i}: No matching fragment found (start: {sub_start:.2f}s)")

        if not matched_segments:
            print_error("No subtitle-fragment matches found")
            print_info("Check that subtitle timing matches the audio fragments")
            return 1

        print_success(f"Matched {len(matched_segments)} subtitle entries with audio fragments")
        print_info(f"Unmatched: {len(subtitles) - len(matched_segments)} entries")

        # Step 3: Voice clone each segment
        print_header("Step 3/4: Voice Cloning Translation")
        print_info(f"Cloning {len(matched_segments)} segments...")

        import numpy as np
        import soundfile as sf
        import io

        cloned_segments = []

        # Use tqdm progress bar
        with tqdm(total=len(matched_segments), desc="Cloning", unit="segment",
                 bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                 ncols=80) as pbar:
                for seg in matched_segments:
                    # Call voice-clone API with the same seed for all segments
                    audio_bytes = voice_clone_translation(
                        ref_audio_path=seg['ref_audio_path'],
                        text=seg['target_text'],
                        text_language=target_lang,
                        prompt_text=seg['source_text'],
                        prompt_language=source_lang,
                        api_url=api_url,
                        seed=seed,
                        verbose=False
                    )

                    if audio_bytes:
                        # Load audio from bytes
                        audio_array, sr = sf.read(io.BytesIO(audio_bytes))

                        cloned_segments.append({
                            'start': seg['start'],
                            'end': seg['end'],
                            'audio': audio_array,
                            'sample_rate': sr
                        })
                    else:
                        tqdm.write(f"{Colors.YELLOW}⚠ Segment {seg['subtitle_index']}: Voice cloning failed, skipping{Colors.END}")

                    # Update progress bar
                    pbar.update(1)

        if not cloned_segments:
            print_error("No segments successfully cloned")
            return 1

        print_success(f"Successfully cloned {len(cloned_segments)} segments")

        # Step 4: Concatenate cloned segments with timeline alignment
        print_header("Step 4/4: Concatenating Audio")
        print_info(f"Concatenating {len(cloned_segments)} cloned segments...")

        # Get total duration from metadata or calculate from last segment
        total_duration = cached_metadata.get('total_duration', 0)
        if total_duration == 0 and cloned_segments:
            total_duration = max(seg['end'] for seg in cloned_segments)

        # Use the sample rate from cloned audio (usually 32000 for GPT-SoVITS)
        # instead of cached metadata (16000 for original audio)
        if cloned_segments:
            sample_rate = cloned_segments[0]['sample_rate']
            print_info(f"Using cloned audio sample rate: {sample_rate} Hz")
        else:
            sample_rate = cached_metadata.get('sample_rate', 16000)

        # Create final audio array with silence gaps
        final_duration_samples = int(total_duration * sample_rate)
        final_audio = np.zeros(final_duration_samples, dtype=np.float32)

        for seg_data in cloned_segments:
            start_sample = int(seg_data['start'] * sample_rate)
            audio_data = seg_data['audio']
            seg_sample_rate = seg_data['sample_rate']

            # Convert to mono if stereo
            if len(audio_data.shape) > 1:
                audio_data = np.mean(audio_data, axis=1)

            # Ensure float32
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)

            # Resample if segment sample rate doesn't match target
            if seg_sample_rate != sample_rate:
                from scipy import signal
                # Calculate resampling ratio
                num_samples = int(len(audio_data) * sample_rate / seg_sample_rate)
                audio_data = signal.resample(audio_data, num_samples)

            # Insert audio at correct position
            end_sample = start_sample + len(audio_data)
            if end_sample <= final_duration_samples:
                final_audio[start_sample:end_sample] = audio_data
            else:
                # Truncate if exceeds total duration
                available = final_duration_samples - start_sample
                if available > 0:
                    final_audio[start_sample:] = audio_data[:available]

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Generate output filename
        srt_path = Path(srt_file)
        output_filename = f"{srt_path.stem}.cloned.wav"
        output_path = Path(output_dir) / output_filename

        # Save final audio
        print_info(f"Saving audio to: {output_path}")
        sf.write(str(output_path), final_audio, sample_rate)
        print_success(f"Audio saved to: {output_path}")

        # Get file size for result display
        file_size = os.path.getsize(output_path) / 1024  # KB

        # Print result summary
        print_header("Voice Cloning Result")
        print_success("Voice cloning translation completed!")
        print_success(f"Cloned {len(cloned_segments)} speech segments")
        print_info(f"Output file: {output_path}")
        print_info(f"File size: {file_size:.1f} KB")
        print_info(f"Sample rate: {sample_rate} Hz")
        print_info(f"Duration: {total_duration:.2f} seconds")

    except Exception as e:
        print_error(f"Error during voice cloning translation: {e}")
        import traceback
        traceback.print_exc()
        return 1

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

  # Generate bilingual subtitles (English + Chinese)
  python -m main video.mp4 --lang eng:cmn --subtitle --subtitle-source-lang

  # Generate voice-cloned audio from bilingual SRT file (with --lang)
  python -m main video.mp4 --lang eng:cmn --trans-voice video.eng-cmn.srt

  # Generate voice-cloned audio from bilingual SRT file (infer from filename)
  python -m main --trans-voice video.eng-cmn.srt

  # Generate voice-cloned audio with fixed seed for reproducibility
  python -m main video.mp4 --lang eng:cmn --trans-voice video.eng-cmn.srt --seed 42

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
        nargs='?',  # Make optional (required only for subtitle/audio modes)
        help='Input video or audio file path'
    )

    # Language pair argument
    parser.add_argument(
        '--lang',
        required=False,  # Not required if can infer from --trans-voice filename
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

    # Voice cloning from SRT
    parser.add_argument(
        '--trans-voice',
        metavar='SRT_FILE',
        help='Generate voice-cloned audio from bilingual SRT subtitle file'
    )

    # Optional subtitle source language
    parser.add_argument(
        '--subtitle-source-lang',
        action='store_true',
        help='Source language for subtitle generation (default: same as --lang source language)'
    )

    # Subtitle refiner option
    parser.add_argument(
        '--subtitle-refiner',
        action='store_true',
        help='Automatically run subtitle-refiner on generated subtitle file to improve translation quality (enables --subtitle-source-lang by default)'
    )

    # Audio split option (split before segmentation)
    parser.add_argument(
        '--split',
        action='store_true',
        help='Split audio into vocals and accompaniment before timeline segmentation (use vocals for segmentation)'
    )

    # Optional speaker ID for audio generation
    parser.add_argument(
        '--speaker-id',
        type=int,
        default=0,
        metavar='ID',
        help='Speaker voice ID for audio generation (0-199, default: 0)'
    )

    # Random seed for voice cloning
    parser.add_argument(
        '--seed',
        type=int,
        default=None,
        metavar='SEED',
        help='Random seed for voice cloning reproducibility (default: random but fixed across one generation process, 0-1000000 for specific seed)'
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

    # Auto-enable subtitle-source-lang when using subtitle-refiner
    if args.subtitle_refiner:
        args.subtitle_source_lang = True
        if args.subtitle:
            print_info("--subtitle-refiner enabled: bilingual subtitles will be generated automatically")

    # Check if using --trans-voice mode
    if args.trans_voice:
        # Voice cloning from SRT file
        # Language inference: Priority 1: --lang, Priority 2: SRT filename
        if args.lang:
            source_lang, target_lang = parse_language_pair(args.lang)
            if not source_lang or not target_lang:
                return 1
        else:
            # Try to infer from SRT filename
            source_lang, target_lang = infer_language_from_srt_filename(args.trans_voice)
            if not source_lang or not target_lang:
                print_error("Cannot infer language pair from SRT filename")
                print_info("Please specify --lang or use SRT filename format: xxx.source-target.srt")
                print_info("Example: video.eng-cmn.srt")
                return 1
            print_info(f"Inferred language pair from SRT filename: {source_lang}:{target_lang}")

        # Process voice cloning translation
        try:
            return process_trans_voice(
                input_file=args.input,  # May be None if not provided
                srt_file=args.trans_voice,
                source_lang=source_lang,
                target_lang=target_lang,
                output_dir=args.output,
                api_url=args.api_url,
                seed=args.seed
            )
        except KeyboardInterrupt:
            print_error("\n\nInterrupted by user")
            return 130
        except Exception as e:
            print_error(f"\nUnexpected error: {e}")
            import traceback
            traceback.print_exc()
            return 1

    else:
        # Normal video processing mode
        # Validate required arguments for normal mode
        if not args.input:
            print_error("Input video file is required")
            print_info("Usage: python -m main video.mp4 --lang eng:cmn --subtitle")
            return 1

        if not args.lang:
            print_error("Language pair (--lang) is required")
            print_info("Usage: python -m main video.mp4 --lang eng:cmn --subtitle")
            return 1

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
                args.speaker_id,
                args.split,
                args.subtitle_refiner
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
