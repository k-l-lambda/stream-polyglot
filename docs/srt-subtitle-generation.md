# SRT Subtitle Generation with Timeline-Based Translation

Stream-Polyglot provides automatic SRT subtitle generation with precise timeline-based translation, powered by VAD (Voice Activity Detection) segmentation.

## Features

- **VAD-Based Segmentation**: Automatically detects speech segments in audio using Silero VAD
- **Timeline-Accurate Translation**: Each speech segment is translated independently with precise timestamps
- **Standard SRT Format**: Generates SubRip Text (.srt) files compatible with all video players
- **Bilingual Support**: Optionally generate subtitles in both source and target languages
- **Smart Merging**: Automatically merges very short subtitle segments for better readability

## Usage

### Basic Subtitle Generation

Generate Chinese subtitles for an English video:

```bash
cd /home/camus/work/stream-polyglot
./env/bin/python -m main video.mp4 --lang eng:cmn --subtitle
```

### With Custom Output Directory

```bash
./env/bin/python -m main video.mp4 --lang eng:cmn --subtitle --output ./subtitles/
```

### Generate Both Source and Target Language Subtitles

Use `--subtitle-source-lang` to generate subtitles in both languages:

```bash
./env/bin/python -m main video.mp4 --lang eng:cmn --subtitle --subtitle-source-lang
```

This generates:
- `video.cmn.srt` - Chinese (target language) subtitles
- `video.eng.srt` - English (source language) subtitles

### Combined Audio Dubbing and Subtitles

Generate both audio dubbing and subtitles:

```bash
./env/bin/python -m main video.mp4 --lang eng:jpn --subtitle --audio
```

## How It Works

### 1. Audio Extraction

FFmpeg extracts audio from the video file:
- Format: PCM 16-bit little-endian
- Sample rate: 16kHz (required by SeamlessM4T)
- Channels: Mono

### 2. VAD-Based Segmentation

The audio is segmented using Voice Activity Detection:
- Processes audio in 30-second chunks
- Detects speech boundaries with Silero VAD
- Handles incomplete segments at chunk boundaries
- Returns timeline with precise start/end timestamps

```
Original audio (8.86s):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    ▓▓▓▓   ░░  ▓▓▓▓▓  ░░  ▓▓▓▓
    0.1s      3.8s      7.1s

Segmented:
Fragment 1: 0.1s - 2.8s
Fragment 2: 3.8s - 6.1s
Fragment 3: 7.1s - 8.9s
```

### 3. Fragment-by-Fragment Translation

Each speech segment is translated independently:
- Maintains temporal accuracy
- Preserves sentence boundaries
- Handles translation context per segment

### 4. SRT File Generation

Generates standard SRT format with:
- Sequential numbering (1, 2, 3...)
- Timestamp format: `HH:MM:SS,mmm --> HH:MM:SS,mmm`
- Translated text (automatically cleaned and formatted)
- Optional short subtitle merging for readability

## Output Example

### Generated SRT File (`video.cmn.srt`)

```
1
00:00:00,098 --> 00:00:02,750
欢迎来到视频翻译测试

2
00:00:03,810 --> 00:00:06,078
这是我们演示的第二部分

3
00:00:07,073 --> 00:00:08,859
感谢您观看这个测试视频
```

## Configuration Options

### Language Codes

Common language codes for translation:

| Language | Code | Example |
|----------|------|---------|
| English | eng | --lang eng:cmn |
| Chinese (Simplified) | cmn | --lang cmn:eng |
| Japanese | jpn | --lang jpn:eng |
| Korean | kor | --lang kor:eng |
| Spanish | spa | --lang spa:eng |
| French | fra | --lang fra:eng |
| German | deu | --lang deu:eng |
| Russian | rus | --lang rus:eng |
| Arabic | arb | --lang arb:eng |

