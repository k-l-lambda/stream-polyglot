# subtitle-refiner v2.0

LLM-powered SRT subtitle refinement with function calling. Uses OpenAI GPT-4 (or compatible APIs) to improve translation quality.

## Key Features

- **Function Calling**: LLM marks subtitles as fine or refined via `this_is_fine()` / `this_should_be()`
- **Centered Window**: First unfinished subtitle stays at window center for optimal context
- **State Tracking**: Real-time progress tracking with finished/unfinished states
- **Retry Mechanism**: Automatic retry prompts when LLM makes no progress
- **Checkpoint System**: Automatic progress saving and resume support for long refinement jobs
- **Bilingual Support**: Refines both target and source language lines with proper ordering
- **OpenAI Compatible**: Works with any OpenAI-compatible API

## Bilingual Subtitle Convention

### Filename Format

```
{name}.{source}-{target}.srt
```

- **source**: Original audio language (e.g., `eng`, `jpn`, `cmn`)
- **target**: Translation language (e.g., `cmn`, `eng`, `jpn`)

### Display Order

**Target language at top, source language at bottom**

This is because audiences primarily read the target language (translation).

### Examples

```
video.eng-cmn.srt  → English source, Chinese target
                   → Display: Chinese at top, English at bottom

movie.jpn-eng.srt  → Japanese source, English target
                   → Display: English at top, Japanese at bottom

test.cmn-eng.srt   → Chinese source, English target
                   → Display: English at top, Chinese at bottom
```

### Sample Content

```srt
1
00:00:01,000 --> 00:00:04,000
你好，你今天好吗？           ← Target (Chinese) at top
Hello, how are you today?    ← Source (English) at bottom
```

## Quick Start

### 1. Install Dependencies

```bash
npm install
npm run build
```

### 2. Configure Environment

Create `.env` file:

```bash
# OpenAI (official)
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4-turbo-preview

# Or use OpenAI-compatible API (e.g., local model)
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-4
OPENAI_BASE_URL=http://localhost:8000/v1
```

### 3. Run

```bash
# Dry run (preview windows, no API calls)
npm run dev -- examples/test.srt --dry-run -w 10

# Actual refinement
npm run dev -- input.srt -w 6

# Custom window size and retries
npm run dev -- input.srt -w 8 --max-retries 5

# Verbose logging
npm run dev -- input.srt --verbose

# With checkpoint system (auto-save every 5 rounds)
npm run dev -- input.srt --checkpoint-interval 5

# Resume from checkpoint
npm run dev -- input.srt --resume --checkpoint-interval 5
```

## Checkpoint System

For long refinement jobs (100+ subtitles), the checkpoint system automatically saves progress:

### Features

- **Automatic Saving**: Saves checkpoint every N rounds (default: 5)
- **Resume Support**: Continue from last checkpoint with `--resume` flag
- **Error Recovery**: Saves checkpoint before exit on errors
- **Auto-Cleanup**: Deletes checkpoint on successful completion

### Usage

```bash
# Enable checkpoints (save every 5 rounds)
npm run dev -- large-file.srt --checkpoint-interval 5

# If process crashes or is interrupted
# Resume from last checkpoint
npm run dev -- large-file.srt --resume --checkpoint-interval 5
```

### Checkpoint File

- **Location**: Same directory as input file
- **Filename**: `input.checkpoint.json`
- **Contents**: Subtitle states, progress stats, window position
- **Size**: ~2-5x input file size (includes all metadata)

### Example

```bash
# Start refinement
$ npm run dev -- movie.eng-cmn.srt --checkpoint-interval 10

# ... processing...
# ℹ Checkpoint saved (round 10)
# ℹ Checkpoint saved (round 20)
# ^C (interrupted at round 25)

# Resume later
$ npm run dev -- movie.eng-cmn.srt --resume --checkpoint-interval 10
# ℹ Found checkpoint:
# Checkpoint from 2025-11-21 15:30:00
# Progress: 45/128 (35.2%)
# Rounds: 25, LLM calls: 27
# ✓ Resuming from checkpoint...
```

## How It Works

### Function Calling Architecture

LLM reviews subtitles and calls functions:

```typescript
// Subtitle is acceptable
this_is_fine(5)

// Subtitle needs refinement
this_should_be(6,
  "Improved source text",        // first_lang_text (source)
  "Improved translation text"    // second_lang_text (target)
)
// Note: Output will display target at top, source at bottom
```

### Centered Window Strategy

Window keeps first unfinished subtitle at center:

