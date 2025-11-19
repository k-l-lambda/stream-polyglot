# Audio Timeline Segmentation

Intelligent audio segmentation module that splits long audio files into speech fragments using Voice Activity Detection (VAD), with smart chunk processing and boundary handling.

## Features

- **Chunk-based Processing**: Process long audio in manageable chunks (default 30s)
- **Intelligent Boundary Handling**: Detects incomplete speech fragments at chunk boundaries and carries them over to avoid splitting sentences
- **VAD Integration**: Uses m4t's Silero VAD API for accurate speech detection
- **Timeline Generation**: Outputs JSON timeline with precise timestamps for each fragment
- **Fragment Export**: Saves each speech segment as individual WAV file
- **Memory Efficient**: Processes large files without loading everything into memory at once

## Installation

Dependencies are already included in `requirements.txt`:
```bash
cd /home/camus/work/stream-polyglot
pip install -r requirements.txt
```

Requires m4t API server running:
```bash
cd /home/camus/work/m4t
python server.py
```

## Usage

### Command Line

```bash
python audio_timeline.py <audio_file> [output_dir] [chunk_duration]
```

**Examples:**
```bash
# Basic usage (30s chunks)
python audio_timeline.py video_audio.wav ./fragments

# Smaller chunks (5s) for testing
python audio_timeline.py video_audio.wav ./fragments 5.0

# Larger chunks (60s) for production
python audio_timeline.py video_audio.wav ./output 60.0
```

### Python API

```python
from audio_timeline import segment_with_timeline

# Segment audio and get timeline
timeline, metadata = segment_with_timeline(
    audio_path="long_video.wav",
    output_dir="./fragments",
    chunk_duration=30.0,
    m4t_api_url="http://localhost:8000",
    save_timeline=True  # Saves timeline.json
)

# Access results
print(f"Total duration: {metadata['total_duration']:.2f}s")
print(f"Created {metadata['fragment_count']} fragments")

# Iterate through fragments
for fragment in timeline:
    print(f"Fragment {fragment['id']}: {fragment['start']:.2f}s - {fragment['end']:.2f}s")
    audio_file = f"{metadata['output_dir']}/{fragment['file']}"
    # Process fragment...
```

### Advanced Usage

```python
from audio_timeline import AudioTimeline

# Custom VAD settings
segmenter = AudioTimeline(
    m4t_api_url="http://localhost:8000",
    min_silence_duration_ms=500,  # Longer pauses = sentence boundaries
    min_speech_duration_ms=100,   # Shorter minimum speech
    vad_threshold=0.3             # More sensitive detection
)

# Segment with custom settings
timeline, metadata = segmenter.segment_with_timeline(
    audio_path="podcast.wav",
    output_dir="./segments",
    chunk_duration=45.0
)
```

## Output Format

### Timeline JSON

The `timeline.json` file contains:

```json
{
  "input_file": "video_audio.wav",
  "total_duration": 600.5,
  "sample_rate": 16000,
  "fragment_count": 25,
  "output_dir": "./fragments",
  "fragments": [
    {
      "id": 0,
      "file": "fragment_0000000.3_0000005.2.wav",
      "start": 0.258,
      "end": 5.234
    },
    {
      "id": 1,
      "file": "fragment_0000005.5_0000012.8.wav",
      "start": 5.532,
      "end": 12.846
    }
  ]
}
```

### Fragment Files

Audio fragments are saved as:
- **Format**: WAV, 16-bit PCM
- **Sample Rate**: Same as input (typically 16kHz)
- **Naming**: `fragment_{start}_{end}.wav` with millisecond precision
- **Content**: Complete speech segments only

## Algorithm Overview

### 1. Chunk Processing Loop

```
For each chunk of audio:
  1. Extract chunk (e.g., 30 seconds)
  2. Run VAD to detect speech segments
  3. Check if last segment is incomplete:
     - If YES: buffer it and adjust next chunk start
     - If NO: save all segments
  4. Move to next chunk position
```

### 2. Boundary Detection

A segment is considered **incomplete** if:
- It ends within 0.1s of the chunk boundary
- There's no silence gap at the end

