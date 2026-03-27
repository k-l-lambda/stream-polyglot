"""
pipeline.py — End-to-end lecture annotation pipeline.

Orchestrates: Download → Transcribe → Extract Frames → LLM Annotate

Usage:
    from lecture_annotator.pipeline import run_pipeline

    result = run_pipeline("https://youtu.be/xxx", "./output/")
    print(result)
    # {'video': '...', 'audio': '...', 'srt': '...', 'frames_dir': '...', 'annotation': '...', 'success': True}
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LLM_BASE_URL = os.environ.get("LLM_BASE_URL")


def _resolve_api_key(api_key: Optional[str] = None) -> str:
    """Resolve LLM API key: parameter > env var.

    Args:
        api_key: Explicitly provided API key.

    Returns:
        The resolved API key string.

    Raises:
        ValueError: If no API key can be found.
    """
    if api_key:
        return api_key
    env_key = os.environ.get("LLM_API_KEY", "")
    if env_key:
        return env_key
    raise ValueError(
        "No LLM API key found. Please set the LLM_API_KEY environment variable "
        "or pass --api-key / api_key= parameter."
    )


def run_pipeline(
    url: str = "",
    output_dir: str = "./output",
    # Download options
    cookies: Optional[str] = None,
    proxy: Optional[str] = None,
    # Transcription options
    language: Optional[str] = None,
    whisper_model: str = "base",
    m4t_api_url: Optional[str] = None,   # e.g. "http://localhost:8001"
    # Frame extraction options
    frame_strategy: str = "semantic",
    frame_interval: float = 60.0,
    max_frames: int = 50,
    # Annotation options
    annotate_model: str = "",
    api_key: Optional[str] = None,
    # Control options
    skip_download: bool = False,
    video_path: Optional[str] = None,
    audio_path: Optional[str] = None,
    skip_transcribe: bool = False,
    srt_path: Optional[str] = None,
    skip_frames: bool = False,
    frames_dir: Optional[str] = None,
) -> dict:
    """Run the end-to-end lecture annotation pipeline.

    Steps:
        1. Download video from YouTube (skippable)
        2. Transcribe audio to SRT via Whisper (skippable)
        3. Extract key frames from video (skippable)
        4. Annotate lecture using LLM with SRT + frames

    Args:
        url: YouTube video URL (required unless skip_download=True).
        output_dir: Directory for all pipeline outputs.
        cookies: Path to cookies.txt for yt-dlp.
        proxy: Proxy URL for yt-dlp.
        language: ISO 639-1 language code for Whisper (None = auto-detect).
        whisper_model: Whisper model size ('tiny', 'base', 'small', 'medium', 'large-v3').
        frame_strategy: Frame extraction strategy ('semantic', 'uniform', 'scene').
        frame_interval: Interval in seconds for 'uniform' strategy.
        max_frames: Maximum number of frames to extract.
        annotate_model: LLM model identifier for annotation (falls back to $LLM_MODEL).
        api_key: LLM API key (falls back to $LLM_API_KEY env var).
        skip_download: Skip download step (use video_path/audio_path instead).
        video_path: Path to existing video file (used with skip_download).
        audio_path: Path to existing audio file (used with skip_download).
        skip_transcribe: Skip transcription step (use srt_path instead).
        srt_path: Path to existing SRT file (used with skip_transcribe).
        skip_frames: Skip frame extraction step (use frames_dir instead).
        frames_dir: Path to existing frames directory (used with skip_frames).

    Returns:
        dict with keys:
            - ``video``      — path to video file (or None)
            - ``audio``      — path to audio file (or None)
            - ``srt``        — path to SRT subtitle file (or None)
            - ``frames_dir`` — path to frames directory (or None)
            - ``annotation`` — path to final Markdown file (or None)
            - ``success``    — bool indicating overall success
    """
    t0 = time.time()
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    result = {
        "video": video_path,
        "audio": audio_path,
        "srt": srt_path,
        "segments": None,
        "frames_dir": frames_dir,
        "annotation": None,
        "success": False,
    }

    api_key = _resolve_api_key(api_key)
    if not annotate_model:
        annotate_model = os.environ.get("LLM_MODEL", "gpt-4o")
    title = ""  # will be set by download step if run

    # -----------------------------------------------------------------------
    # Step 1: Download
    # -----------------------------------------------------------------------
    logger.info("[1/4] Download video …")

    if skip_download:
        logger.info("  ⏭  Skipped (using provided paths)")
        if video_path:
            logger.info("  Video: %s", video_path)
        if audio_path:
            logger.info("  Audio: %s", audio_path)
    else:
        if not url:
            raise ValueError("YouTube URL is required when skip_download=False")

        from .download import download_video

        logger.info("Downloading: %s", url)
        dl_result = download_video(
            url, output_dir, cookies=cookies, proxy=proxy,
        )
        video_path = str(dl_result["video"])
        audio_path = str(dl_result["audio"])
        result["video"] = video_path
        result["audio"] = audio_path
        title = dl_result.get("title", "")
        logger.info("  ✅ Downloaded: %s", video_path)
        logger.info("     Audio: %s", audio_path)

    # -----------------------------------------------------------------------
    # Step 2: Transcribe
    # -----------------------------------------------------------------------
    logger.info("[2/4] Transcribe audio (Whisper %s) …", whisper_model)

    if skip_transcribe:
        logger.info("  ⏭  Skipped (using provided SRT)")
        if srt_path:
            logger.info("  SRT: %s", srt_path)
    else:
        if not audio_path:
            raise ValueError(
                "audio_path is required for transcription. "
                "Provide --audio or run download step first."
            )

        from .transcribe import transcribe_audio

        logger.info("Transcribing: %s (model=%s, lang=%s, m4t=%s)", audio_path, whisper_model, language, m4t_api_url or "none")
        srt_path = transcribe_audio(
            audio_path, output_dir,
            language=language, model_size=whisper_model,
            m4t_api_url=m4t_api_url,
        )
        result["srt"] = srt_path
        logger.info("  ✅ SRT: %s", srt_path)

    # -----------------------------------------------------------------------
    # Step 2.5: Transcript-wide segmentation
    # -----------------------------------------------------------------------
    transcript_segments = None
    logger.info("[2.5/4] Segment transcript with model=pa/gpt-5.4 …")
    if not srt_path:
        raise ValueError(
            "srt_path is required for transcript segmentation. "
            "Provide --srt or run transcription step first."
        )
    from .segmenter import load_segments_json, segment_transcript
    segments_path = segment_transcript(
        srt_path=srt_path,
        output_dir=output_dir,
        api_key=api_key,
        base_url=LLM_BASE_URL,
        model="pa/gpt-5.4",
    )
    transcript_segments = load_segments_json(segments_path)
    result["segments"] = segments_path
    logger.info("  ✅ Segments: %s (%d paragraphs)", segments_path, len(transcript_segments))

    # -----------------------------------------------------------------------
    # Step 3: Extract key frames
    # -----------------------------------------------------------------------
    logger.info("[3/4] Extract key frames (strategy=%s) …", frame_strategy)

    if skip_frames:
        logger.info("  ⏭  Skipped (using provided frames dir)")
        if frames_dir:
            logger.info("  Frames: %s", frames_dir)
    else:
        if not video_path:
            raise ValueError(
                "video_path is required for frame extraction. "
                "Provide --video or run download step first."
            )

        from .extract_frames import extract_key_frames

        frames_output = os.path.join(output_dir, "frames")
        os.makedirs(frames_output, exist_ok=True)

        logger.info(
            "Extracting frames: video=%s, strategy=%s, max=%d",
            video_path, frame_strategy, max_frames,
        )
        frames_list = extract_key_frames(
            video_path, frames_output,
            srt_path=srt_path,
            interval_secs=frame_interval,
            strategy=frame_strategy,
            max_frames=max_frames,
            transcript_segments=transcript_segments,
        )
        frames_dir = frames_output
        result["frames_dir"] = frames_dir
        logger.info("  ✅ Extracted %d frames → %s", len(frames_list), frames_dir)

    # -----------------------------------------------------------------------
    # Step 4: LLM Annotation
    # -----------------------------------------------------------------------
    logger.info("[4/4] LLM annotation (model=%s) …", annotate_model)

    if not srt_path:
        raise ValueError(
            "srt_path is required for annotation. "
            "Provide --srt or run transcription step first."
        )

    from .annotate import annotate_lecture

    annotation_path = os.path.join(output_dir, "lecture_notes.md")

    # Use download title if available, otherwise derive from filename
    video_title = title if title else ""
    if not video_title and video_path:
        video_title = Path(video_path).stem.replace("_", " ")

    logger.info("Annotating: srt=%s, frames=%s → %s", srt_path, frames_dir, annotation_path)
    annotation_path = annotate_lecture(
        srt_path=srt_path,
        frames_dir=frames_dir or "",
        output_path=annotation_path,
        video_title=video_title,
        model=annotate_model,
        api_key=api_key,
        base_url=LLM_BASE_URL,
        video_path=video_path,
        video_url=url,
        transcript_segments=transcript_segments,
    )
    result["annotation"] = annotation_path
    result["success"] = True
    logger.info("  ✅ Annotation: %s", annotation_path)

    elapsed = time.time() - t0
    logger.info("🎉 Pipeline complete in %.1fs", elapsed)
    logger.info("   Output directory: %s", output_dir)

    return result
