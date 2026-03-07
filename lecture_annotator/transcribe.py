"""
transcribe.py — Whisper ASR transcription to SRT subtitles.

Supports both ``openai-whisper`` and ``faster-whisper`` as backends.
Automatically detects which is installed and falls back gracefully.

Usage:
    from lecture_annotator.transcribe import transcribe_audio

    srt_path = transcribe_audio("/tmp/output/lecture.wav", "/tmp/output")
    print(srt_path)  # /tmp/output/lecture.srt
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Backend detection
# ---------------------------------------------------------------------------

_BACKEND: Optional[str] = None  # "openai-whisper" | "faster-whisper" | None

try:
    import whisper as _openai_whisper  # noqa: F401
    _BACKEND = "openai-whisper"
    logger.debug("openai-whisper backend available")
except ImportError:
    _openai_whisper = None  # type: ignore[assignment]

if _BACKEND is None:
    try:
        from faster_whisper import WhisperModel as _FasterWhisperModel  # noqa: F401
        _BACKEND = "faster-whisper"
        logger.debug("faster-whisper backend available")
    except ImportError:
        _FasterWhisperModel = None  # type: ignore[assignment, misc]


def _check_backend() -> str:
    """Ensure at least one Whisper backend is importable.

    Returns:
        Name of the available backend.

    Raises:
        ImportError: If neither ``openai-whisper`` nor ``faster-whisper`` is installed.
    """
    if _BACKEND is None:
        raise ImportError(
            "Neither openai-whisper nor faster-whisper is installed.\n"
            "Install one of them:\n"
            "  pip install openai-whisper          # official OpenAI Whisper\n"
            "  pip install faster-whisper           # CTranslate2-based, lower VRAM\n"
        )
    return _BACKEND


# ---------------------------------------------------------------------------
# SRT formatting helpers
# ---------------------------------------------------------------------------

def _format_ts(seconds: float) -> str:
    """Format a timestamp in SRT format (HH:MM:SS,mmm).

    Args:
        seconds: Time in seconds.

    Returns:
        SRT-formatted timestamp string.
    """
    if seconds < 0:
        raise ValueError(f"Negative timestamp: {seconds}")
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _segments_to_srt(segments: list[dict]) -> str:
    """Convert a list of segment dicts to SRT string.

    Each segment dict must have keys: ``start``, ``end``, ``text``.

    Args:
        segments: List of transcription segments.

    Returns:
        Complete SRT-formatted string.
    """
    lines: list[str] = []
    for idx, seg in enumerate(segments, start=1):
        start = _format_ts(seg["start"])
        end = _format_ts(seg["end"])
        text = seg["text"].strip()
        lines.append(f"{idx}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# OpenAI-Whisper backend
# ---------------------------------------------------------------------------

def _transcribe_openai_whisper(
    audio_path: Path,
    *,
    language: Optional[str],
    model_size: str,
) -> list[dict]:
    """Transcribe using the official openai-whisper library.

    Args:
        audio_path: Path to 16 kHz mono WAV.
        language: ISO 639-1 language code, or None for auto-detect.
        model_size: Whisper model name (e.g. 'large-v3', 'base').

    Returns:
        List of segment dicts with keys: start, end, text.
    """
    import whisper  # type: ignore[import-untyped]

    logger.info("Loading openai-whisper model '%s' …", model_size)
    model = whisper.load_model(model_size)

    transcribe_kwargs: dict = {
        "verbose": True,  # progress display
    }
    if language:
        transcribe_kwargs["language"] = language

    logger.info("Transcribing %s …", audio_path.name)
    result = model.transcribe(str(audio_path), **transcribe_kwargs)

    detected_lang = result.get("language", "unknown")
    logger.info("Detected language: %s", detected_lang)

    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "start": float(seg["start"]),
            "end": float(seg["end"]),
            "text": seg["text"],
        })
    return segments


# ---------------------------------------------------------------------------
# Faster-Whisper backend
# ---------------------------------------------------------------------------

def _transcribe_faster_whisper(
    audio_path: Path,
    *,
    language: Optional[str],
    model_size: str,
) -> list[dict]:
    """Transcribe using faster-whisper (CTranslate2).

    Args:
        audio_path: Path to 16 kHz mono WAV.
        language: ISO 639-1 language code, or None for auto-detect.
        model_size: Whisper model name (e.g. 'large-v3', 'base').

    Returns:
        List of segment dicts with keys: start, end, text.
    """
    from faster_whisper import WhisperModel  # type: ignore[import-untyped]

    logger.info("Loading faster-whisper model '%s' …", model_size)
    model = WhisperModel(model_size, device="auto", compute_type="auto")

    transcribe_kwargs: dict = {}
    if language:
        transcribe_kwargs["language"] = language

    logger.info("Transcribing %s …", audio_path.name)
    raw_segments, info = model.transcribe(str(audio_path), **transcribe_kwargs)

    logger.info("Detected language: %s (prob=%.2f)", info.language, info.language_probability)

    segments = []
    for seg in raw_segments:
        segments.append({
            "start": float(seg.start),
            "end": float(seg.end),
            "text": seg.text,
        })
        # Progress: log every segment as it comes
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("[%.1f–%.1f] %s", seg.start, seg.end, seg.text.strip())
    return segments


# ---------------------------------------------------------------------------
# Model size fallback logic
# ---------------------------------------------------------------------------

_MODEL_FALLBACK_CHAIN = ["large-v3", "medium", "small", "base", "tiny"]


def _resolve_model_size(requested: str) -> str:
    """Validate and potentially adjust the requested model size.

    For faster-whisper, all standard sizes are supported.
    For openai-whisper, 'large-v3' maps to the latest large checkpoint.

    Args:
        requested: Requested model size string.

    Returns:
        The model size to use (unchanged in most cases).
    """
    # Accept as-is; the underlying library will raise if invalid
    return requested


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transcribe_audio(
    audio_path: str | Path,
    output_dir: str | Path,
    *,
    language: Optional[str] = None,
    model_size: str = "large-v3",
) -> str:
    """Transcribe an audio file to SRT subtitles using Whisper.

    Automatically selects between ``openai-whisper`` and ``faster-whisper``
    depending on what is installed. If neither is available, raises
    ``ImportError`` with installation instructions.

    Args:
        audio_path: Path to the input audio file (WAV recommended,
                    16 kHz mono for best results).
        output_dir: Directory where the ``.srt`` file will be written.
        language: ISO 639-1 language code (``"zh"``, ``"en"``, etc.).
                  ``None`` for automatic detection.
        model_size: Whisper model to use. Common values:
                    ``"large-v3"`` (best quality, ~10 GB VRAM),
                    ``"medium"`` (~5 GB), ``"small"`` (~2 GB),
                    ``"base"`` (~1 GB), ``"tiny"`` (~400 MB).
                    Defaults to ``"large-v3"``.

    Returns:
        Absolute path to the generated ``.srt`` file as a string.

    Raises:
        ImportError: If no Whisper backend is installed.
        FileNotFoundError: If the audio file does not exist.
        RuntimeError: If transcription fails.

    Example::

        srt = transcribe_audio("/tmp/lecture.wav", "/tmp/output", language="zh")
        print(srt)  # /tmp/output/lecture.srt
    """
    backend = _check_backend()
    logger.info("Using backend: %s", backend)

    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model_size = _resolve_model_size(model_size)

    # --- Transcribe ---
    try:
        if backend == "openai-whisper":
            segments = _transcribe_openai_whisper(
                audio_path, language=language, model_size=model_size,
            )
        else:
            segments = _transcribe_faster_whisper(
                audio_path, language=language, model_size=model_size,
            )
    except Exception as exc:
        logger.error("Transcription failed: %s", exc)
        raise RuntimeError(f"Transcription failed: {exc}") from exc

    if not segments:
        logger.warning("No speech segments detected in %s", audio_path.name)

    logger.info("Transcribed %d segments", len(segments))

    # --- Write SRT ---
    srt_content = _segments_to_srt(segments)
    srt_path = output_dir / (audio_path.stem + ".srt")
    srt_path.write_text(srt_content, encoding="utf-8")
    logger.info("SRT written to %s (%d bytes)", srt_path, srt_path.stat().st_size)

    return str(srt_path.resolve())


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Transcribe audio to SRT via Whisper")
    parser.add_argument("audio", help="Path to input audio file (WAV)")
    parser.add_argument("-o", "--output-dir", default=".", help="Output directory for SRT")
    parser.add_argument("-l", "--language", default=None, help="Language code (zh, en, …)")
    parser.add_argument("-m", "--model", default="large-v3",
                        help="Whisper model size (large-v3, medium, small, base, tiny)")
    args = parser.parse_args()

    try:
        srt = transcribe_audio(args.audio, args.output_dir,
                               language=args.language, model_size=args.model)
        print(f"SRT saved: {srt}")
    except Exception as exc:
        logger.error("Failed: %s", exc)
        sys.exit(1)
