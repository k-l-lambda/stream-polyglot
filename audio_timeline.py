"""
Audio Timeline Segmentation Module

Segments long audio files into speech fragments using VAD with intelligent
chunk processing. Handles boundary conditions by carrying over incomplete
fragments to the next chunk.

Usage:
    from audio_timeline import segment_with_timeline

    timeline, fragments = segment_with_timeline(
        audio_path="video_audio.wav",
        output_dir="./fragments",
        chunk_duration=30.0,
        m4t_api_url="http://localhost:8000"
    )
"""

import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import requests
import soundfile as sf
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AudioTimeline:
    """Audio segmentation with timeline tracking"""

    def __init__(
        self,
        m4t_api_url: str = "http://localhost:8000",
        min_silence_duration_ms: int = 300,
        min_speech_duration_ms: int = 250,
        vad_threshold: float = 0.5
    ):
        """
        Initialize audio timeline segmenter

        Args:
            m4t_api_url: URL of m4t API server
            min_silence_duration_ms: Minimum silence gap to consider sentence boundary
            min_speech_duration_ms: Minimum speech segment duration
            vad_threshold: VAD sensitivity (0.0-1.0, lower = more sensitive)
        """
        self.m4t_api_url = m4t_api_url.rstrip('/')
        self.min_silence_duration_ms = min_silence_duration_ms
        self.min_speech_duration_ms = min_speech_duration_ms
        self.vad_threshold = vad_threshold

    def detect_speech_in_chunk(self, audio_chunk: bytes) -> List[Dict]:
        """
        Detect speech segments in audio chunk using m4t VAD API

        Args:
            audio_chunk: Audio data in WAV format (bytes)

        Returns:
            List of speech segments with start, end, duration
        """
        try:
            response = requests.post(
                f"{self.m4t_api_url}/v1/detect-voice",
                files={"audio": ("chunk.wav", audio_chunk, "audio/wav")},
                data={
                    "threshold": self.vad_threshold,
                    "min_speech_duration_ms": self.min_speech_duration_ms,
                    "min_silence_duration_ms": self.min_silence_duration_ms
                },
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            return result.get("speech_segments", [])

        except requests.RequestException as e:
            logger.error(f"VAD API request failed: {e}")
            raise RuntimeError(f"Failed to detect speech: {e}")

    def extract_audio_chunk(
        self,
        audio_array: np.ndarray,
        sample_rate: int,
        start_time: float,
        duration: float
    ) -> Tuple[np.ndarray, bytes]:
        """
        Extract a chunk of audio from the full array

        Args:
            audio_array: Full audio as numpy array
            sample_rate: Audio sample rate
            start_time: Start time in seconds
            duration: Chunk duration in seconds

        Returns:
            (chunk_array, chunk_bytes) - numpy array and WAV bytes
        """
        start_sample = int(start_time * sample_rate)
        end_sample = int((start_time + duration) * sample_rate)
        end_sample = min(end_sample, len(audio_array))

        chunk_array = audio_array[start_sample:end_sample]

        # Convert to WAV bytes
        import io
        buffer = io.BytesIO()
        sf.write(buffer, chunk_array, sample_rate, format='WAV')
        buffer.seek(0)
        chunk_bytes = buffer.read()

        return chunk_array, chunk_bytes

    def save_fragment(
        self,
        audio_array: np.ndarray,
        sample_rate: int,
        start_time: float,
        end_time: float,
        fragment_id: int,
        output_dir: str
    ) -> str:
        """
        Save audio fragment to disk

        Args:
            audio_array: Full audio array
            sample_rate: Sample rate
            start_time: Fragment start time
            end_time: Fragment end time
            fragment_id: Sequential fragment ID
            output_dir: Output directory path

        Returns:
            Path to saved fragment file
        """
        start_sample = int(start_time * sample_rate)
        end_sample = int(end_time * sample_rate)
        fragment_audio = audio_array[start_sample:end_sample]

        # Format: fragment_000012.5_000018.3.wav
        filename = f"fragment_{start_time:09.1f}_{end_time:09.1f}.wav"
        filepath = os.path.join(output_dir, filename)

        sf.write(filepath, fragment_audio, sample_rate)
        logger.info(f"Saved fragment {fragment_id}: {filename} ({end_time - start_time:.2f}s)")

        return filepath

    def is_incomplete_segment(
        self,
        segment: Dict,
        chunk_end_time: float,
        tolerance: float = 0.1
    ) -> bool:
        """
        Check if a speech segment is incomplete (cut off at chunk boundary)

        Args:
            segment: Speech segment dict with start, end, duration
            chunk_end_time: End time of current chunk
            tolerance: Time tolerance in seconds

        Returns:
            True if segment appears to be cut off
        """
        # If segment ends very close to chunk boundary, likely incomplete
        return abs(segment["end"] - chunk_end_time) < tolerance

    def segment_with_timeline(
        self,
        audio_path: str,
        output_dir: str,
        chunk_duration: float = 30.0
    ) -> Tuple[List[Dict], Dict]:
        """
        Segment audio file into speech fragments with timeline

        Args:
            audio_path: Path to input audio file
            output_dir: Directory to save fragments
            chunk_duration: Duration of processing chunks in seconds

        Returns:
            (timeline, metadata) tuple:
            - timeline: List of fragment dicts with id, file, start, end
            - metadata: Dict with input_file, total_duration, fragment_count
        """
        logger.info(f"Loading audio from: {audio_path}")

        # Load audio
        audio_array, sample_rate = sf.read(audio_path, dtype='float32')
        total_duration = len(audio_array) / sample_rate

        logger.info(f"Audio loaded: {total_duration:.2f}s, {sample_rate}Hz")

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Process in chunks
        timeline = []
        fragment_id = 0
        current_time = 0.0
        incomplete_buffer = None  # Carry-over incomplete segment

        while current_time < total_duration:
            # Calculate chunk boundaries
            chunk_start = current_time
            chunk_end = min(current_time + chunk_duration, total_duration)
            actual_chunk_duration = chunk_end - chunk_start

            logger.info(f"Processing chunk: {chunk_start:.1f}s - {chunk_end:.1f}s")

            # Extract chunk
            chunk_array, chunk_bytes = self.extract_audio_chunk(
                audio_array, sample_rate, chunk_start, actual_chunk_duration
            )

            # Detect speech in chunk
            speech_segments = self.detect_speech_in_chunk(chunk_bytes)
            logger.info(f"  Detected {len(speech_segments)} speech segments")

            # Adjust segment timestamps to absolute time
            for seg in speech_segments:
                seg["start"] += chunk_start
                seg["end"] += chunk_start

            # Handle incomplete segment from previous chunk
            if incomplete_buffer:
                logger.info(f"  Carrying over incomplete segment from {incomplete_buffer['start']:.1f}s")
                # If current chunk starts with speech, merge with buffer
                if speech_segments and speech_segments[0]["start"] - chunk_start < 0.5:
                    # Extend incomplete buffer to include first segment
                    incomplete_buffer["end"] = speech_segments[0]["end"]
                    incomplete_buffer["duration"] = incomplete_buffer["end"] - incomplete_buffer["start"]
                    speech_segments[0] = incomplete_buffer
                else:
                    # Save incomplete buffer as-is (speech ended at chunk boundary)
                    filepath = self.save_fragment(
                        audio_array, sample_rate,
                        incomplete_buffer["start"], incomplete_buffer["end"],
                        fragment_id, output_dir
                    )
                    timeline.append({
                        "id": fragment_id,
                        "file": os.path.basename(filepath),
                        "start": incomplete_buffer["start"],
                        "end": incomplete_buffer["end"]
                    })
                    fragment_id += 1

                incomplete_buffer = None

            # Check if last segment is incomplete (but NOT if we're at the end of the audio)
            if speech_segments:
                last_segment = speech_segments[-1]
                # Only mark as incomplete if NOT at the end of the audio
                is_at_audio_end = chunk_end >= total_duration - 0.05
                if self.is_incomplete_segment(last_segment, chunk_end) and not is_at_audio_end:
                    logger.info(f"  Last segment incomplete at {last_segment['end']:.1f}s, buffering")
                    incomplete_buffer = last_segment
                    speech_segments = speech_segments[:-1]

                    # Adjust next chunk start to begin slightly before incomplete segment end
                    # This ensures we capture the complete sentence
                    next_chunk_start = last_segment["start"]
                else:
                    next_chunk_start = chunk_end
            else:
                next_chunk_start = chunk_end

            # Save complete segments
            for segment in speech_segments:
                filepath = self.save_fragment(
                    audio_array, sample_rate,
                    segment["start"], segment["end"],
                    fragment_id, output_dir
                )
                timeline.append({
                    "id": fragment_id,
                    "file": os.path.basename(filepath),
                    "start": segment["start"],
                    "end": segment["end"]
                })
                fragment_id += 1

            # Move to next chunk
            current_time = next_chunk_start

            # Safety check: prevent infinite loop
            if next_chunk_start == chunk_start:
                logger.warning("No progress made, advancing by 1 second")
                current_time += 1.0

        # Handle final incomplete buffer if exists
        if incomplete_buffer:
            logger.info("Saving final incomplete segment")
            filepath = self.save_fragment(
                audio_array, sample_rate,
                incomplete_buffer["start"], incomplete_buffer["end"],
                fragment_id, output_dir
            )
            timeline.append({
                "id": fragment_id,
                "file": os.path.basename(filepath),
                "start": incomplete_buffer["start"],
                "end": incomplete_buffer["end"]
            })
            fragment_id += 1

        # Create metadata
        metadata = {
            "input_file": os.path.basename(audio_path),
            "total_duration": total_duration,
            "sample_rate": sample_rate,
            "fragment_count": len(timeline),
            "output_dir": output_dir
        }

        logger.info(f"Segmentation complete: {len(timeline)} fragments")

        return timeline, metadata


def segment_with_timeline(
    audio_path: str,
    output_dir: str,
    chunk_duration: float = 30.0,
    m4t_api_url: str = "http://localhost:8000",
    save_timeline: bool = True
) -> Tuple[List[Dict], Dict]:
    """
    Convenience function to segment audio with timeline

    Args:
        audio_path: Path to input audio file
        output_dir: Directory to save fragments and timeline
        chunk_duration: Processing chunk size in seconds (default: 30.0)
        m4t_api_url: URL of m4t VAD API server
        save_timeline: If True, save timeline.json to output_dir

    Returns:
        (timeline, metadata) tuple
    """
    segmenter = AudioTimeline(m4t_api_url=m4t_api_url)
    timeline, metadata = segmenter.segment_with_timeline(
        audio_path, output_dir, chunk_duration
    )

    if save_timeline:
        timeline_path = os.path.join(output_dir, "timeline.json")
        timeline_data = {
            **metadata,
            "fragments": timeline
        }
        with open(timeline_path, 'w', encoding='utf-8') as f:
            json.dump(timeline_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Timeline saved to: {timeline_path}")

    return timeline, metadata


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) < 2:
        print("Usage: python audio_timeline.py <audio_file> [output_dir] [chunk_duration]")
        sys.exit(1)

    audio_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "./fragments"
    chunk_dur = float(sys.argv[3]) if len(sys.argv) > 3 else 30.0

    timeline, metadata = segment_with_timeline(audio_file, output_dir, chunk_dur)

    print(f"\nSegmentation complete!")
    print(f"Total duration: {metadata['total_duration']:.2f}s")
    print(f"Fragments created: {metadata['fragment_count']}")
    print(f"Output directory: {output_dir}")
