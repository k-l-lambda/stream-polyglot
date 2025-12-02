# Stream-Polyglot Test Suite

## Speaker Clustering Tests

### Core Tests

#### `test_speaker_clustering_module.py`
**Purpose**: Unit test for speaker_clustering.py module

Tests:
- Clusterer initialization
- Fragment clustering (first 50 fragments)
- Reference fragment selection
- Fragment concatenation
- Speaker-to-segment assignment

**Usage**:
```bash
cd ~/work/stream-polyglot
./env/bin/python tests/test_speaker_clustering_module.py
```

**Expected Output**: 8 speakers detected, reference audio generation successful

---

#### `test_speaker_clustering_full.py`
**Purpose**: Full integration test showing reference audio mapping for all fragments

Tests:
- Clustering on ALL 415 fragments
- Speaker statistics and distribution
- Reference audio generation (longest 2-3 fragments per speaker)
- Simulated subtitle segment matching
- Reference audio mapping display

**Usage**:
```bash
cd ~/work/stream-polyglot
./env/bin/python tests/test_speaker_clustering_full.py
```

**Expected Output**:
- 26 speakers detected
- Reference audio files generated in `test_speaker_references_full/`
- Mapping table showing which reference is used for sample segments

---

#### `test_speaker_clustering_dynamic.py`
**Purpose**: Test dynamic per-segment reference audio selection strategy

**Strategy**:
- Segments >= 10s: Use itself as reference
- Segments 5-10s: Use itself as reference
- Segments < 5s: Concatenate nearby fragments to reach 5-10s

**Usage**:
```bash
cd ~/work/stream-polyglot
./env/bin/python tests/test_speaker_clustering_dynamic.py
```

**Expected Output**:
- 12 test segments from different duration ranges
- Strategy distribution statistics
- Average reference duration: ~10s
- 91.8% of references in 5-10s range

---

### Research Tests (Historical)

#### `test_clustering_comparison.py`
Compare Resemblyzer vs pyannote.audio clustering methods

#### `test_comparison_50fragments.py`
Compare clustering results on first 50 fragments

#### `test_fragments_clustering.py`
Test fragment-based clustering approach

#### `test_resemblyzer_detailed.py`
Detailed Resemblyzer embedding analysis

#### `test_threshold_tuning.py`
Test different clustering thresholds (0.5, 0.6, 0.65, 0.7, 0.8)

---

## Utility Scripts

### `utils/generate_reference_mapping_with_text.py`
**Purpose**: Generate complete segment-to-reference mapping file with speech transcription

**Features**:
- Processes all 415 fragments
- Transcribes reference audio using m4t API
- Generates detailed mapping file with:
  - Segment timing and duration
  - Speaker assignment
  - Reference strategy used
  - Reference files with timing
  - Speech text for each reference fragment
  - Combined reference text

**Output**: `speaker_reference_mapping.txt` (~290KB)

**Usage**:
```bash
cd ~/work/stream-polyglot
./env/bin/python tests/utils/generate_reference_mapping_with_text.py
```

**Note**: Requires m4t API server running at http://localhost:8000

---

### `utils/show_concat_details.py`
**Purpose**: Show detailed examples of fragment concatenation for short segments

**Usage**:
```bash
cd ~/work/stream-polyglot
./env/bin/python tests/utils/show_concat_details.py
```

**Output**: Detailed breakdown showing how short fragments are concatenated to form 5-10s references

---

## Test Data

**Audio File**: `~/work/stream-polyglot/assets/066. 移民第五季 第十三集.mp3`

**Cache Directory**: `~/work/stream-polyglot/assets/.stream-polyglot-cache/066. 移民第五季 第十三集/`
- `timeline.json` - Fragment metadata
- `fragments/` - Individual audio fragments (415 files)
- `speaker_reference_mapping.txt` - Complete reference mapping

---

## Running All Tests

```bash
cd ~/work/stream-polyglot

# Quick test (50 fragments)
./env/bin/python tests/test_speaker_clustering_module.py

# Full test (415 fragments)
./env/bin/python tests/test_speaker_clustering_full.py

# Dynamic strategy test
./env/bin/python tests/test_speaker_clustering_dynamic.py

# Generate complete mapping
./env/bin/python tests/utils/generate_reference_mapping_with_text.py
```

---

## Key Findings

### Speaker Detection
- **Threshold 0.65**: 26 speakers (optimal for this audio)
- **Threshold 0.5**: 2 speakers (under-segmentation)
- **Threshold 0.8**: 80+ speakers (over-segmentation)

### Reference Audio Quality
- **Before optimization**: Many 1-2s short references
- **After optimization**:
  - Average: 6.2s
  - 91.8% in 5-10s range
  - Only 3.6% below 5s

### Strategy Distribution (391 segments)
- Long segments (>=10s): 6 (1.5%)
- Medium segments (5-10s): 25 (6.4%)
- **Short segments (<5s) with concatenation**: 352 (90.0%)
- Short segments using self: 8 (2.0%)

This optimization ensures **all segments have adequate reference audio for high-quality voice cloning**.
