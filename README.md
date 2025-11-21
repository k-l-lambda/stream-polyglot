# Stream-Polyglot

**Seamless multilingual video/audio translation and subtitle generation tool**

Stream-Polyglot is a cross-platform video and audio translation application that leverages the SeamlessM4T API to provide high-quality speech-to-text translation, subtitle generation, and audio dubbing capabilities across 100+ languages.

## Features

- **Video Translation**: Extract audio from video files, translate speech to text in target language
- **Subtitle Generation**: Automatically generate SRT/VTT subtitle files with accurate timestamps
- **Bilingual Subtitles**: Generate subtitles with both source and target languages
- **Audio Dubbing**: Replace original audio with translated speech (text-to-speech in target language)
- **Voice Cloning Translation**: Generate voice-cloned audio from bilingual SRT files using GPT-SoVITS
- **Multi-format Support**: Works with MP4, MKV, WebM, AVI, and various audio formats (WAV, MP3, FLAC, M4A, OGG)
- **100+ Languages**: Supports speech input in 101 languages and text output in 96 languages via SeamlessM4T
- **Cross-platform**: Runs on Windows, macOS, and Linux

## Architecture

```
┌─────────────────┐
│  Video/Audio    │
│  Input Files    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│  FFmpeg         │────▶│  m4t API Server  │
│  Audio Extract  │     │  (SeamlessM4T)   │
└─────────┬───────┘     └────────┬─────────┘
          │                      │
          │                      │
          ▼                      ▼
┌─────────────────┐     ┌──────────────────┐
│  Subtitle       │     │  TTS (Optional)  │
│  Generator      │     │  Audio Dubbing   │
└─────────┬───────┘     └────────┬─────────┘
          │                      │
          └──────────┬───────────┘
                     ▼
          ┌──────────────────┐
          │  Output:         │
          │  - Subtitles     │
          │  - Dubbed Audio  │
          │  - Merged Video  │
          └──────────────────┘
```

## Technology Stack

### Core Dependencies
- **Python 3.10+**: Main programming language
- **FFmpeg**: Video/audio processing and manipulation
- **m4t API**: SeamlessM4T translation backend (required)

### Python Libraries
- **python-dotenv**: Environment variable management
- **requests**: HTTP client for m4t API communication
- **ffmpeg-python**: FFmpeg wrapper for video/audio operations (planned)
- **pysrt**: SRT subtitle file parsing and generation (planned)
- **webvtt-py**: WebVTT subtitle format support (planned)
- **soundfile**: Audio file I/O (planned)
- **numpy**: Numerical operations for audio processing (planned)

### Optional
- **MoviePy**: Alternative video editing library (user-friendly)
- **PyAV**: Low-level FFmpeg bindings for advanced control

## Installation

### Prerequisites

1. **FFmpeg**: Install FFmpeg on your system
   ```bash
   # Ubuntu/Debian
   sudo apt-get install ffmpeg

   # macOS
   brew install ffmpeg

   # Windows
   # Download from https://ffmpeg.org/download.html
   ```

2. **m4t API Server**: Start the SeamlessM4T API server by Docker (8GB GPU memory required at least)

   ```bash
   # Pull the m4t Docker image
   docker pull kllambda/m4t:v1.0.0

   # Run the m4t server (requires GPU)
   docker run -d \
     --name m4t-server \
     --gpus all \
     -p 8000:8000 \
     kllambda/m4t:v1.0.0

   # Check server status
   curl http://localhost:8000/health
   ```

   The server will be available at `http://localhost:8000` by default.

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/stream-polyglot.git
   cd stream-polyglot
   ```

2. Create virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure m4t API endpoint (optional):

   **Option 1: Using .env file (recommended)**
   ```bash
   # Copy the example file
   cp .env.example .env

   # Edit .env and set M4T_API_URL
   # M4T_API_URL=http://localhost:8000
   ```

   **Option 2: Using environment variable**
   ```bash
   export M4T_API_URL=http://localhost:8000
   ```

   **Option 3: Using command-line argument**
   ```bash
   python main.py test --api-url http://localhost:8000
   ```

## Usage

### Generate Subtitles

Generate Chinese subtitles for English video:

```bash
python -m main video.mp4 --lang eng:cmn --subtitle
```

### Generate Bilingual Subtitles

Generate bilingual subtitles (English + Chinese):

```bash
python -m main video.mp4 --lang eng:cmn --subtitle --subtitle-source-lang
```

Output format (video.eng-cmn.srt):
```srt
1
00:00:01,000 --> 00:00:04,000
你好，今天怎么样？
Hello, how are you today?

