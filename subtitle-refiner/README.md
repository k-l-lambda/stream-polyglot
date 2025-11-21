# Subtitle Refiner

LLM-powered SRT subtitle refinement tool with sliding window processing. Refine subtitle translations, fix grammar, and improve overall quality using OpenAI, Claude, or local LLMs.

## Features

- **🔄 Sliding Window Processing**: Process subtitles in manageable chunks with context overlap
- **🤖 Multi-Provider Support**: OpenAI GPT-4, Anthropic Claude, or Ollama (local models)
- **🌐 Bilingual Subtitles**: Refine both target and source language lines
- **📝 Custom Prompts**: Use built-in or custom system prompts
- **⚙️ Configurable**: Window size, overlap, model selection via CLI or environment
- **🎯 Focus on Translation**: Default prompt optimized for fixing translation mistakes
- **🔍 Dry Run Mode**: Preview processing windows without API calls

## Installation

```bash
cd subtitle-refiner
npm install
npm run build
```

## Quick Start

### 1. Configure Environment

Create a `.env` file (copy from `.env.example`):

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```env
# Choose your provider
LLM_PROVIDER=openai

# OpenAI Configuration
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4-turbo-preview

# Or Anthropic Claude
# ANTHROPIC_API_KEY=sk-ant-your-key-here
# ANTHROPIC_MODEL=claude-3-opus-20240229

# Or Ollama (local)
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=llama2

# Processing Configuration
WINDOW_SIZE=6
WINDOW_OVERLAP=2
```

### 2. Run Refinement

```bash
# Basic usage (uses env config)
npm run dev -- input.srt

# Specify output file
npm run dev -- input.srt -o output.srt

# Use different provider
npm run dev -- input.srt -p claude

# Custom window size
npm run dev -- input.srt -w 8

# Dry run (preview windows)
npm run dev -- input.srt --dry-run

# Verbose logging
npm run dev -- input.srt --verbose
```

### 3. After Building

```bash
# Run as global command
npm run build
./dist/index.js input.srt

# Or use npm start
npm start -- input.srt
```

## Usage

```
subtitle-refiner [options] <input>

Arguments:
  input                      Input SRT file path

Options:
  -V, --version             output the version number
  -o, --output <file>       Output file path (default: input.refined.srt)
  -p, --provider <name>     LLM provider: openai|claude|ollama (default: "openai")
  -m, --model <name>        Model name (e.g., gpt-4, claude-3-opus)
  -w, --window-size <number> Window size (number of subtitle entries) (default: "6")
  --window-overlap <number> Window overlap size (default: "2")
  -P, --prompt <file>       Custom prompt file path
  --dry-run                 Preview windows without calling LLM (default: false)
  --verbose                 Show detailed processing logs (default: false)
  -h, --help                display help for command
```

## Examples

### Example 1: Basic Refinement

```bash
npm run dev -- video.eng-cmn.srt
```

Output: `video.eng-cmn.refined.srt`

### Example 2: Custom Window Size

For longer context (more expensive but better coherence):

```bash
npm run dev -- video.srt -w 10 --window-overlap 3
```

### Example 3: Using Claude

```bash
npm run dev -- video.srt -p claude -m claude-3-sonnet-20240229
```

### Example 4: Local Model (Ollama)

First, ensure Ollama is running:

```bash
ollama serve
ollama pull llama2
```

Then:

```bash
npm run dev -- video.srt -p ollama -m llama2
```

### Example 5: Custom Prompt

Create a custom prompt file (e.g., `my-prompt.txt`):

```
You are a grammar expert. Fix only grammatical errors and punctuation.
Do not change translations. Return JSON format: {"refined": [{"index": 1, "text": "..."}]}
```

Run with custom prompt:

```bash
npm run dev -- video.srt -P my-prompt.txt
```

### Example 6: Dry Run Preview

Preview how subtitles will be windowed:

```bash
npm run dev -- video.srt --dry-run
```

Output:
```
═══════════════════════════════════════════════════════════
Dry Run Mode - Preview Windows

ℹ Window 1/4 (entries 1-6)
  Entries: 1, 2, 3, 4, 5, 6
  Preview: [1] Hello, how are you? | 你好，你好吗？...

ℹ Window 2/4 (entries 5-10)
  Entries: 5, 6, 7, 8, 9, 10
  Context: 3, 4 (read-only)
  Preview: [5] I'm doing great! | 我很好！...
...
```

## How It Works

### Sliding Window Strategy

```
Subtitles: [1] [2] [3] [4] [5] [6] [7] [8] [9] [10]

Window 1: [1] [2] [3] [4] [5] [6]
Window 2:         [5] [6] [7] [8] [9] [10]
          ↑       ↑
     Context   Overlap (refinement reprocessed)
```

**Benefits:**
- **Context awareness**: LLM sees previous subtitles for coherence
- **Overlap**: Ensures consistent refinement at window boundaries
- **Manageable size**: Fits within LLM context limits
- **Cost-effective**: Process long subtitle files without huge API costs

### Bilingual Subtitle Format

Input SRT:
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

Both lines are refined (target language primarily, source if needed).

## Providers

### OpenAI

**Models:**
- `gpt-4-turbo-preview` - Best quality, larger context
- `gpt-4` - High quality, shorter context
- `gpt-3.5-turbo` - Faster, cheaper, good for simple fixes

