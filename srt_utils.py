"""
SRT Subtitle Utilities

Provides functions for generating and formatting SRT (SubRip Text) subtitle files.

SRT Format:
1
00:00:04,354 --> 00:00:05,470
First subtitle text

2
00:00:06,852 --> 00:00:08,832
Second subtitle text
"""

from typing import List, Dict
import math


def format_srt_timestamp(seconds: float) -> str:
    """
    Convert seconds to SRT timestamp format: HH:MM:SS,mmm

    Args:
        seconds: Time in seconds (can be float with milliseconds)

    Returns:
        Formatted timestamp string (e.g., "00:00:04,354")

    Examples:
        >>> format_srt_timestamp(4.354)
        '00:00:04,354'
        >>> format_srt_timestamp(125.678)
        '00:02:05,678'
    """
    # Handle negative values
    if seconds < 0:
        seconds = 0

    # Calculate components
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds % 1) * 1000)

    # Format: HH:MM:SS,mmm
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"


def clean_subtitle_text(text: str, max_length: int = 80) -> str:
    """
    Clean and format subtitle text

    Args:
        text: Raw subtitle text
        max_length: Maximum characters per line (default: 80)

    Returns:
        Cleaned text
    """
    if not text:
        return ""

    # Strip whitespace
    text = text.strip()

    # Replace multiple spaces with single space, but preserve newlines
    import re
    # Split by newlines first to preserve line structure (for bilingual subtitles)
    lines = text.split('\n')
    cleaned_lines = []

    for line in lines:
        # For each line, replace multiple spaces with single space
        line = line.strip()
        line = re.sub(r' +', ' ', line)

        # Optionally break long lines
        if len(line) > max_length:
            # Try to break at natural points
            words = line.split()
            sub_lines = []
            current_line = []
            current_length = 0

            for word in words:
                word_len = len(word) + (1 if current_line else 0)
                if current_length + word_len <= max_length:
                    current_line.append(word)
                    current_length += word_len
                else:
                    if current_line:
                        sub_lines.append(' '.join(current_line))
                    current_line = [word]
                    current_length = len(word)

            if current_line:
                sub_lines.append(' '.join(current_line))

            cleaned_lines.extend(sub_lines)
        else:
            cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def merge_short_subtitles(
    subtitles: List[Dict],
    min_duration: float = 0.5,
    max_duration: float = 7.0
) -> List[Dict]:
    """
    Merge very short subtitles to improve readability

    Args:
        subtitles: List of subtitle dicts with start, end, text
        min_duration: Minimum duration threshold (seconds)
        max_duration: Maximum duration for merged subtitle

    Returns:
        List of subtitles with short ones merged
    """
    if not subtitles:
        return []

    merged = []
    buffer = None

    for sub in subtitles:
        duration = sub['end'] - sub['start']

        if duration < min_duration:
            if buffer is None:
                # Start buffering
                buffer = sub.copy()
            else:
                # Merge with buffer
                merged_duration = sub['end'] - buffer['start']
                if merged_duration <= max_duration:
                    buffer['end'] = sub['end']
                    buffer['text'] += ' ' + sub['text']
                else:
                    # Buffer is full, flush it
                    merged.append(buffer)
                    buffer = sub.copy()
        else:
            # Normal duration subtitle
            if buffer:
                # Flush buffer first
                merged.append(buffer)
                buffer = None
            merged.append(sub)

    # Flush remaining buffer
    if buffer:
        merged.append(buffer)

    return merged


def generate_srt_entry(index: int, start: float, end: float, text: str) -> str:
    """
    Generate a single SRT subtitle entry

    Args:
        index: Subtitle number (1-indexed)
        start: Start time in seconds
        end: End time in seconds
        text: Subtitle text

    Returns:
        Formatted SRT entry string
    """
    start_ts = format_srt_timestamp(start)
    end_ts = format_srt_timestamp(end)
    cleaned_text = clean_subtitle_text(text)

    return f"{index}\n{start_ts} --> {end_ts}\n{cleaned_text}\n"


def generate_srt_content(subtitles: List[Dict], merge_short: bool = True) -> str:
    """
    Generate complete SRT file content from subtitle list

    Args:
        subtitles: List of dicts with keys: start, end, text
                   Optional: index (will be generated if missing)
        merge_short: Whether to merge very short subtitles

    Returns:
        Complete SRT file content as string

    Example:
        subtitles = [
            {"start": 4.354, "end": 5.470, "text": "Hello world"},
            {"start": 6.852, "end": 8.832, "text": "How are you?"}
        ]
        srt_content = generate_srt_content(subtitles)
    """
    if not subtitles:
        return ""

    # Optionally merge short subtitles
    if merge_short:
        subtitles = merge_short_subtitles(subtitles)

    # Sort by start time
    sorted_subs = sorted(subtitles, key=lambda x: x['start'])

    # Generate SRT entries
    entries = []
    for i, sub in enumerate(sorted_subs, start=1):
        entry = generate_srt_entry(
            index=sub.get('index', i),
            start=sub['start'],
            end=sub['end'],
            text=sub.get('text', '')
        )
        entries.append(entry)

    # Join with blank lines between entries
    return '\n'.join(entries)


def save_srt_file(srt_content: str, output_path: str) -> bool:
    """
    Save SRT content to file

    Args:
        srt_content: SRT file content string
        output_path: Path to save SRT file

    Returns:
        True if successful, False otherwise
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        return True
    except Exception as e:
        print(f"Error saving SRT file: {e}")
        return False


def validate_subtitle_timing(subtitles: List[Dict]) -> List[str]:
    """
    Validate subtitle timing and return list of issues

    Args:
        subtitles: List of subtitle dicts

    Returns:
        List of error messages (empty if no issues)
    """
    issues = []

    for i, sub in enumerate(subtitles):
        # Check required fields
        if 'start' not in sub:
            issues.append(f"Subtitle {i}: Missing 'start' field")
        if 'end' not in sub:
            issues.append(f"Subtitle {i}: Missing 'end' field")
        if 'text' not in sub:
            issues.append(f"Subtitle {i}: Missing 'text' field")

        # Check timing validity
        if 'start' in sub and 'end' in sub:
            if sub['start'] < 0:
                issues.append(f"Subtitle {i}: Negative start time ({sub['start']})")
            if sub['end'] < 0:
                issues.append(f"Subtitle {i}: Negative end time ({sub['end']})")
            if sub['end'] <= sub['start']:
                issues.append(f"Subtitle {i}: End time ({sub['end']}) must be after start time ({sub['start']})")

        # Check for overlaps with next subtitle
        if i < len(subtitles) - 1:
            next_sub = subtitles[i + 1]
            if 'start' in next_sub and 'end' in sub:
                if next_sub['start'] < sub['end']:
                    issues.append(f"Subtitle {i} and {i+1}: Timing overlap detected")

    return issues


if __name__ == "__main__":
    # Example usage
    test_subtitles = [
        {"start": 4.354, "end": 5.470, "text": "Hello, how are you today?"},
        {"start": 6.852, "end": 8.832, "text": "I'm doing great, thanks for asking!"},
        {"start": 10.125, "end": 12.456, "text": "Let's talk about the weather."}
    ]

    print("=== Example SRT Generation ===\n")

    # Generate SRT content
    srt_content = generate_srt_content(test_subtitles)
    print(srt_content)

    # Validate timing
    issues = validate_subtitle_timing(test_subtitles)
    if issues:
        print("\n=== Validation Issues ===")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\n✓ No timing issues detected")