### 3. Carry-Over Mechanism

```
Chunk 1: [speech1] [speech2-incomplete]
                            ↓ buffer
Chunk 2: ←-- adjust start  [speech2-complete] [speech3]
```

The next chunk starts slightly before the incomplete segment to ensure complete capture.

## Integration with Translation

### Example: Translate All Fragments

```python
import json
from pathlib import Path

# Load timeline
with open("./fragments/timeline.json") as f:
    data = json.load(f)

# Translate each fragment
subtitles = []
for fragment in data['fragments']:
    audio_path = Path(data['output_dir']) / fragment['file']

    # Call translation API
    translated_text = translate_audio(str(audio_path),
                                     source_lang="jpn",
                                     target_lang="cmn")

    # Build subtitle with timeline
    subtitles.append({
        "start": fragment['start'],
        "end": fragment['end'],
        "text": translated_text
    })

# Save subtitles (SRT format example)
with open("subtitles.srt", "w") as f:
    for i, sub in enumerate(subtitles, 1):
        f.write(f"{i}\n")
        f.write(f"{format_time(sub['start'])} --> {format_time(sub['end'])}\n")
        f.write(f"{sub['text']}\n\n")
```

## Performance

### Benchmarks (on NVIDIA H20 GPU)

| Audio Length | Chunk Size | Fragments | Processing Time | Speed |
|--------------|------------|-----------|-----------------|-------|
| 3 minutes    | 30s        | 12        | ~5s             | 36x   |
| 10 minutes   | 30s        | 40        | ~15s            | 40x   |
| 30 minutes   | 30s        | 120       | ~45s            | 40x   |

**VAD overhead**: ~0.06s per 3s audio chunk (50x faster than real-time)

### Memory Usage

- **Peak memory**: ~500MB for 1-hour audio
- **Disk space**: Same as input audio (fragments total equals original)

## Troubleshooting

### M4T API Not Responding

```bash
# Check if server is running
curl http://localhost:8000/health

# If not, start it:
cd /home/camus/work/m4t
python server.py
```

### No Fragments Generated

- **Check audio format**: Must be readable by soundfile (WAV, MP3, FLAC)
- **Check VAD threshold**: Try lowering to 0.3 for more sensitivity
- **Check min_silence_duration_ms**: Lower values detect more breaks

### Fragments Too Short/Long

Adjust VAD parameters:
```python
segmenter = AudioTimeline(
    min_silence_duration_ms=500,  # Longer = fewer, longer fragments
    min_speech_duration_ms=250,   # Shorter = capture brief speech
)
```

## Testing

Run the example script:
```bash
cd examples
python segment_example.py
```

Or test manually:
```bash
# Create test audio (9s, multi-speaker)
python -c "
import soundfile as sf
import numpy as np

files = ['assets/japanese_speech.wav', 'assets/english_speech.wav']
audio = []
for f in files:
    a, sr = sf.read(f)
    audio.append(a)
    audio.append(np.zeros(16000))  # 1s silence

combined = np.concatenate(audio)
sf.write('/tmp/test_multi.wav', combined, 16000)
"

# Segment it
python audio_timeline.py /tmp/test_multi.wav /tmp/test_output 5.0

# Check results
cat /tmp/test_output/timeline.json
ls -lh /tmp/test_output/
```

## Known Limitations

1. **Chunk size minimum**: 5 seconds recommended (VAD needs enough context)
2. **Silence detection**: Very short pauses (<100ms) between words are not detected as boundaries
3. **Music/noise**: Background noise may be detected as speech (use Spleeter preprocessing from m4t)
4. **Very long continuous speech**: May create large fragments if no natural pauses

## Future Enhancements

- [ ] Parallel chunk processing for faster execution
- [ ] Streaming mode for real-time segmentation
- [ ] Optional ASR integration for text-based boundary detection
- [ ] SRT/VTT subtitle generation directly
- [ ] Progress callback for long audio files

## See Also

- [m4t README](../m4t/README.md) - Voice Activity Detection API
- [audio-segmentation-research.md](../diary-job/memo/audio-segmentation-research.md) - Research notes