**Configuration:**
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo-preview
```

### Anthropic Claude

**Models:**
- `claude-3-opus-20240229` - Best quality, largest context (200k tokens)
- `claude-3-sonnet-20240229` - Balanced quality and speed
- `claude-3-haiku-20240307` - Fastest, most cost-effective

**Configuration:**
```env
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-opus-20240229
```

### Ollama (Local)

**Requirements:**
- [Ollama](https://ollama.ai/) installed and running
- Model pulled (e.g., `ollama pull llama2`)

**Models:**
- `llama2` - General purpose
- `mistral` - High quality
- `codellama` - Code-focused
- Any other Ollama-compatible model

**Configuration:**
```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2
```

**Advantages:**
- ✅ Free (no API costs)
- ✅ Private (data stays local)
- ✅ No rate limits

**Disadvantages:**
- ❌ Slower than cloud APIs
- ❌ Requires powerful hardware (GPU recommended)
- ❌ May have lower quality than GPT-4/Claude

## Custom Prompts

Default prompt focuses on fixing translation mistakes. You can customize for different purposes:

### Grammar-Only Prompt (`prompts/grammar-only.txt`)

```
You are a grammar expert. Fix grammatical errors, punctuation, and capitalization.
Do not change the meaning or translation.

For bilingual subtitles, fix both lines.

Return JSON: {"refined": [{"index": 1, "text": "Corrected text\nSecond line"}]}
```

### Style Normalization Prompt

```
Normalize subtitle style:
- Use smart quotes (" ")
- Consistent ellipsis (…)
- Em dashes (—) for interruptions
- Proper capitalization

Preserve meaning and translation.

Return JSON: {"refined": [{"index": 1, "text": "..."}]}
```

### Translation Improvement Prompt

```
Improve translation quality:
- Fix mistranslations
- Make phrases more natural and idiomatic
- Adapt cultural references
- Maintain consistent terminology

Return JSON: {"refined": [{"index": 1, "text": "..."}]}
```

## Integration with stream-polyglot

This tool is designed to work seamlessly with [stream-polyglot](../README.md):

```bash
# Step 1: Generate bilingual subtitles with stream-polyglot
cd ../stream-polyglot
python -m main video.mp4 --lang eng:cmn --subtitle --subtitle-source-lang

# Step 2: Refine the generated subtitles
cd ../subtitle-refiner
npm run dev -- ../stream-polyglot/video.eng-cmn.srt

# Step 3: Use refined subtitles for voice cloning
cd ../stream-polyglot
python -m main video.mp4 --lang eng:cmn --trans-voice video.eng-cmn.refined.srt
```

## Project Structure

```
subtitle-refiner/
├── src/
│   ├── index.ts              # CLI entry point
│   ├── types.ts              # TypeScript type definitions
│   ├── parsers/
│   │   └── srt-parser.ts     # SRT parsing and generation
│   ├── refiners/
│   │   ├── llm-refiner.ts    # Core refinement logic
│   │   └── providers/        # LLM provider implementations
│   │       ├── factory.ts
│   │       ├── openai.ts
│   │       ├── claude.ts
│   │       └── ollama.ts
│   ├── prompts/
│   │   └── default-prompts.ts # Built-in system prompts
│   └── utils/
│       ├── window.ts         # Sliding window logic
│       └── logger.ts         # Colored logging
├── prompts/                  # User-editable prompt files
│   └── translation-fix.txt
├── examples/                 # Example SRT files
├── package.json
├── tsconfig.json
├── .env.example
└── README.md
```

## Development

```bash
# Install dependencies
npm install

# Run in development mode
npm run dev -- input.srt

# Build TypeScript
npm run build

# Run tests
npm test
```

## Troubleshooting

### Error: "OPENAI_API_KEY is required"

Create `.env` file with your API key:
```env
OPENAI_API_KEY=sk-your-key-here
```

### Error: "No response from LLM"

- Check API key is valid
- Check network connection
- Try with `--verbose` flag for detailed logs
- For Ollama, ensure service is running (`ollama serve`)

### Poor Refinement Quality

- Increase window size: `-w 10` (more context)
- Try different model: `-m gpt-4` (higher quality)
- Use custom prompt: `-P your-prompt.txt` (specific instructions)
- Check input quality (garbage in, garbage out)

### Rate Limit Errors

- Decrease window size: `-w 4` (fewer API calls)
- Add delay between requests (modify `src/refiners/llm-refiner.ts`)
- Switch to local model: `-p ollama`

## Cost Estimation

### OpenAI GPT-4 Turbo

- Input: $0.01 / 1K tokens
- Output: $0.03 / 1K tokens
- Typical subtitle entry: ~50 tokens
- Window of 6 entries: ~300 tokens input + ~350 tokens output
- **Cost per window**: ~$0.014
- **100 subtitles (17 windows)**: ~$0.24

### Anthropic Claude Opus

- Input: $0.015 / 1K tokens
- Output: $0.075 / 1K tokens
- **Cost per window**: ~$0.031
- **100 subtitles (17 windows)**: ~$0.53

### Ollama (Local)

- **Cost**: $0 (free, but requires hardware)

## Limitations

- Does not modify timing (by design)
- Does not merge/split subtitles (by design)
- Quality depends on LLM model chosen
- Requires API keys for cloud providers
- Processing time depends on subtitle count and provider

## Future Enhancements

- [ ] Caching refined results (avoid re-processing)
- [ ] Batch processing multiple SRT files
- [ ] Diff view (show changes before/after)
- [ ] Web UI for interactive refinement
- [ ] Support for more subtitle formats (ASS, VTT)
- [ ] Quality metrics (change statistics)

## License

MIT

## Contributing

Contributions welcome! Please open an issue or pull request.

## Related Projects

- [stream-polyglot](../stream-polyglot/) - Video translation with voice cloning
- [m4t](../../m4t/) - SeamlessM4T API server with GPT-SoVITS

## Author

Claude Code (AI Assistant) - 2025
