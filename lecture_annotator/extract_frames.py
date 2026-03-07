"""
extract_frames — Key frame extraction from lecture videos.

Strategies:
  1. semantic  — SRT-driven: extract frames at moments with formulae, theorems,
                 transitions, or long pauses (requires srt_path).
  2. uniform   — Every N seconds (fallback, no SRT needed).
  3. scene     — ffmpeg scene-change detection.

Usage:
    frames = extract_key_frames("lecture.mp4", "out/", srt_path="lecture.srt")
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from .srt_utils import parse_srt_file as _parse_srt_shared

logger = logging.getLogger(__name__)


def _parse_srt(path: str) -> list[dict]:
    """
    Parse an SRT file using the shared srt_utils parser.

    Returns list of dicts:
        [{'index': int, 'start': float, 'end': float, 'text': str}, ...]
    """
    entries = _parse_srt_shared(path)
    # Strip HTML tags from text for consistency with the original implementation
    for e in entries:
        e["text"] = re.sub(r"<[^>]+>", "", e["text"]).strip()
    entries.sort(key=lambda e: e["start"])
    return entries


# ---------------------------------------------------------------------------
# Keyword sets for semantic detection
# ---------------------------------------------------------------------------

_FORMULA_KEYWORDS = re.compile(
    r"公式|定理|证明|equation|formula|theorem|proof|define|定义|推导",
    re.IGNORECASE,
)

_TRANSITION_KEYWORDS = re.compile(
    r"总结|结论|conclusion|therefore|所以|这说明",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Frame extraction helpers
# ---------------------------------------------------------------------------


def _sanitize_reason(reason: str) -> str:
    """Make reason safe for use in filenames."""
    return re.sub(r"[^a-zA-Z0-9_\u4e00-\u9fff]", "", reason)[:20]


def _frame_filename(time_secs: float, reason: str) -> str:
    return f"frame_{time_secs:08.1f}_{_sanitize_reason(reason)}.jpg"


def _extract_single_frame(
    video_path: str, time_secs: float, output_path: str
) -> bool:
    """Extract a single frame at *time_secs* using ffmpeg. Returns True on success."""
    cmd = [
        "ffmpeg",
        "-y",
        "-ss", f"{time_secs:.3f}",
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        output_path,
    ]
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=True,
        )
        return os.path.isfile(output_path) and os.path.getsize(output_path) > 0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        logger.warning("ffmpeg failed for t=%.1f: %s", time_secs, exc)
        return False


def _get_video_duration(video_path: str) -> float:
    """Return video duration in seconds via ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.PIPE, timeout=15)
        return float(out.strip())
    except Exception as exc:
        logger.warning("ffprobe duration failed: %s — falling back to 0", exc)
        return 0.0


# ---------------------------------------------------------------------------
# Strategy implementations
# ---------------------------------------------------------------------------


def _strategy_semantic(
    video_path: str,
    output_dir: str,
    srt_path: str,
    max_frames: int,
) -> list[dict]:
    """Extract frames at semantically important moments identified from SRT."""
    if not srt_path or not os.path.isfile(srt_path):
        raise FileNotFoundError(f"SRT file not found: {srt_path}")

    entries = _parse_srt(srt_path)
    if not entries:
        logger.warning("SRT file is empty or unparseable: %s", srt_path)
        return []

    candidates: list[dict] = []

    for i, entry in enumerate(entries):
        reasons: list[str] = []
        text = entry["text"]

        if _FORMULA_KEYWORDS.search(text):
            reasons.append("formula")
        if _TRANSITION_KEYWORDS.search(text):
            reasons.append("transition")

        # Gap detection: >3 s silence before this subtitle
        if i > 0:
            gap = entry["start"] - entries[i - 1]["end"]
            if gap > 3.0:
                reasons.append("paragraph")

        if reasons:
            candidates.append(
                {
                    "time": entry["start"],
                    "subtitle": text,
                    "reason": "+".join(reasons),
                }
            )

    # De-duplicate: keep at most one frame per 5-second window
    filtered: list[dict] = []
    last_t = -999.0
    for c in candidates:
        if c["time"] - last_t >= 5.0:
            filtered.append(c)
            last_t = c["time"]

    # Trim to max_frames
    if len(filtered) > max_frames:
        # Evenly sample from candidates
        step = len(filtered) / max_frames
        filtered = [filtered[int(i * step)] for i in range(max_frames)]

    logger.info(
        "Semantic strategy: %d candidates → %d after dedup/trim (from %d subtitles)",
        len(candidates),
        len(filtered),
        len(entries),
    )

    results: list[dict] = []
    for idx, c in enumerate(filtered, 1):
        fname = _frame_filename(c["time"], c["reason"])
        out_path = os.path.join(output_dir, fname)
        logger.info(
            "[%d/%d] Extracting frame at %.1fs — %s",
            idx, len(filtered), c["time"], c["reason"],
        )
        if _extract_single_frame(video_path, c["time"], out_path):
            results.append(
                {
                    "time": c["time"],
                    "path": out_path,
                    "subtitle": c["subtitle"],
                    "reason": c["reason"],
                }
            )
        else:
            logger.warning("  ↳ skipped (ffmpeg failure)")

    return results