2
00:00:05,000 --> 00:00:08,000
我很好，谢谢！
I'm doing great, thank you!
```

### Generate Audio Dubbing

Replace audio with translated speech:

```bash
python -m main video.mp4 --lang eng:jpn --audio
```

### Split Audio into Vocals and Accompaniment

**NEW FEATURE**: Use `--split` to separate vocals from background music before timeline segmentation:

```bash
# Split audio before generating subtitles
python -m main video.mp4 --lang eng:cmn --subtitle --split

# Split audio before generating audio dubbing
python -m main video.mp4 --lang eng:jpn --audio --split

# Works with both subtitle and audio generation
python -m main video.mp4 --lang eng:cmn --subtitle --audio --split
```

**How it works:**
1. Extracts audio from video using FFmpeg
2. Calls m4t `/v1/audio-split` API to separate vocals from accompaniment (using Spleeter)
3. Saves both streams to cache directory (`.stream-polyglot-cache/[video_name]/split/`)
   - `vocals.wav`: Clean human voice/speech
   - `accompaniment.wav`: Background music and other sounds
4. Uses vocals audio for timeline segmentation (better speech detection accuracy)
5. Generates subtitles/dubbing based on the vocals stream

**Benefits:**
- **Better speech detection**: Removing background music improves VAD (Voice Activity Detection) accuracy
- **Cleaner segmentation**: Speech fragments are more precisely extracted without music interference
- **Cached for reuse**: Split audio is saved for future subtitle/audio generation
- **Optional feature**: Only used when `--split` flag is set (normal processing without it)

**Use cases:**
- Videos with strong background music that interferes with speech detection
- Music videos with vocals that need translation
- Movies with loud soundtracks
- Presentations with background music

**Requirements:**
- m4t server must have Spleeter installed (`pip install spleeter`)
- Processing time increases by ~0.6-0.7x real-time for audio splitting step

### Generate Voice-Cloned Audio from Bilingual Subtitles

**NEW FEATURE**: Generate voice-cloned audio using bilingual SRT subtitles with GPT-SoVITS voice cloning:

```bash
# Option 1: Use existing cached timeline (fast)
# First generate bilingual subtitle to create cache
python -m main video.mp4 --lang eng:cmn --subtitle --subtitle-source-lang

# Then generate voice-cloned audio using cache
python -m main video.mp4 --lang eng:cmn --trans-voice video.eng-cmn.srt

# Option 2: Direct voice cloning (automatic segmentation if no cache)
# If cache doesn't exist, it will automatically extract audio and segment it
python -m main video.mp4 --lang eng:cmn --trans-voice video.eng-cmn.srt

# Option 3: Infer language from SRT filename
python -m main --trans-voice video.eng-cmn.srt

# Option 4: Use fixed seed for reproducible voice cloning
python -m main video.mp4 --lang eng:cmn --trans-voice video.eng-cmn.srt --seed 42
```

**Random Seed for Reproducibility:**
- `--seed` parameter controls the randomness in voice generation
- **Default (no --seed)**: Generates one random seed at the start and uses it for ALL segments in that generation
  - This ensures consistency across all voice cloned segments in a single run
  - Different runs will produce different (but internally consistent) results
- **Fixed seed (--seed 42)**: Uses the same seed across runs for fully reproducible results
  - Same input + same seed = identical output audio
  - Useful for A/B testing, debugging, or when consistent output is required

**How it works:**
1. Reads bilingual SRT file (target language + source language)
2. Checks for cached timeline; if not found, automatically extracts audio and segments it
3. Matches subtitle timing with cached audio fragments
4. Uses cached fragment audio as reference for voice cloning
5. Generates target language speech with cloned voice characteristics (using the same seed for all segments)
6. Concatenates all segments into final audio track

**Benefits:**
- Preserves original speaker's voice characteristics
- Better than generic TTS (more natural and expressive)
- Reuses cached timeline data for fast processing
- Automatic segmentation if cache doesn't exist
- Perfect for dubbing videos while maintaining voice identity
- Consistent voice characteristics across all segments (same seed used for all cloning operations)

### Generate Both Subtitles and Audio

Create both subtitle file and dubbed audio:

```bash
python -m main video.mp4 --lang eng:cmn --subtitle --audio
```

### Specify Custom Output Directory

```bash
python -m main video.mp4 --lang jpn:eng --subtitle --output ./translated/
```

### Use Custom API Server

```bash
python -m main video.mp4 --lang eng:cmn --subtitle --api-url http://192.168.1.100:8000
```

### View All Options

```bash
python -m main --help
```

## Supported Languages

SeamlessM4T supports 101 languages for speech input and 96 languages for text output.

### Popular Languages

| Language | Code | Speech Input | Text Output |
|----------|------|--------------|-------------|
| English | eng | ✓ | ✓ |
| Chinese (Simplified) | cmn | ✓ | ✓ |
| Chinese (Traditional) | cmn_Hant | ✓ | ✓ |
| Japanese | jpn | ✓ | ✓ |
| Korean | kor | ✓ | ✓ |
| French | fra | ✓ | ✓ |
| German | deu | ✓ | ✓ |
| Spanish | spa | ✓ | ✓ |
| Russian | rus | ✓ | ✓ |
| Arabic | arb | ✓ | ✓ |

See [m4t documentation](http://localhost:8000/languages) for the complete language list.

## Subtitle Formats

### SRT (SubRip)
```srt
1
00:00:01,000 --> 00:00:04,000
Hello, how are you today?

