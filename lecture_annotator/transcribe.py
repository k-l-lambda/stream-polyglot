"""
transcribe.py — ASR transcription to SRT subtitles.

Backends (in priority order):
  1. m4t API  — SeamlessM4T via local Docker service (fastest, no model download)
  2. openai-whisper — official OpenAI library
  3. faster-whisper — CTranslate2-based

Usage:
    from lecture_annotator.transcribe import transcribe_audio

    # Use m4t API (preferred)
    srt_path = transcribe_audio("/tmp/output/lecture.wav", "/tmp/output",
                                m4t_api_url="http://localhost:8001")

    # Use Whisper (fallback)
    srt_path = transcribe_audio("/tmp/output/lecture.wav", "/tmp/output")
    print(srt_path)  # /tmp/output/lecture.srt
"""

from __future__ import annotations

import logging
import math
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import requests

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
# m4t API backend
# ---------------------------------------------------------------------------

_M4T_CHUNK_SECS = 60.0  # split long audio into chunks for m4t

# Map ISO 639-1 codes to m4t language codes (Flores-200 / ISO 639-3)
_LANG_TO_M4T = {
    "zh": "cmn",
    "en": "eng",
    "ja": "jpn",
    "ko": "kor",
    "fr": "fra",
    "de": "deu",
    "es": "spa",
    "ru": "rus",
    "ar": "arb",
    "pt": "por",
}