See [m4t server /languages endpoint](http://localhost:8000/languages) for full list.

### Timeline Segmentation Parameters

The segmentation behavior can be adjusted in `audio_timeline.py`:

- `chunk_duration`: Processing chunk size (default: 30.0s)
- `tolerance`: Incomplete segment detection threshold (default: 0.1s)
- `min_duration`: Minimum subtitle duration for merging (default: 0.5s)
- `max_duration`: Maximum merged subtitle duration (default: 7.0s)

## Technical Details

### SRT Format Specification

SubRip Text (.srt) format structure:

```
[Sequence number]
[Start time] --> [End time]
[Subtitle text line 1]
[Subtitle text line 2]
[Blank line]
```

Timestamp format: `HH:MM:SS,mmm` (comma for milliseconds, not period)

### Timeline Metadata

The segmentation process provides:

```json
{
  "input_file": "video.wav",
  "total_duration": 519.8,
  "sample_rate": 16000,
  "fragment_count": 128,
  "output_dir": "/tmp/fragments"
}
```

### Subtitle Validation

Automatic validation checks:
- Required fields: start, end, text
- Timing constraints: end > start, no negative times
- Overlap detection between consecutive subtitles
- Empty text filtering

## Performance

### Processing Time

Typical performance on an 8.86-second audio file:

| Step | Duration | Notes |
|------|----------|-------|
| Audio extraction | ~0.5s | FFmpeg |
| VAD segmentation | ~1.0s | Silero VAD |
| Translation (3 fragments) | ~2.0s | SeamlessM4T S2TT |
| SRT generation | <0.1s | srt_utils |
| **Total** | **~3.6s** | |

Scales linearly with audio duration (~0.4s per second of audio).

### Resource Usage

- **Memory**: ~2GB (SeamlessM4T model loading)
- **GPU**: Recommended for faster translation (CUDA)
- **Disk**: Temporary fragments (~10% of original audio size)

## Troubleshooting

### Issue: m4t Server Not Accessible

**Error**: "Cannot connect to m4t API server"

**Solution**:
```bash
# Start the m4t server
cd /home/camus/work/m4t
./env/bin/python server.py

# Verify server is running
curl http://localhost:8000/health
```

### Issue: FFmpeg Not Found

**Error**: "FFmpeg not found. Please install FFmpeg."

**Solution**:
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Verify installation
ffmpeg -version
```

### Issue: No Subtitles Generated

**Error**: "No subtitles generated"

**Possible causes**:
1. No speech detected in audio (check VAD sensitivity)
2. Translation failed (check m4t server logs)
3. Audio format incompatible (should be auto-converted by FFmpeg)

**Debug**:
```bash
# Check audio timeline log output
./env/bin/python -m main video.mp4 --lang eng:cmn --subtitle 2>&1 | grep "INFO:audio_timeline"
```

### Issue: Incorrect Timestamps

**Problem**: Subtitles appear at wrong times

**Possible causes**:
1. VAD sensitivity too high/low
2. Audio and video out of sync in source file

**Solution**:
- Adjust VAD parameters in `audio_timeline.py`
- Pre-process video to ensure A/V sync

### Issue: Text Too Long Per Subtitle

**Problem**: Subtitles have very long lines

**Solution**:
The `clean_subtitle_text()` function in `srt_utils.py` automatically breaks lines at 80 characters. Adjust `max_length` parameter if needed:

```python
# In srt_utils.py
def clean_subtitle_text(text: str, max_length: int = 60):  # Changed from 80
    ...
```

## Integration with Video Players

### VLC Media Player

1. Place SRT file in same directory as video
2. Name it: `video_name.srt` (same base name as video)
3. Open video in VLC
4. Subtitles will load automatically

Or manually:
- Subtitle → Add Subtitle File → Select .srt file

### mpv

```bash
mpv video.mp4 --sub-file=video.cmn.srt
```

### Web Players (HTML5)

```html
<video controls>
  <source src="video.mp4" type="video/mp4">
  <track kind="subtitles" src="video.cmn.srt" srclang="cmn" label="Chinese">
  <track kind="subtitles" src="video.eng.srt" srclang="eng" label="English">
</video>
```

## API Reference

### `generate_srt_content()`

Generate SRT file content from subtitle list.

```python
from srt_utils import generate_srt_content

subtitles = [
    {"start": 0.1, "end": 2.8, "text": "First subtitle"},
    {"start": 3.8, "end": 6.1, "text": "Second subtitle"},
    {"start": 7.1, "end": 8.9, "text": "Third subtitle"}
]

srt_content = generate_srt_content(subtitles, merge_short=True)
```

**Parameters**:
- `subtitles` (List[Dict]): List of subtitle dicts with `start`, `end`, `text`
- `merge_short` (bool): Whether to merge very short subtitles (default: True)

**Returns**: Complete SRT file content as string

### `save_srt_file()`

Save SRT content to file.

```python
from srt_utils import save_srt_file

success = save_srt_file(srt_content, "output.srt")
```

**Parameters**:
- `srt_content` (str): SRT file content
- `output_path` (str): Path to save SRT file

**Returns**: True if successful, False otherwise

### `segment_with_timeline()`

Segment audio with VAD-based timeline.

```python
from audio_timeline import segment_with_timeline

timeline, metadata = segment_with_timeline(
    audio_path="audio.wav",
    output_dir="/tmp/fragments",
    chunk_duration=30.0,
    m4t_api_url="http://localhost:8000"
)
```

**Parameters**:
- `audio_path` (str): Path to input audio file
- `output_dir` (str): Directory to save audio fragments
- `chunk_duration` (float): Processing chunk size in seconds (default: 30.0)
- `m4t_api_url` (str): m4t API server URL
- `save_timeline` (bool): Save timeline JSON file (default: True)

**Returns**: Tuple of (timeline, metadata)
- `timeline`: List of fragments with `id`, `file`, `start`, `end`
- `metadata`: Dict with `total_duration`, `sample_rate`, `fragment_count`

## See Also

- [Main CLI Documentation](./main-cli.md)
- [Audio Timeline Segmentation](./audio-timeline.md)
- [m4t API Reference](../m4t/README.md)
- [Generate All Speakers](./generate-all-speakers.md) - For audio dubbing voice selection
