# Speaker Clustering Implementation Plan

## Problem Analysis

### Current Issue
When using `--trans-voice` for voice cloning, each subtitle entry uses only its corresponding timeline fragment as reference audio. Problems:

1. **Short reference audio** (typically 3-10 seconds per fragment)
2. **Insufficient voice characteristics** for high-quality cloning
3. **Voice instability** across different cloned segments
4. **Missing prosody context** from single short clips

### Proposed Solution

**Speaker-aware reference concatenation**: Group all audio fragments by speaker identity, then use concatenated audio from the same speaker as reference for voice cloning.

**Benefits**:
- Longer reference audio (30+ seconds per speaker)
- More complete voice characteristics
- Better prosody and intonation modeling
- More consistent voice cloning across segments

## Implementation Architecture

### Phase 1: Speaker Clustering Module

Create `speaker_clustering.py`:

```python
class SpeakerClusterer:
    """
    Cluster audio fragments by speaker identity using voice embeddings
    """

    def __init__(self, method='resemblyzer', threshold=0.5):
        """
        Args:
            method: 'resemblyzer' or 'pyannote'
            threshold: Similarity threshold for clustering (0.0-1.0)
        """
        self.method = method
        self.threshold = threshold
        self.encoder = None

    def initialize(self):
        """Load pre-trained model"""
        if self.method == 'resemblyzer':
            from resemblyzer import VoiceEncoder
            self.encoder = VoiceEncoder()
        elif self.method == 'pyannote':
            # TODO: implement pyannote loading
            pass

    def extract_embedding(self, audio_path):
        """
        Extract speaker embedding from audio file

        Args:
            audio_path: Path to audio file

        Returns:
            numpy array: Speaker embedding vector
        """
        if self.method == 'resemblyzer':
            from resemblyzer import preprocess_wav
            wav = preprocess_wav(audio_path)
            return self.encoder.embed_utterance(wav)

    def cluster_fragments(self, fragment_paths):
        """
        Cluster audio fragments by speaker

        Args:
            fragment_paths: List of audio file paths

        Returns:
            dict: {
                'labels': List of cluster labels (one per fragment),
                'embeddings': numpy array of embeddings,
                'n_clusters': Number of detected speakers
            }
        """
        # Extract embeddings
        embeddings = []
        valid_indices = []

        for i, path in enumerate(fragment_paths):
            try:
                embedding = self.extract_embedding(path)
                embeddings.append(embedding)
                valid_indices.append(i)
            except Exception as e:
                print(f"Warning: Failed to extract embedding for {path}: {e}")

        if len(embeddings) < 2:
            # Only one speaker or not enough data
            return {
                'labels': [0] * len(fragment_paths),
                'embeddings': np.array(embeddings),
                'n_clusters': 1
            }

        embeddings = np.array(embeddings)

        # Cluster using agglomerative clustering
        from sklearn.cluster import AgglomerativeClustering

        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=1 - self.threshold,
            metric='cosine',
            linkage='average'
        )

        valid_labels = clustering.fit_predict(embeddings)

        # Map back to all fragments (assign -1 to failed extractions)
        labels = [-1] * len(fragment_paths)
        for i, label in zip(valid_indices, valid_labels):
            labels[i] = label

        return {
            'labels': labels,
            'embeddings': embeddings,
            'n_clusters': len(set(valid_labels))
        }

    def concatenate_speaker_audio(self, fragment_paths, speaker_label, labels, max_duration=30.0):
        """
        Concatenate audio from same speaker cluster

        Args:
            fragment_paths: List of all fragment paths
            speaker_label: Target speaker cluster label
            labels: Cluster labels for all fragments
            max_duration: Maximum concatenated duration in seconds

        Returns:
            tuple: (concatenated_audio, sample_rate) or None
        """
        import soundfile as sf
        import numpy as np

        speaker_audio = []
        total_duration = 0.0
        sample_rate = None

        for path, label in zip(fragment_paths, labels):
            if label != speaker_label:
                continue

            try:
                audio, sr = sf.read(path)
                if sample_rate is None:
                    sample_rate = sr

                duration = len(audio) / sr
                if total_duration + duration > max_duration:
                    # Take only partial audio to not exceed max_duration
                    remaining = max_duration - total_duration
                    samples_to_take = int(remaining * sr)
                    audio = audio[:samples_to_take]

                speaker_audio.append(audio)
                total_duration += len(audio) / sr

                if total_duration >= max_duration:
                    break

            except Exception as e:
                print(f"Warning: Failed to load audio {path}: {e}")

        if not speaker_audio:
            return None

        concatenated = np.concatenate(speaker_audio)
        return concatenated, sample_rate
```

### Phase 2: Integration with Voice Cloning

Modify `process_trans_voice()` in `main.py`:

