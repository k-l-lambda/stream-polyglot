"""
SRT Subtitle Utilities (local copy for lecture_annotator package)

Provides functions for parsing and formatting SRT (SubRip Text) subtitle files.
Supports both `,` and `.` as millisecond separator:
    00:00:01,000  (standard SRT)
    00:00:01.000  (alternative)
"""

from __future__ import annotations

import math
import re
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------------

def parse_srt_timestamp(timestamp: str) -> float:
    """Parse an SRT timestamp (HH:MM:SS,mmm or HH:MM:SS.mmm) to seconds.

    Args:
        timestamp: SRT timestamp string.

    Returns:
        Time in seconds as a float.

    Raises:
        ValueError: If the timestamp format is invalid.

    Examples:
        >>> parse_srt_timestamp("00:00:04,354")
        4.354
        >>> parse_srt_timestamp("00:00:04.354")
        4.354
        >>> parse_srt_timestamp("00:02:05,678")
        125.678
    """
    # Accept both comma and dot as millisecond separator
    match = re.match(r'(\d+):(\d+):(\d+)[,.](\d+)', timestamp.strip())
    if not match:
        raise ValueError(f"Invalid SRT timestamp format: {timestamp!r}")
    hours, minutes, seconds, milliseconds = map(int, match.groups())
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0


def format_srt_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format: HH:MM:SS,mmm.

    Args:
        seconds: Time in seconds (non-negative float).

    Returns:
        Formatted timestamp string, e.g. ``"00:00:04,354"``.

    Examples:
        >>> format_srt_timestamp(4.354)
        '00:00:04,354'
        >>> format_srt_timestamp(125.678)
        '00:02:05,678'
    """
    if seconds < 0:
        seconds = 0.0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int(round((seconds % 1) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"


# ---------------------------------------------------------------------------
# SRT file parsing
# ---------------------------------------------------------------------------

def parse_srt_file(srt_path: str) -> List[Dict]:
    """Parse an SRT subtitle file.

    Handles both ``,`` and ``.`` as millisecond separators.

    Args:
        srt_path: Path to the SRT file.

    Returns:
        List of subtitle dicts with keys: ``index``, ``start``, ``end``, ``text``.
        For bilingual subtitles, ``text`` contains both languages separated by ``\\n``.
    """
    with open(srt_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    subtitles: List[Dict] = []
    entries = re.split(r'\n\n+', content.strip())

    for entry in entries:
        if not entry.strip():
            continue
        lines = entry.strip().split('\n')
        if len(lines) < 3:
            continue

        try:
            index = int(lines[0].strip())
            timestamp_line = lines[1].strip()
            match = re.match(r'(.+?)\s*-->\s*(.+)', timestamp_line)
            if not match:
                continue
            start_ts, end_ts = match.groups()
            start = parse_srt_timestamp(start_ts.strip())
            end = parse_srt_timestamp(end_ts.strip())
            text = '\n'.join(lines[2:])
            subtitles.append({'index': index, 'start': start, 'end': end, 'text': text})
        except (ValueError, IndexError):
            continue

    return subtitles


# ---------------------------------------------------------------------------
# Bilingual helpers
# ---------------------------------------------------------------------------

def extract_bilingual_text(text: str) -> Tuple[str, str]:
    """Extract target and source text from a bilingual subtitle.

    Args:
        text: Subtitle text (possibly two lines).

    Returns:
        ``(target_text, source_text)`` tuple.
        If only one line is present both values are the same.
    """
    lines = text.strip().split('\n')
    if len(lines) >= 2:
        return lines[0].strip(), lines[1].strip()
    elif lines:
        return lines[0].strip(), lines[0].strip()
    return "", ""


# ---------------------------------------------------------------------------
# SRT generation helpers
# ---------------------------------------------------------------------------

def clean_subtitle_text(text: str, max_length: int = 80) -> str:
    """Clean and lightly reformat subtitle text."""
    if not text:
        return ""
    lines = text.split('\n')
    cleaned: List[str] = []
    for line in lines:
        line = re.sub(r' +', ' ', line.strip())
        if len(line) > max_length:
            words = line.split()
            sub_lines: List[str] = []
            cur: List[str] = []
            cur_len = 0
            for word in words:
                wl = len(word) + (1 if cur else 0)
                if cur_len + wl <= max_length:
                    cur.append(word)
                    cur_len += wl
                else:
                    if cur:
                        sub_lines.append(' '.join(cur))
                    cur = [word]
                    cur_len = len(word)
            if cur:
                sub_lines.append(' '.join(cur))
            cleaned.extend(sub_lines)
        else:
            cleaned.append(line)
    return '\n'.join(cleaned)


def generate_srt_entry(index: int, start: float, end: float, text: str) -> str:
    """Generate a single SRT entry string."""
    return f"{index}\n{format_srt_timestamp(start)} --> {format_srt_timestamp(end)}\n{clean_subtitle_text(text)}\n"


def generate_srt_content(subtitles: List[Dict], merge_short: bool = False) -> str:
    """Generate complete SRT file content from a list of subtitle dicts."""
    if not subtitles:
        return ""
    sorted_subs = sorted(subtitles, key=lambda x: x['start'])
    entries = [
        generate_srt_entry(i, s['start'], s['end'], s.get('text', ''))
        for i, s in enumerate(sorted_subs, start=1)
    ]
    return '\n'.join(entries)


def save_srt_file(srt_content: str, output_path: str) -> bool:
    """Save SRT content string to a file."""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        return True
    except Exception as exc:
        print(f"Error saving SRT file: {exc}")
        return False