def _strategy_uniform(
    video_path: str,
    output_dir: str,
    interval_secs: float,
    max_frames: int,
) -> list[dict]:
    """Extract one frame every *interval_secs* seconds."""
    duration = _get_video_duration(video_path)
    if duration <= 0:
        logger.error("Cannot determine video duration for %s", video_path)
        return []

    times = []
    t = 0.0
    while t < duration:
        times.append(t)
        t += interval_secs
    if len(times) > max_frames:
        times = times[:max_frames]

    logger.info(
        "Uniform strategy: %d frames, interval=%.1fs, duration=%.1fs",
        len(times), interval_secs, duration,
    )

    results: list[dict] = []
    for idx, t in enumerate(times, 1):
        fname = _frame_filename(t, "uniform")
        out_path = os.path.join(output_dir, fname)
        logger.info("[%d/%d] Extracting frame at %.1fs", idx, len(times), t)
        if _extract_single_frame(video_path, t, out_path):
            results.append(
                {
                    "time": t,
                    "path": out_path,
                    "subtitle": "",
                    "reason": "uniform",
                }
            )

    return results


def _strategy_scene(
    video_path: str,
    output_dir: str,
    max_frames: int,
    threshold: float = 0.3,
) -> list[dict]:
    """Detect scene changes via ffmpeg and extract those frames."""
    # Step 1: detect scene-change timestamps
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vf", f"select='gt(scene,{threshold})',showinfo",
        "-vsync", "vfr",
        "-f", "null",
        "-",
    ]
    logger.info("Running scene detection (threshold=%.2f) …", threshold)
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=600,
            text=True,
        )
        stderr = proc.stderr
    except subprocess.TimeoutExpired:
        logger.error("Scene detection timed out (10 min limit)")
        return []

    # Parse showinfo lines for pts_time
    pts_re = re.compile(r"pts_time:\s*([\d.]+)")
    times: list[float] = []
    for m in pts_re.finditer(stderr):
        times.append(float(m[1]))

    # De-duplicate within 2-second windows
    deduped: list[float] = []
    last = -999.0
    for t in sorted(times):
        if t - last >= 2.0:
            deduped.append(t)
            last = t

    if len(deduped) > max_frames:
        step = len(deduped) / max_frames
        deduped = [deduped[int(i * step)] for i in range(max_frames)]

    logger.info(
        "Scene strategy: %d raw detections → %d after dedup/trim",
        len(times), len(deduped),
    )

    # Step 2: extract frames
    results: list[dict] = []
    for idx, t in enumerate(deduped, 1):
        fname = _frame_filename(t, "scene")
        out_path = os.path.join(output_dir, fname)
        logger.info("[%d/%d] Extracting scene frame at %.1fs", idx, len(deduped), t)
        if _extract_single_frame(video_path, t, out_path):
            results.append(
                {
                    "time": t,
                    "path": out_path,
                    "subtitle": "",
                    "reason": "scene",
                }
            )

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_key_frames(
    video_path: str,
    output_dir: str,
    srt_path: Optional[str] = None,
    interval_secs: float = 60,
    strategy: str = "semantic",
    max_frames: int = 50,
) -> list[dict]:
    """
    Extract key frames from a lecture video.

    Args:
        video_path:     Path to the input video file.
        output_dir:     Directory to save extracted frame images.
        srt_path:       Path to SRT subtitle file (required for 'semantic').
        interval_secs:  Interval in seconds for 'uniform' strategy.
        strategy:       One of 'semantic', 'uniform', 'scene'.
        max_frames:     Maximum number of frames to extract.

    Returns:
        List of dicts, each containing:
            time     — timestamp in seconds
            path     — absolute path to the saved JPEG
            subtitle — subtitle text at that moment (if available)
            reason   — why this frame was selected
    """
    video_path = os.path.abspath(video_path)
    output_dir = os.path.abspath(output_dir)

    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    os.makedirs(output_dir, exist_ok=True)

    logger.info(
        "extract_key_frames: video=%s strategy=%s max_frames=%d",
        video_path, strategy, max_frames,
    )

    if strategy == "semantic":
        if not srt_path:
            logger.warning(
                "Semantic strategy requested but no srt_path — falling back to uniform"
            )
            return _strategy_uniform(video_path, output_dir, interval_secs, max_frames)
        return _strategy_semantic(video_path, output_dir, srt_path, max_frames)

    elif strategy == "uniform":
        return _strategy_uniform(video_path, output_dir, interval_secs, max_frames)

    elif strategy == "scene":
        return _strategy_scene(video_path, output_dir, max_frames)

    else:
        raise ValueError(
            f"Unknown strategy {strategy!r} — choose 'semantic', 'uniform', or 'scene'"
        )