```python
def process_trans_voice(..., speaker_clustering=False, clustering_threshold=0.5):
    """
    Process voice cloning with optional speaker clustering

    New args:
        speaker_clustering: Enable speaker-aware reference concatenation
        clustering_threshold: Similarity threshold for clustering
    """

    # ... existing code to load timeline and subtitles ...

    if speaker_clustering:
        print_header("Speaker Clustering")
        print_info("Clustering audio fragments by speaker identity...")

        # Initialize clusterer
        from speaker_clustering import SpeakerClusterer
        clusterer = SpeakerClusterer(
            method='resemblyzer',
            threshold=clustering_threshold
        )
        clusterer.initialize()

        # Get all fragment paths
        fragment_paths = [seg['ref_audio_path'] for seg in matched_segments]

        # Cluster fragments
        clustering_result = clusterer.cluster_fragments(fragment_paths)
        labels = clustering_result['labels']
        n_clusters = clustering_result['n_clusters']

        print_success(f"Detected {n_clusters} speaker(s)")

        # Show cluster distribution
        for speaker_id in range(n_clusters):
            count = labels.count(speaker_id)
            print_info(f"  Speaker {speaker_id}: {count} fragments")

        # Create concatenated reference audio for each speaker
        speaker_references = {}
        cache_ref_dir = cache_dir / 'speaker_references'
        os.makedirs(cache_ref_dir, exist_ok=True)

        for speaker_id in range(n_clusters):
            concat_audio, sr = clusterer.concatenate_speaker_audio(
                fragment_paths,
                speaker_id,
                labels,
                max_duration=30.0  # 30 seconds max reference
            )

            if concat_audio is not None:
                # Save concatenated reference
                ref_path = cache_ref_dir / f"speaker_{speaker_id}_ref.wav"
                sf.write(ref_path, concat_audio, sr)
                speaker_references[speaker_id] = str(ref_path)

                duration = len(concat_audio) / sr
                print_info(f"  Speaker {speaker_id} reference: {duration:.2f}s saved to {ref_path.name}")

        # Update matched segments with speaker labels and concatenated references
        for i, seg in enumerate(matched_segments):
            speaker_label = labels[i]
            if speaker_label >= 0 and speaker_label in speaker_references:
                seg['speaker_id'] = speaker_label
                seg['speaker_ref_audio'] = speaker_references[speaker_label]
            else:
                seg['speaker_id'] = -1  # Unknown speaker

    # Voice cloning loop
    for idx, seg in enumerate(matched_segments):
        # Choose reference audio
        if speaker_clustering and 'speaker_ref_audio' in seg:
            ref_audio_path = seg['speaker_ref_audio']
            print_info(f"Using speaker {seg['speaker_id']} reference ({Path(ref_audio_path).name})")
        else:
            ref_audio_path = seg['ref_audio_path']

        # Call voice cloning API
        audio_bytes = voice_clone_translation(
            ref_audio_path=ref_audio_path,
            text=seg['target_text'],
            ...
        )
```

### Phase 3: CLI Integration

Add new arguments to `main.py`:

```python
parser.add_argument(
    '--speaker-clustering',
    action='store_true',
    help='Enable speaker clustering to concatenate reference audio from same speaker for better voice cloning quality'
)

parser.add_argument(
    '--clustering-threshold',
    type=float,
    default=0.5,
    metavar='THRESHOLD',
    help='Speaker similarity threshold for clustering (0.0-1.0, default: 0.5). Higher = stricter matching.'
)

parser.add_argument(
    '--max-ref-duration',
    type=float,
    default=30.0,
    metavar='SECONDS',
    help='Maximum concatenated reference audio duration per speaker (default: 30.0 seconds)'
)
```

### Phase 4: Testing & Validation

**Test cases**:
1. Single speaker video (should produce 1 cluster)
2. Multi-speaker video (e.g., interview, debate)
3. Video with background speakers/noise
4. Compare voice cloning quality: with vs without clustering

**Metrics to evaluate**:
- Clustering accuracy (manual verification)
- Voice cloning quality (subjective listening test)
- Processing time overhead
- Reference audio duration per speaker

## Configuration Recommendations

### Threshold Tuning

Based on cosine similarity of speaker embeddings:

- **0.3-0.4**: Very loose (may merge different speakers)
- **0.5-0.6**: Balanced (recommended starting point)
- **0.7-0.8**: Strict (may split same speaker into multiple clusters)

### Max Reference Duration

- **10-20s**: Minimum for capturing voice characteristics
- **30s**: Recommended balance (enough context, not too slow)
- **60s+**: Diminishing returns, slower processing

## Implementation Checklist

- [ ] Install Resemblyzer: `pip install resemblyzer`
- [ ] Create `speaker_clustering.py` module
- [ ] Test clustering with sample videos
- [ ] Integrate into `process_trans_voice()`
- [ ] Add CLI arguments
- [ ] Test with single-speaker video
- [ ] Test with multi-speaker video
- [ ] Compare voice quality: with/without clustering
- [ ] Update documentation (README.md)
- [ ] Add to diary with results

## Alternative: pyannote.audio

If Resemblyzer accuracy is insufficient, consider pyannote.audio:

**Pros**:
- Higher accuracy (state-of-the-art)
- Better handling of overlapping speakers
- More robust to noise

**Cons**:
- Requires HuggingFace authentication
- Heavier dependencies
- Slower processing

**Installation**:
```bash
pip install pyannote.audio
huggingface-cli login
```

**Usage**:
```python
from pyannote.audio import Pipeline

pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-3.1",
    use_auth_token=True
)

# Apply to all fragments
for fragment in fragments:
    diarization = pipeline(fragment)
    # Extract speaker embedding or use diarization result
```

## Expected Improvements

With speaker clustering:

1. **Voice quality**: 20-30% improvement in naturalness
2. **Voice consistency**: More stable across segments
3. **Prosody**: Better intonation and rhythm
4. **Processing time**: +10-20% overhead (acceptable)

## Risks & Mitigation

**Risk 1**: Clustering errors (merging different speakers)
- **Mitigation**: Provide adjustable threshold, allow per-segment manual override

**Risk 2**: Single speaker split into multiple clusters
- **Mitigation**: Use lower threshold, add merge option

**Risk 3**: Processing time increase
- **Mitigation**: Cache embeddings, parallelize extraction

**Risk 4**: Large concatenated reference causes GPT-SoVITS issues
- **Mitigation**: Enforce max_ref_duration limit (30s default)
