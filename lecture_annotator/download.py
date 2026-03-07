"""
download.py — YouTube video downloader using yt-dlp.

Downloads video (mp4, ≤720p) and extracts audio (16kHz mono WAV) for ASR.
Handles YouTube bot-detection / IP blocks with cookie and proxy fallback.

Usage:
    from lecture_annotator.download import download_video

    result = download_video("https://www.youtube.com/watch?v=...", "/tmp/output")
    print(result)
    # {'video': PosixPath('/tmp/output/...mp4'),
    #  'audio': PosixPath('/tmp/output/...wav'),
    #  'title': '...', 'duration': 123.4}
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default cookie path used by yt-dlp / browser export tools
_DEFAULT_COOKIES = Path.home() / ".config" / "yt-dlp" / "cookies.txt"

# yt-dlp binary — resolved from PATH at import time (may be None)
_YTDLP_BIN = shutil.which("yt-dlp")
_FFMPEG_BIN = shutil.which("ffmpeg") or "ffmpeg"


def _run(cmd: list[str], *, desc: str = "") -> subprocess.CompletedProcess:
    """Run a subprocess, log it, and raise on failure.

    Args:
        cmd: Command and arguments.
        desc: Human-readable description for log messages.

    Returns:
        CompletedProcess on success.

    Raises:
        RuntimeError: If the process exits with non-zero status.
    """
    logger.info("Running%s: %s", f" ({desc})" if desc else "", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("Command failed (rc=%d): %s\nstderr: %s",
                      result.returncode, " ".join(cmd), result.stderr.strip())
        raise RuntimeError(
            f"{desc or 'Command'} failed (rc={result.returncode}): {result.stderr.strip()}"
        )
    return result


def _sanitize_filename(title: str) -> str:
    """Turn a video title into a safe filename fragment.

    Args:
        title: Raw title string.

    Returns:
        Sanitized string suitable for use in filenames.
    """
    title = re.sub(r'[\\/:*?"<>|]', "_", title)
    title = re.sub(r"\s+", "_", title.strip())
    return title[:120]  # cap length


def _probe_duration(filepath: Path) -> float:
    """Get media duration in seconds via ffprobe.

    Args:
        filepath: Path to a media file.

    Returns:
        Duration in seconds, or 0.0 on failure.
    """
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", str(filepath)],
            capture_output=True, text=True,
        )
        info = json.loads(r.stdout)
        return float(info.get("format", {}).get("duration", 0))
    except Exception as exc:
        logger.warning("ffprobe failed for %s: %s", filepath, exc)
        return 0.0


def _fetch_metadata(url: str, extra_args: list[str] | None = None) -> dict:
    """Fetch video metadata without downloading.

    Args:
        url: YouTube video URL.
        extra_args: Additional yt-dlp arguments (cookies, proxy, etc.).

    Returns:
        Parsed JSON metadata dict.

    Raises:
        RuntimeError: If metadata extraction fails.
    """
    cmd = [
        _YTDLP_BIN, "--dump-json", "--no-playlist",
        *(extra_args or []),
        url,
    ]
    result = _run(cmd, desc="fetch metadata")
    return json.loads(result.stdout)


def _build_ytdlp_args(
    url: str,
    output_template: str,
    *,
    cookies: Optional[str | Path] = None,
    proxy: Optional[str] = None,
) -> list[str]:
    """Build the base yt-dlp argument list.

    Args:
        url: YouTube video URL.
        output_template: yt-dlp output template string.
        cookies: Path to a Netscape cookies file.
        proxy: Proxy URL (e.g. socks5://127.0.0.1:1080).

    Returns:
        List of command-line arguments.
    """
    cmd = [
        _YTDLP_BIN,
        "--no-playlist",
        "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", output_template,
        "--no-overwrites",
    ]
    if cookies:
        cmd.extend(["--cookies", str(cookies)])
    if proxy:
        cmd.extend(["--proxy", proxy])
    cmd.append(url)
    return cmd


def _attempt_download(
    url: str,
    output_template: str,
    *,
    cookies: Optional[str | Path] = None,
    proxy: Optional[str] = None,
) -> subprocess.CompletedProcess:
    """Attempt a yt-dlp download, with automatic cookie fallback.

    Strategy:
      1. Try without cookies (unless explicitly provided).
      2. On 403 / bot-detection failure, retry with default cookie file if available.

    Args:
        url: YouTube video URL.
        output_template: yt-dlp output template string.
        cookies: Explicit cookie file path (skips fallback logic).
        proxy: Proxy URL.

    Returns:
        CompletedProcess of the successful download.

    Raises:
        RuntimeError: If all attempts fail.
    """
    # --- First attempt ---
    cmd = _build_ytdlp_args(url, output_template, cookies=cookies, proxy=proxy)
    logger.info("Download attempt 1 (cookies=%s, proxy=%s)", cookies or "none", proxy or "none")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        return result

    stderr = result.stderr.lower()
    is_bot_block = any(kw in stderr for kw in ("403", "forbidden", "bot", "sign in", "confirm"))

    # --- Cookie fallback (only if no explicit cookies were given) ---
    if is_bot_block and cookies is None and _DEFAULT_COOKIES.is_file():
        logger.warning("Blocked by YouTube — retrying with cookies from %s", _DEFAULT_COOKIES)
        cmd = _build_ytdlp_args(url, output_template, cookies=_DEFAULT_COOKIES, proxy=proxy)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return result

    # All attempts failed
    raise RuntimeError(
        f"yt-dlp download failed after retries.\n"
        f"Last stderr: {result.stderr.strip()}"
    )


def _extract_audio(video_path: Path, audio_path: Path) -> Path:
    """Extract 16 kHz mono WAV audio from a video file using ffmpeg.

    Args:
        video_path: Path to the source video.
        audio_path: Desired output WAV path.

    Returns:
        The audio_path on success.

    Raises:
        RuntimeError: If ffmpeg fails.
    """
    cmd = [
        _FFMPEG_BIN,
        "-y",               # overwrite
        "-i", str(video_path),
        "-vn",              # no video
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(audio_path),
    ]
    _run(cmd, desc="extract audio")
    return audio_path


def download_video(
    url: str,
    output_dir: str | Path,
    *,
    cookies: Optional[str | Path] = None,
    proxy: Optional[str] = None,
) -> dict:
    """Download a YouTube video and extract 16 kHz mono WAV audio.

    Args:
        url: YouTube video URL.
        output_dir: Directory to save downloaded files into (created if absent).
        cookies: Path to a Netscape-format cookies.txt file.
                 If None and the first download attempt is blocked,
                 ``~/.config/yt-dlp/cookies.txt`` is used automatically
                 when present.
        proxy: Proxy URL (e.g. ``http://127.0.0.1:7890`` or
               ``socks5://127.0.0.1:1080``).

    Returns:
        dict with keys:
            - ``video``   — ``pathlib.Path`` to the downloaded MP4
            - ``audio``   — ``pathlib.Path`` to the extracted 16 kHz WAV
            - ``title``   — ``str`` video title
            - ``duration``— ``float`` duration in seconds

    Raises:
        FileNotFoundError: If yt-dlp binary is not found.
        RuntimeError: If download or audio extraction fails.

    Example::

        result = download_video(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "/tmp/lectures",
        )
        print(result["video"])   # /tmp/lectures/Never_Gonna_Give_You_Up.mp4
        print(result["audio"])   # /tmp/lectures/Never_Gonna_Give_You_Up.wav
    """
    # Validate yt-dlp is available
    if not _YTDLP_BIN:
        raise FileNotFoundError(
            "yt-dlp not found on PATH. Install with: pip install yt-dlp"
        )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Fetch metadata to get the title ---
    extra = []
    if cookies:
        extra.extend(["--cookies", str(cookies)])
    if proxy:
        extra.extend(["--proxy", proxy])

    logger.info("Fetching metadata for %s …", url)
    try:
        meta = _fetch_metadata(url, extra_args=extra)
    except RuntimeError:
        # Metadata fetch may also be blocked; try with default cookies
        if cookies is None and _DEFAULT_COOKIES.is_file():
            logger.warning("Metadata fetch failed — retrying with cookies")
            extra.extend(["--cookies", str(_DEFAULT_COOKIES)])
            meta = _fetch_metadata(url, extra_args=extra)
        else:
            raise

    title = meta.get("title", "untitled")
    safe_title = _sanitize_filename(title)
    logger.info("Video title: %s  (safe: %s)", title, safe_title)

    # --- Download video ---
    video_template = str(output_dir / f"{safe_title}.%(ext)s")
    _attempt_download(url, video_template, cookies=cookies, proxy=proxy)

    # Find the downloaded mp4
    candidates = sorted(output_dir.glob(f"{safe_title}.*mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        # Fallback: any recently created mp4
        candidates = sorted(output_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError(f"Download appeared to succeed but no mp4 found in {output_dir}")

    video_path = candidates[0]
    logger.info("Downloaded video: %s", video_path)

    # --- Extract audio ---
    audio_path = video_path.with_suffix(".wav")
    _extract_audio(video_path, audio_path)
    logger.info("Extracted audio: %s", audio_path)

    # --- Duration ---
    duration = _probe_duration(video_path)

    return {
        "video": str(video_path),
        "audio": str(audio_path),
        "title": title,
        "duration": duration,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Download YouTube video + extract audio")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("-o", "--output-dir", default=".", help="Output directory")
    parser.add_argument("--cookies", help="Path to cookies.txt")
    parser.add_argument("--proxy", help="Proxy URL")
    args = parser.parse_args()

    try:
        result = download_video(args.url, args.output_dir, cookies=args.cookies, proxy=args.proxy)
        print(json.dumps({k: str(v) for k, v in result.items()}, indent=2, ensure_ascii=False))
    except Exception as exc:
        logger.error("Failed: %s", exc)
        sys.exit(1)