```
Round 1: [1u 2u 3u 4u 5u 6u 7u 8u 9u 10u]
          ^^^^^^^^^^ center

Round 2: [3f 4f 5f 6u 7u 8u 9u 10u 11u 12u]
                    ^^^^^^^^^^ center (moved forward)
```

- **Context**: Finished subtitles before center (read-only)
- **To Process**: Unfinished subtitles at/after center

### Processing Loop

1. Create window centered on first unfinished
2. Send to LLM with function calling
3. Process function calls (mark finished/refined)
4. Check progress:
   - **Progress made**: Move window forward
   - **No progress**: Send retry prompt
   - **Still no progress after max retries**: Fail and exit

## Configuration

### Window Size

Default: 10 subtitles per window

```bash
# Small window (less context, cheaper)
npm run dev -- input.srt -w 6

# Large window (more context, better quality)
npm run dev -- input.srt -w 15
```

### Max Retries

Default: 3 attempts when LLM makes no progress

```bash
npm run dev -- input.srt --max-retries 5
```

## Use Cases

### Example 1: Official OpenAI

```bash
# .env
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4-turbo-preview

npm run dev -- input.srt
```

### Example 2: Azure OpenAI

```bash
# .env
OPENAI_API_KEY=your-azure-key
OPENAI_MODEL=gpt-4
OPENAI_BASE_URL=https://your-resource.openai.azure.com/openai/deployments/your-deployment

npm run dev -- input.srt
```

### Example 3: Local vLLM Server

```bash
# .env
OPENAI_API_KEY=dummy-key
OPENAI_MODEL=mistralai/Mixtral-8x7B-Instruct-v0.1
OPENAI_BASE_URL=http://localhost:8000/v1

npm run dev -- input.srt
```

### Example 4: Together AI

```bash
# .env
OPENAI_API_KEY=your-together-key
OPENAI_MODEL=mistralai/Mixtral-8x7B-Instruct-v0.1
OPENAI_BASE_URL=https://api.together.xyz/v1

npm run dev -- input.srt
```

## Integration with stream-polyglot

```bash
# Step 1: Generate bilingual subtitles
cd ../stream-polyglot
python -m main video.mp4 --lang eng:cmn --subtitle --subtitle-source-lang

# Step 2: Refine subtitles
cd ../subtitle-refiner
npm run dev -- ../stream-polyglot/video.eng-cmn.srt

# Step 3: Use refined subtitles for voice cloning
cd ../stream-polyglot
python -m main video.mp4 --lang eng:cmn --trans-voice video.eng-cmn.refined.srt
```

## Output

Input: `video.eng-cmn.srt`
Output: `video.eng-cmn.refined.srt`

Progress display:

```
Round 1
───────────────────────────────────────
Window: 1-10
First unfinished: #1 (center)
Context: 0 finished
To process: 10 unfinished

  ○ [1] 你好 | Hello ← CENTER
  ○ [2] 谢谢 | Thank you
  ...

✓ Processed 10 function calls
ℹ Progress: 10/50 finished
───────────────────────────────────────

Round 2
...
```

## Troubleshooting

### Error: "No progress after N rounds"

LLM is not calling functions properly. Try:
- Use more capable model (gpt-4 instead of gpt-3.5)
- Increase `--max-retries`
- Check API compatibility (must support function calling)

### Error: "OPENAI_API_KEY is required"

Create `.env` file with your API key.

### Poor refinement quality

- Increase window size (`-w 15`) for more context
- Use better model (`gpt-4-turbo-preview`)
- Ensure input subtitles have reasonable quality

## Architecture

```
subtitle-refiner/
├── src/
│   ├── types.ts                    # TypeScript types
│   ├── index.ts                    # CLI entry
│   ├── parsers/srt-parser.ts       # SRT I/O
│   ├── utils/
│   │   ├── state-manager.ts        # State tracking
│   │   ├── window.ts               # Centered window
│   │   ├── function-tools.ts       # Function definitions
│   │   └── logger.ts               # Colored logging
│   ├── refiners/
│   │   ├── llm-refiner.ts          # Main loop
│   │   └── providers/
│   │       ├── openai.ts           # OpenAI provider
│   │       └── factory.ts          # Provider factory
│   └── prompts/
│       └── default-prompts.ts      # System prompts
└── examples/test.srt               # Sample file
```

## Requirements

- Node.js 18+
- TypeScript 5+
- OpenAI API key (or compatible service)

## License

MIT

## Version

2.0.0 - Complete rewrite with function calling and centered window strategy
