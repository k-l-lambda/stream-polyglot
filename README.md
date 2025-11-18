# Stream-Polyglot

**Seamless multilingual video/audio translation and subtitle generation tool**

Stream-Polyglot is a cross-platform video and audio translation application that leverages the SeamlessM4T API to provide high-quality speech-to-text translation, subtitle generation, and audio dubbing capabilities across 100+ languages.

## Features

- **Video Translation**: Extract audio from video files, translate speech to text in target language
- **Subtitle Generation**: Automatically generate SRT/VTT subtitle files with accurate timestamps
- **Audio Dubbing**: Replace original audio with translated speech (text-to-speech in target language)
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
- **ffmpeg-python**: FFmpeg wrapper for video/audio operations
- **requests**: HTTP client for m4t API communication
- **pysrt**: SRT subtitle file parsing and generation
- **webvtt-py**: WebVTT subtitle format support
- **soundfile**: Audio file I/O
- **numpy**: Numerical operations for audio processing

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

2. **m4t API Server**: Ensure the SeamlessM4T API server is running
   ```bash
   # Default endpoint: http://localhost:8000
   # See: https://github.com/yourusername/m4t
   ```

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
   ```bash
   export M4T_API_URL=http://localhost:8000
   ```

## Usage

### Basic Translation

Translate Japanese video to Chinese subtitles:

```bash
python stream-polyglot.py translate \
  --input video.mp4 \
  --source-lang jpn \
  --target-lang cmn \
  --output video.cmn.srt
```

### Audio Dubbing

Replace audio with translated speech:

```bash
python stream-polyglot.py dub \
  --input video.mp4 \
  --source-lang jpn \
  --target-lang eng \
  --output video_dubbed.mp4
```

### Batch Processing

Process multiple files:

```bash
python stream-polyglot.py batch \
  --input-dir ./videos \
  --source-lang jpn \
  --target-lang cmn \
  --output-dir ./translated
```

### Python API

```python
from stream_polyglot import VideoTranslator

# Initialize translator
translator = VideoTranslator(
    m4t_api_url="http://localhost:8000"
)

# Translate video to subtitles
translator.translate_video(
    input_path="movie.mp4",
    source_lang="jpn",
    target_lang="cmn",
    output_subtitle="movie.cmn.srt"
)

# Generate dubbed audio
translator.dub_video(
    input_path="movie.mp4",
    source_lang="jpn",
    target_lang="eng",
    output_path="movie_dubbed.mp4"
)
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

## Related Projects

- [m4t API Server](https://github.com/yourusername/m4t) - SeamlessM4T FastAPI backend
- [SeamlessM4T](https://github.com/facebookresearch/seamless_communication) - Original Meta AI model

## Contact

- **Issues**: https://github.com/yourusername/stream-polyglot/issues
- **Discussions**: https://github.com/yourusername/stream-polyglot/discussions

---

**Stream-Polyglot** - Breaking language barriers, one frame at a time.