def _probe_duration(audio_path: Path) -> float:
    """Get audio duration via ffprobe."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_entries", "format=duration", str(audio_path)],
            capture_output=True, text=True, timeout=30,
        )
        import json
        return float(json.loads(r.stdout).get("format", {}).get("duration", 0))
    except Exception:
        return 0.0


def _split_audio_chunk(audio_path: Path, start: float, duration: float, out_path: Path) -> bool:
    """Cut a chunk from audio using ffmpeg."""
    r = subprocess.run(
        ["ffmpeg", "-y", "-ss", str(start), "-t", str(duration),
         "-i", str(audio_path), "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
         str(out_path)],
        capture_output=True, timeout=60,
    )
    return r.returncode == 0


def _transcribe_chunk_m4t(chunk_path: Path, api_url: str, language: Optional[str]) -> dict:
    """Call m4t /v1/transcribe on one chunk, return result dict."""
    m4t_lang = _LANG_TO_M4T.get(language, language) if language else "cmn"
    with open(chunk_path, "rb") as f:
        resp = requests.post(
            f"{api_url.rstrip('/')}/v1/transcribe",
            files={"audio": ("chunk.wav", f, "audio/wav")},
            data={"language": m4t_lang},
            timeout=300,
        )
    resp.raise_for_status()
    result = resp.json()
    # m4t returns {"output_text": "...", "input_duration": ..., ...}
    return result


def _transcribe_m4t(
    audio_path: Path,
    *,
    language: Optional[str],
    api_url: str,
) -> list[dict]:
    """Transcribe via m4t API using VAD-based sentence segmentation.

    Reuses the project's existing audio_timeline.segment_with_timeline()
    for VAD-based speech detection, then transcribes each speech fragment
    via m4t /v1/transcribe. This produces SRT entries aligned to natural
    sentence/phrase boundaries instead of arbitrary fixed-time chunks.

    Falls back to fixed-chunk splitting if audio_timeline is unavailable
    or VAD fails.
    """
    duration = _probe_duration(audio_path)
    if duration <= 0:
        duration = _M4T_CHUNK_SECS

    # Try VAD-based segmentation (reuse project's existing module)
    try:
        # Import from the project root (audio_timeline.py)
        import sys as _sys
        _project_root = str(Path(__file__).resolve().parent.parent)
        if _project_root not in _sys.path:
            _sys.path.insert(0, _project_root)
        from audio_timeline import segment_with_timeline

        logger.info("m4t: using VAD segmentation (audio_timeline) for %s (%.1fs)", audio_path.name, duration)

        with tempfile.TemporaryDirectory() as vad_tmpdir:
            timeline, metadata = segment_with_timeline(
                str(audio_path), vad_tmpdir,
                chunk_duration=30.0,
                m4t_api_url=api_url,
                save_timeline=False,
            )
            logger.info("VAD: %d speech segments detected", len(timeline))

            if not timeline:
                logger.warning("VAD returned no segments, falling back to fixed chunks")
                return _transcribe_m4t_fixed_chunks(audio_path, language=language, api_url=api_url, duration=duration)

            # Transcribe each VAD fragment
            segments: list[dict] = []
            for i, frag in enumerate(timeline):
                frag_path = Path(vad_tmpdir) / frag["file"]
                if not frag_path.exists():
                    logger.warning("Fragment %d missing: %s", i, frag["file"])
                    continue

                logger.info(
                    "Transcribing %d/%d (%.1f–%.1fs) …",
                    i + 1, len(timeline), frag["start"], frag["end"],
                )
                try:
                    result = _transcribe_chunk_m4t(frag_path, api_url, language)
                except Exception as exc:
                    logger.warning("Segment %d/%d transcription failed: %s", i + 1, len(timeline), exc)
                    continue

                text = result.get("output_text", "").strip()
                if text:
                    segments.append({
                        "start": frag["start"],
                        "end": frag["end"],
                        "text": text,
                    })

            logger.info("m4t (VAD): %d transcribed segments from %d fragments", len(segments), len(timeline))
            return segments

    except ImportError:
        logger.info("audio_timeline not importable, falling back to fixed-chunk splitting")
    except Exception as exc:
        logger.warning("VAD segmentation failed (%s), falling back to fixed chunks", exc)

    return _transcribe_m4t_fixed_chunks(audio_path, language=language, api_url=api_url, duration=duration)


def _transcribe_m4t_fixed_chunks(
    audio_path: Path,
    *,
    language: Optional[str],
    api_url: str,
    duration: float,
) -> list[dict]:
    """Fallback: transcribe via m4t with fixed-size chunk splitting."""
    num_chunks = max(1, math.ceil(duration / _M4T_CHUNK_SECS))
    logger.info("m4t fixed-chunk: %s (%.1fs, %d chunks)", audio_path.name, duration, num_chunks)

    segments: list[dict] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(num_chunks):
            start = i * _M4T_CHUNK_SECS
            chunk_path = Path(tmpdir) / f"chunk_{i:04d}.wav"
            ok = _split_audio_chunk(audio_path, start, _M4T_CHUNK_SECS, chunk_path)
            if not ok or not chunk_path.exists():
                logger.warning("Chunk %d/%d: ffmpeg split failed, skipping", i + 1, num_chunks)
                continue

            logger.info("Chunk %d/%d (%.0f–%.0fs) …", i + 1, num_chunks, start, start + _M4T_CHUNK_SECS)
            try:
                result = _transcribe_chunk_m4t(chunk_path, api_url, language)
            except Exception as exc:
                logger.warning("Chunk %d/%d failed: %s", i + 1, num_chunks, exc)
                continue

            text = result.get("output_text", "").strip()
            if text:
                chunk_duration = result.get("input_duration") or _M4T_CHUNK_SECS
                segments.append({
                    "start": start,
                    "end": min(start + chunk_duration, duration),
                    "text": text,
                })

    logger.info("m4t (fixed): %d total segments", len(segments))
    return segments


def check_m4t_health(api_url: str, timeout: float = 5.0) -> bool:
    """Return True if the m4t API is healthy."""
    try:
        r = requests.get(f"{api_url.rstrip('/')}/health", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


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
    m4t_api_url: Optional[str] = None,
) -> str:
    """Transcribe an audio file to SRT subtitles.

    Backend priority:
      1. m4t API (if ``m4t_api_url`` is given and the service is healthy)
      2. openai-whisper (if installed)
      3. faster-whisper (if installed)

    If m4t_api_url is not given, falls back to Whisper automatically.

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
    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Choose backend ---
    use_m4t = False
    if m4t_api_url:
        if check_m4t_health(m4t_api_url):
            use_m4t = True
            logger.info("Using backend: m4t API (%s)", m4t_api_url)
        else:
            logger.warning("m4t API not reachable at %s, falling back to Whisper", m4t_api_url)

    if not use_m4t:
        backend = _check_backend()
        logger.info("Using backend: %s", backend)

    model_size = _resolve_model_size(model_size)

    # --- Transcribe ---
    try:
        if use_m4t:
            segments = _transcribe_m4t(audio_path, language=language, api_url=m4t_api_url)
        elif backend == "openai-whisper":
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
