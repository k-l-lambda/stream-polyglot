# Speaker Clustering Research for Voice Clone Optimization

> **Research Date**: 2025-11-30
>
> **Search Sources**:
> - [Top 8 speaker diarization libraries and APIs in 2025](https://assemblyai.com/blog/top-speaker-diarization-libraries-and-apis)
> - [pyannote/pyannote-audio GitHub](https://github.com/pyannote/pyannote-audio)
> - [Best Speaker Diarization Models Comparison 2025](https://brasstranscripts.com/blog/speaker-diarization-models-comparison)
> - [Awesome Diarization (curated list)](https://github.com/wq2012/awesome-diarization)

## Problem Statement

Current issue: Reference audio segments for voice cloning may be too short, lacking sufficient context for high-quality voice reproduction.

**Proposed solution**: Cluster all audio segments by speaker identity, then use concatenated audio from the same speaker as reference for voice cloning.

## Speaker Identification and Clustering Methods

### 1. **pyannote.audio** (Recommended)
- **Repository**: https://github.com/pyannote/pyannote-audio
- **Features**:
  - State-of-the-art speaker diarization
  - Speaker embedding extraction
  - Speaker verification and identification
  - Pre-trained models available
  - Active development (2024-2025)

- **Key Components**:
  - `pyannote.audio.pipelines.SpeakerDiarization`: End-to-end pipeline
  - `pyannote.audio.Model`: Pre-trained embedding models
  - Speaker embeddings can be clustered with sklearn

- **Installation**:
  ```bash
  pip install pyannote.audio
  ```

- **Usage Example**:
  ```python
  from pyannote.audio import Pipeline

  # Load pre-trained pipeline
  pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")

  # Apply to audio file
  diarization = pipeline("audio.wav")

  # Access speaker segments
  for turn, _, speaker in diarization.itertracks(yield_label=True):
      print(f"Speaker {speaker}: {turn.start:.1f}s - {turn.end:.1f}s")
  ```

- **Pros**:
  - High accuracy
  - Easy to use
  - Well-maintained
  - Supports both speaker diarization and embedding extraction

- **Cons**:
  - Requires HuggingFace authentication token for some models
  - GPU recommended for real-time processing

### 2. **Resemblyzer** (Speaker Embedding)
- **Repository**: https://github.com/resemble-ai/Resemblyzer
- **Features**:
  - Extract speaker embeddings (d-vectors)
  - Based on GE2E (Generalized End-to-End) loss
  - Simple API for voice similarity

- **Installation**:
  ```bash
  pip install resemblyzer
  ```

- **Usage Example**:
  ```python
  from resemblyzer import VoiceEncoder, preprocess_wav
  from pathlib import Path
  import numpy as np

  # Load encoder
  encoder = VoiceEncoder()

  # Extract embeddings from multiple audio files
  wav_fpaths = list(Path("audio_dir").glob("*.wav"))
  wavs = [preprocess_wav(fpath) for fpath in wav_fpaths]

  # Compute speaker embeddings
  embeddings = np.array([encoder.embed_utterance(wav) for wav in wavs])

  # Cluster with sklearn
  from sklearn.cluster import AgglomerativeClustering
  clustering = AgglomerativeClustering(n_clusters=None, distance_threshold=0.5)
  labels = clustering.fit_predict(embeddings)
  ```

- **Pros**:
  - Lightweight and fast
  - No authentication required
  - Good for speaker verification

- **Cons**:
  - No built-in diarization pipeline
  - Older model (pre-2024)
  - Less accurate than pyannote

### 3. **SpeechBrain**
- **Repository**: https://github.com/speechbrain/speechbrain
- **Features**:
  - Complete speech processing toolkit
  - Speaker recognition and diarization
  - Multiple pre-trained models
  - Active development

- **Installation**:
  ```bash
  pip install speechbrain
  ```

- **Usage Example**:
  ```python
  from speechbrain.pretrained import SpeakerRecognition

  # Load model
  verification = SpeakerRecognition.from_hparams(
      source="speechbrain/spkrec-ecapa-voxceleb",
      savedir="pretrained_models/spkrec-ecapa-voxceleb"
  )

  # Verify if two audio files are from same speaker
  score, prediction = verification.verify_files("audio1.wav", "audio2.wav")
  ```

- **Pros**:
  - Comprehensive toolkit
  - State-of-the-art models
  - Good documentation

- **Cons**:
  - Heavier dependency
  - Steeper learning curve

### 4. **Western Speakers** (Simple Clustering)
- **Repository**: https://github.com/wq2012/SpectralCluster
- **Features**:
  - Spectral clustering for speaker diarization
  - Works with pre-computed embeddings
  - Lightweight

- **Installation**:
  ```bash
  pip install spectralcluster
  ```

- **Usage Example**:
  ```python
  from spectralcluster import SpectralClusterer

  # embeddings: numpy array of shape (n_segments, embedding_dim)
  clusterer = SpectralClusterer(
      min_clusters=1,
      max_clusters=10,
      p_percentile=0.95
  )
  labels = clusterer.predict(embeddings)
  ```

## Recommended Approach for stream-polyglot

### Option 1: pyannote.audio (Best for accuracy) ⭐ Recommended

**According to 2025 research**:
- AssemblyAI reports pyannote.audio achieved **10.1% improvement in DER** (Diarization Error Rate) in 2024-2025
- Listed as top speaker diarization library in multiple 2025 comparisons
- State-of-the-art performance with active development

**Workflow**:
1. Extract all audio fragments from timeline
2. Use pyannote to extract speaker embeddings for each fragment
3. Cluster embeddings using cosine similarity threshold
4. For each subtitle entry, concatenate reference audio from same speaker cluster
5. Pass concatenated audio as reference to GPT-SoVITS

**Pros**:
- Highest accuracy
- End-to-end pipeline available
- Can handle multiple speakers automatically

**Cons**:
- Requires HuggingFace token
- Heavier dependency

### Option 2: Resemblyzer + Sklearn (Best for simplicity)

**Workflow**:
1. Extract speaker embeddings using Resemblyzer
2. Cluster with sklearn (AgglomerativeClustering or DBSCAN)
3. Group audio fragments by cluster
4. Concatenate audio within each cluster for reference

**Pros**:
- Lightweight
- No authentication required
- Easy to integrate

**Cons**:
- Lower accuracy than pyannote
- Need to tune clustering parameters

### Option 3: Hybrid Approach

Use Resemblyzer for embedding extraction + pyannote's clustering logic:
- Fast embedding extraction
- Robust clustering algorithm
- Balance between speed and accuracy

## Integration Plan

### Phase 1: Add Speaker Clustering Module

Create `speaker_clustering.py`:
```python
class SpeakerClusterer:
    def __init__(self, method='resemblyzer'):
        self.method = method

    def extract_embeddings(self, audio_paths):
        """Extract speaker embeddings from audio files"""
        pass

    def cluster_speakers(self, embeddings, threshold=0.5):
        """Cluster embeddings into speaker groups"""
        pass

    def group_fragments_by_speaker(self, fragments, labels):
        """Group audio fragments by speaker identity"""
        pass
```

### Phase 2: Modify Voice Cloning Workflow

Update `process_trans_voice()`:
1. After loading timeline fragments
2. Extract speaker embeddings for all fragments
3. Cluster fragments by speaker
4. For each subtitle entry, find matching speaker cluster
5. Concatenate multiple fragments from same speaker as reference
6. Pass concatenated reference to voice cloning API

### Phase 3: Configuration Options

Add CLI arguments:
- `--speaker-clustering`: Enable speaker clustering
- `--clustering-method`: Choose method (resemblyzer/pyannote)
- `--speaker-threshold`: Similarity threshold for clustering
- `--min-ref-duration`: Minimum reference audio duration (e.g., 5 seconds)

## Next Steps

1. **Prototype with Resemblyzer** (quickest to test)
2. **Evaluate clustering quality** with sample videos
3. **Measure voice clone improvement** with clustered references
4. **Compare with pyannote** if Resemblyzer results are insufficient
5. **Optimize for production** (caching, parallel processing)

## References

- pyannote.audio: https://github.com/pyannote/pyannote-audio
- Resemblyzer: https://github.com/resemble-ai/Resemblyzer
- SpeechBrain: https://github.com/speechbrain/speechbrain
- SpectralCluster: https://github.com/wq2012/SpectralCluster
