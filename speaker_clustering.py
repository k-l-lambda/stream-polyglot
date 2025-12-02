#!/usr/bin/env python3
"""
Speaker clustering module for identifying and grouping audio fragments by speaker identity.

Uses Resemblyzer for speaker embedding extraction and sklearn for clustering.
"""

import numpy as np
import soundfile as sf
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import warnings


class SpeakerClusterer:
    """
    Speaker clustering using voice embeddings to identify and group fragments by speaker.
    """

    def __init__(self, method: str = 'resemblyzer', threshold: float = 0.65):
        """
        Initialize speaker clusterer.

        Args:
            method: Clustering method ('resemblyzer' supported)
            threshold: Similarity threshold for clustering (0-1)
                      Higher = fewer speakers (more aggressive grouping)
                      Lower = more speakers (more conservative grouping)
                      Recommended: 0.5 for 2 speakers, 0.65 for 8 speakers
        """
        self.method = method
        self.threshold = threshold
        self.encoder = None

        if method == 'resemblyzer':
            try:
                from resemblyzer import VoiceEncoder
                self.encoder = VoiceEncoder()
            except ImportError:
                raise ImportError(
                    "Resemblyzer not installed. Install with: pip install resemblyzer"
                )
        else:
            raise ValueError(f"Unsupported clustering method: {method}")

    def cluster_fragments(
        self,
        fragments_dir: Path,
        timeline: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """
        Cluster audio fragments by speaker identity.

        Args:
            fragments_dir: Directory containing fragment WAV files
            timeline: List of fragment metadata dicts with 'id', 'file', 'start', 'end'

        Returns:
            Dictionary mapping speaker_id to list of fragment info:
            {
                'speaker_0': [
                    {'fragment_id': 0, 'file': 'fragment_...wav', 'start': 1.2, 'end': 5.3, 'duration': 4.1},
                    ...
                ],
                'speaker_1': [...],
                ...
            }
        """
        if self.method == 'resemblyzer':
            return self._cluster_with_resemblyzer(fragments_dir, timeline)
        else:
            raise ValueError(f"Unsupported method: {self.method}")

    def _cluster_with_resemblyzer(
        self,
        fragments_dir: Path,
        timeline: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """
        Cluster fragments using Resemblyzer voice embeddings.

        Args:
            fragments_dir: Directory containing fragment WAV files
            timeline: List of fragment metadata

        Returns:
            Speaker clusters dict
        """
        from resemblyzer import preprocess_wav
        from sklearn.cluster import AgglomerativeClustering

        # Extract embeddings
        embeddings = []
        valid_fragments = []

        for frag in timeline:
            frag_path = fragments_dir / frag['file']

            if not frag_path.exists():
                warnings.warn(f"Fragment file not found: {frag_path}")
                continue

            try:
                # Load and preprocess audio
                wav = preprocess_wav(frag_path)

                # Skip very short fragments (< 0.4 seconds)
                if len(wav) < 6400:  # 16000 Hz * 0.4s
                    warnings.warn(f"Fragment too short, skipping: {frag['file']}")
                    continue

                # Extract embedding
                embedding = self.encoder.embed_utterance(wav)
                embeddings.append(embedding)

                # Store fragment info with duration
                duration = frag['end'] - frag['start']
                frag_info = {
                    'fragment_id': frag['id'],
                    'file': frag['file'],
                    'start': frag['start'],
                    'end': frag['end'],
                    'duration': duration
                }
                valid_fragments.append(frag_info)

            except Exception as e:
                warnings.warn(f"Failed to process fragment {frag['file']}: {e}")
                continue

        if len(embeddings) == 0:
            raise RuntimeError("No valid fragments for clustering")

        # Convert to numpy array
        embeddings = np.array(embeddings)

        # Perform agglomerative clustering
        # distance_threshold = 1 - similarity_threshold
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=1 - self.threshold,
            metric='cosine',
            linkage='average'
        )

        labels = clustering.fit_predict(embeddings)

        # Group fragments by speaker
        speaker_clusters = {}
        for idx, label in enumerate(labels):
            speaker_id = f"speaker_{label}"

            if speaker_id not in speaker_clusters:
                speaker_clusters[speaker_id] = []

            speaker_clusters[speaker_id].append(valid_fragments[idx])

        return speaker_clusters

    def select_reference_fragments(
        self,
        cluster: List[Dict],
        max_duration: float = 30.0
    ) -> List[Path]:
        """
        Select longest 2-3 fragments from a speaker cluster for reference audio.

        Args:
            cluster: List of fragment info dicts from one speaker
            max_duration: Maximum total duration in seconds

        Returns:
            List of Path objects to selected fragment files
        """
        # Sort fragments by duration (longest first)
        sorted_fragments = sorted(cluster, key=lambda x: x['duration'], reverse=True)

        # Select top fragments until max_duration reached
        selected = []
        total_duration = 0.0

        for frag in sorted_fragments:
            if total_duration + frag['duration'] > max_duration:
                # Check if we have at least 1 fragment
                if len(selected) == 0:
                    # Take the longest one even if over limit
                    selected.append(frag)
                break

            selected.append(frag)
            total_duration += frag['duration']

            # Limit to 3 fragments
            if len(selected) >= 3:
                break

        # Return file paths
        return [frag['file'] for frag in selected]

    def concatenate_fragments(
        self,
        fragment_files: List[str],
        fragments_dir: Path,
        output_path: Path
    ) -> Path:
        """
        Concatenate multiple fragment audio files into one reference audio.

        Args:
            fragment_files: List of fragment filenames
            fragments_dir: Directory containing fragment files
            output_path: Path to save concatenated audio

        Returns:
            Path to concatenated audio file
        """
        # Load all fragments
        audio_segments = []
        sample_rate = None

        for frag_file in fragment_files:
            frag_path = fragments_dir / frag_file

            if not frag_path.exists():
                warnings.warn(f"Fragment not found: {frag_path}, skipping")
                continue

            try:
                audio, sr = sf.read(frag_path)

                # Ensure consistent sample rate
                if sample_rate is None:
                    sample_rate = sr
                elif sr != sample_rate:
                    warnings.warn(
                        f"Sample rate mismatch: {sr} vs {sample_rate}, "
                        f"skipping {frag_file}"
                    )
                    continue

                # Convert stereo to mono if needed
                if len(audio.shape) > 1:
                    audio = audio.mean(axis=1)

                audio_segments.append(audio)

            except Exception as e:
                warnings.warn(f"Failed to load fragment {frag_file}: {e}")
                continue

        if len(audio_segments) == 0:
            raise RuntimeError("No valid audio segments to concatenate")

        # Concatenate all segments
        concatenated_audio = np.concatenate(audio_segments)

        # Save to output file
        sf.write(output_path, concatenated_audio, sample_rate)

        return output_path

    def select_reference_for_segment(
        self,
        segment_timing: Dict[str, float],
        speaker_clusters: Dict[str, List[Dict]],
        fragments_dir: Path,
        min_duration: float = 5.0,
        target_duration: float = 10.0
    ) -> Tuple[Optional[str], List[str], float]:
        """
        Dynamically select reference audio for a specific segment.

        Strategy:
        - If segment's own fragment >= 10s: use itself
        - If segment's own fragment < 5s: find nearby fragments from same speaker to reach 5-10s

        Args:
            segment_timing: Dict with 'start' and 'end' times
            speaker_clusters: Speaker clusters from cluster_fragments()
            fragments_dir: Directory containing fragment files
            min_duration: Minimum reference duration (default: 5.0s)
            target_duration: Target reference duration (default: 10.0s)

        Returns:
            Tuple of (speaker_id, [fragment_files], total_duration)
        """
        seg_start = segment_timing['start']
        seg_end = segment_timing['end']
        seg_mid = (seg_start + seg_end) / 2

        # Step 1: Find which speaker this segment belongs to
        speaker_id = self.assign_speaker_to_segment(segment_timing, speaker_clusters)

        if not speaker_id or speaker_id not in speaker_clusters:
            return None, [], 0.0

        cluster = speaker_clusters[speaker_id]

        # Step 2: Find the matching fragment for this segment
        matching_fragment = None
        best_overlap = 0.0

        for frag in cluster:
            frag_start = frag['start']
            frag_end = frag['end']

            # Calculate overlap
            overlap_start = max(seg_start, frag_start)
            overlap_end = min(seg_end, frag_end)
            overlap = max(0.0, overlap_end - overlap_start)

            # Bonus for midpoint match
            if frag_start <= seg_mid <= frag_end:
                overlap += 10.0

            if overlap > best_overlap:
                best_overlap = overlap
                matching_fragment = frag

        if not matching_fragment:
            return speaker_id, [], 0.0

        # Step 3: Check fragment duration
        frag_duration = matching_fragment['duration']

        # Case 1: Fragment is already >= 10s, use it directly
        if frag_duration >= target_duration:
            return speaker_id, [matching_fragment['file']], frag_duration

        # Case 2: Fragment is < 5s, find nearby fragments to reach 5-10s
        if frag_duration < min_duration:
            # Sort fragments by time distance from matching fragment
            sorted_by_distance = sorted(
                cluster,
                key=lambda f: abs((f['start'] + f['end']) / 2 - (matching_fragment['start'] + matching_fragment['end']) / 2)
            )

            selected = [matching_fragment]
            total_duration = frag_duration

            # Add nearby fragments until we reach target_duration
            for frag in sorted_by_distance:
                if frag == matching_fragment:
                    continue

                if total_duration >= target_duration:
                    break

                # Don't add if it would exceed target_duration too much
                if total_duration + frag['duration'] > target_duration * 1.5:
                    continue

                selected.append(frag)
                total_duration += frag['duration']

                if total_duration >= min_duration:
                    break

            # Sort selected fragments by time order for natural concatenation
            selected.sort(key=lambda f: f['start'])

            return speaker_id, [f['file'] for f in selected], total_duration

        # Case 3: Fragment is 5-10s, use it directly
        return speaker_id, [matching_fragment['file']], frag_duration

    def assign_speaker_to_segment(
        self,
        segment_timing: Dict[str, float],
        speaker_clusters: Dict[str, List[Dict]]
    ) -> Optional[str]:
        """
        Find which speaker cluster a subtitle segment belongs to based on timing overlap.

        Args:
            segment_timing: Dict with 'start' and 'end' times in seconds
            speaker_clusters: Speaker clusters from cluster_fragments()

        Returns:
            speaker_id string (e.g., 'speaker_0') or None if no match
        """
        seg_start = segment_timing['start']
        seg_end = segment_timing['end']
        seg_mid = (seg_start + seg_end) / 2

        # Find which speaker has fragments overlapping with this segment
        best_speaker = None
        best_overlap = 0.0

        for speaker_id, fragments in speaker_clusters.items():
            total_overlap = 0.0

            for frag in fragments:
                frag_start = frag['start']
                frag_end = frag['end']

                # Calculate overlap duration
                overlap_start = max(seg_start, frag_start)
                overlap_end = min(seg_end, frag_end)
                overlap = max(0.0, overlap_end - overlap_start)

                total_overlap += overlap

                # Also check if segment midpoint is within fragment
                if frag_start <= seg_mid <= frag_end:
                    total_overlap += 10.0  # Bonus for midpoint match

            if total_overlap > best_overlap:
                best_overlap = total_overlap
                best_speaker = speaker_id

        return best_speaker
