# Generate All Speakers Script

This script generates audio samples for all 200 SeamlessM4T speaker voices, making it easy to compare and select your preferred voice for TTS or S2ST tasks.

## Features

- **Generate all speakers**: Creates audio for speaker IDs 0-199 (or a custom range)
- **Multiple languages**: Works with any language supported by SeamlessM4T
- **HTML index**: Auto-generates an HTML page for easy listening and comparison
- **Progress tracking**: Real-time progress bar with ETA
- **Batch processing**: Efficient generation with error handling

## Requirements

- m4t server running on http://localhost:8000 (or custom URL)
- Python virtual environment with dependencies installed

## Usage

### Basic Usage

Generate English samples with default settings:

```bash
cd /home/camus/work/stream-polyglot
./env/bin/python generate_all_speakers.py \
  --lang eng \
  --text "Hello, how are you today?"
```

### Language Examples

**Chinese (Mandarin):**
```bash
./env/bin/python generate_all_speakers.py \
  --lang cmn \
  --text "你好，今天天气怎么样？"
```

**Japanese:**
```bash
./env/bin/python generate_all_speakers.py \
  --lang jpn \
  --text "こんにちは、元気ですか？"
```

**Spanish:**
```bash
./env/bin/python generate_all_speakers.py \
  --lang spa \
  --text "Hola, ¿cómo estás hoy?"
```

**French:**
```bash
./env/bin/python generate_all_speakers.py \
  --lang fra \
  --text "Bonjour, comment allez-vous?"
```

### Custom Options

**Generate specific range of speakers:**
```bash
./env/bin/python generate_all_speakers.py \
  --lang eng \
  --text "Test audio" \
  --start 0 \
  --end 50 \
  --output ./my_samples
```

**Use custom API URL:**
```bash
./env/bin/python generate_all_speakers.py \
  --lang eng \
  --text "Test" \
  --api-url http://192.168.1.100:8000
```

## Output

The script creates:

1. **Audio files**: One WAV file per speaker
   - Format: `speaker_000_eng.wav`, `speaker_001_eng.wav`, etc.
   - 16kHz, 16-bit PCM
   - Typical size: ~50KB per file (for ~1.5s audio)

2. **HTML index**: `index.html` for easy playback
   - Grid layout showing all speakers
   - Embedded audio players
   - Can be opened directly in any web browser

## Performance

- **Generation speed**: ~0.7-0.8s per speaker
- **Full generation (200 speakers)**: ~2-3 minutes
- **Total size**: ~10-12MB for 200 speakers (varies by text length)

## Example Output

```
SeamlessM4T Speaker Voice Generator

ℹ Text: Hello, how are you today?
ℹ Language: eng
ℹ Speaker ID range: 0-199
ℹ Output directory: ./speaker_samples
ℹ API URL: http://localhost:8000

Checking m4t server...
✓ m4t server is healthy
✓ Output directory ready: ./speaker_samples

Generating Audio Samples (200 speakers)
Progress: 100.0% (200/200) | Success: 200 | Failed: 0 | ETA: 0s

Generation Complete!
✓ Successfully generated: 200 audio files
ℹ Total time: 156.2s (0.78s per speaker)
ℹ Output directory: ./speaker_samples
✓ Generated HTML index: ./speaker_samples/index.html
ℹ Open in browser: file:///path/to/speaker_samples/index.html
```

## Use Cases

1. **Voice selection**: Listen to all voices to find the best match for your project
2. **Voice diversity analysis**: Compare characteristics across different speaker IDs
3. **Quality testing**: Verify TTS quality across all available voices
4. **Documentation**: Create audio samples for project documentation
5. **A/B testing**: Generate samples for user preference testing

## Command-Line Options

```
--lang LANG          Language code (required)
                     Examples: eng, cmn, jpn, fra, spa, deu, ita

--text TEXT          Text to synthesize (required)
                     Can be any text in the target language

--output DIR         Output directory (default: ./speaker_samples)

--start ID           Starting speaker ID (default: 0)
                     Range: 0-199

--end ID             Ending speaker ID (default: 199)
                     Range: 0-199

--api-url URL        m4t API server URL
                     Default: http://localhost:8000

--batch-size N       Progress update frequency (default: 10)
                     Shows progress every N speakers
```

## Tips

1. **Choose meaningful text**: Use text that represents your actual use case
2. **Keep text moderate**: Very long text takes longer to generate
3. **Listen systematically**: Use the HTML index to compare speakers side-by-side
4. **Note your favorites**: Keep track of speaker IDs that work best
5. **Test multiple languages**: Some speakers may sound better in certain languages

## Troubleshooting

### m4t server not responding
```bash
# Start the server first
cd /home/camus/work/m4t
./env/bin/python server.py
```

### Out of disk space
- Each speaker generates ~50KB
- 200 speakers = ~10-12MB total
- Clear old samples with: `rm -rf ./speaker_samples`

### Generation too slow
- Use `--end` to generate fewer speakers initially
- Example: `--start 0 --end 49` for first 50 voices only

## See Also

- [m4t README](../m4t/README.md) - m4t API server documentation
- [stream-polyglot main.py](./main.py) - Main CLI with `--speaker-id` option
- [m4t test_speaker_id.py](../m4t/test_speaker_id.py) - Speaker ID testing script