2
00:00:05,000 --> 00:00:08,000
I'm doing great, thank you!
```

### VTT (WebVTT)
```vtt
WEBVTT

00:00:01.000 --> 00:00:04.000
Hello, how are you today?

00:00:05.000 --> 00:00:08.000
I'm doing great, thank you!
```

## Container Format Support

| Format | Extension | Subtitle Support | Audio Tracks | Recommended Use Case |
|--------|-----------|------------------|--------------|----------------------|
| MP4 | .mp4 | Limited (mov_text) | Single | Universal compatibility |
| MKV | .mkv | Excellent (SRT, ASS, multiple tracks) | Multiple | Professional archiving |
| WebM | .webm | WebVTT | Single | Web streaming |
| AVI | .avi | Poor (external only) | Single | Legacy support |

## Performance

### Processing Speed
- **Subtitle Generation**: ~0.2-0.5x real-time (5-minute video → 10-25 minutes)
- **Audio Dubbing**: ~0.1-0.3x real-time (requires TTS for entire audio)
- **Video Remuxing**: Near real-time (no re-encoding)

### Hardware Requirements
- **CPU**: Multi-core recommended for parallel processing
- **RAM**: 4GB minimum, 8GB+ recommended
- **GPU**: Optional (m4t server uses GPU for inference)
- **Storage**: ~10x video file size for temporary processing

## Project Structure

```
stream-polyglot/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── setup.py                  # Package installation
├── stream_polyglot/          # Main package
│   ├── __init__.py
│   ├── video_processor.py    # FFmpeg integration
│   ├── m4t_client.py         # m4t API client
│   ├── subtitle_generator.py # SRT/VTT generation
│   ├── translator.py         # Main orchestration
│   └── utils.py              # Helper functions
├── tests/                    # Unit tests
│   ├── test_video_processor.py
│   ├── test_m4t_client.py
│   └── test_subtitle_generator.py
└── examples/                 # Example scripts
    ├── basic_translation.py
    ├── batch_processing.py
    └── advanced_dubbing.py
```

## Roadmap

### v0.1.0 (Current)
- [x] Project initialization
- [ ] FFmpeg video processor
- [ ] m4t API client
- [ ] Basic subtitle generation (SRT)
- [ ] CLI interface

### v0.2.0
- [ ] Audio dubbing functionality
- [ ] WebVTT subtitle support
- [ ] Batch processing
- [ ] Progress tracking

### v0.3.0
- [ ] Multi-track subtitle support (MKV)
- [ ] Subtitle timing adjustment
- [ ] Audio/video synchronization
- [ ] Configuration file support

### v1.0.0
- [ ] GUI interface (Streamlit/Qt)
- [ ] Advanced subtitle editing
- [ ] Plugin system
- [ ] Performance optimizations

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Troubleshooting

### Common Issues

**Q: "FFmpeg not found" error**
```bash
# Verify FFmpeg installation
ffmpeg -version

# Add FFmpeg to PATH (Windows)
# Add C:\path\to\ffmpeg\bin to System Environment Variables
```

**Q: "m4t API connection refused"**
```bash
# Check if m4t server is running
curl http://localhost:8000/health

# Start m4t server
cd ~/work/m4t
./start_dev.sh
```

**Q: "Audio/subtitle out of sync"**
```bash
# Use --sync-offset parameter to adjust timing
python stream-polyglot.py translate \
  --input video.mp4 \
  --sync-offset 0.5  # Delay subtitles by 0.5 seconds
```

## License

MIT License - see [LICENSE](LICENSE) file for details

## Acknowledgments

- **SeamlessM4T** (Meta AI): Multilingual translation model
- **FFmpeg**: Video/audio processing framework
- Community contributors and testers

## Contact

- **Issues**: https://github.com/yourusername/stream-polyglot/issues
- **Discussions**: https://github.com/yourusername/stream-polyglot/discussions

---

**Stream-Polyglot** - Breaking language barriers, one frame at a time.
