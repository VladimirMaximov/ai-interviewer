"""Optional local pyannote/SpeechBrain speaker analysis adapter.

Heavy ML packages and model weights are loaded lazily. API startup and the normal
transcription path therefore remain available when the optional proctoring extra
has not been installed.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from app.domain.proctoring import (
    DetectedVoiceEvent,
    MonitoringEventKind,
    ReferenceAudio,
    TimeInterval,
    VoiceAnalysisResult,
    VoiceProfileStatus,
    VoiceProfileValidation,
    merge_intervals,
)


@dataclass(frozen=True)
class _SpeakerTurn:
    start_seconds: float
    end_seconds: float
    speaker: str


class PyannoteVoiceAnalyzer:
    """Detect speaker overlap and compare diarized speakers to two references."""

    name = "pyannote_speechbrain"
    version = "bootstrap_v1"

    def __init__(
        self,
        *,
        huggingface_token: str | None,
        diarization_model: str = "pyannote/speaker-diarization-community-1",
        embedding_model: str = "speechbrain/spkrec-ecapa-voxceleb",
        embedding_cache: str = "apps/api/models/speechbrain-spkrec-ecapa",
        minimum_reference_speech_seconds: float = 20.0,
        reference_similarity_threshold: float = 0.65,
        speaker_similarity_threshold: float = 0.55,
    ) -> None:
        self._token = huggingface_token
        self._diarization_model = diarization_model
        self._embedding_model = embedding_model
        self._embedding_cache = embedding_cache
        self._minimum_reference_speech_seconds = minimum_reference_speech_seconds
        self._reference_similarity_threshold = reference_similarity_threshold
        self._speaker_similarity_threshold = speaker_similarity_threshold
        self._pipeline: Any | None = None
        self._speaker_encoder: Any | None = None
        self._torch: Any | None = None
        self._torchaudio: Any | None = None

    def validate_references(
        self, references: tuple[ReferenceAudio, ReferenceAudio]
    ) -> VoiceProfileValidation:
        """Require two clean, mutually consistent answers before enabling matching."""

        try:
            embeddings = []
            total_speech = 0.0
            for reference in references:
                turns = self._turns(reference.path)
                speakers = {turn.speaker for turn in turns}
                if len(speakers) != 1 or self._overlaps(turns):
                    return VoiceProfileValidation(
                        VoiceProfileStatus.NOT_READY,
                        "reference_contains_multiple_speakers",
                    )
                clean_turns = self._exclude(turns, reference.excluded_intervals)
                total_speech += sum(
                    turn.end_seconds - turn.start_seconds for turn in clean_turns
                )
                embedding = self._embedding(reference.path, clean_turns)
                if embedding is None:
                    return VoiceProfileValidation(
                        VoiceProfileStatus.NOT_READY,
                        "insufficient_clean_reference_audio",
                    )
                embeddings.append(embedding)
            if total_speech < self._minimum_reference_speech_seconds:
                return VoiceProfileValidation(
                    VoiceProfileStatus.NOT_READY,
                    "insufficient_clean_reference_audio",
                )
            similarity = self._cosine(embeddings[0], embeddings[1])
            if similarity < self._reference_similarity_threshold:
                return VoiceProfileValidation(
                    VoiceProfileStatus.NOT_READY,
                    "reference_voices_are_inconsistent",
                )
            return VoiceProfileValidation(VoiceProfileStatus.READY)
        except (ImportError, RuntimeError, OSError):
            return VoiceProfileValidation(
                VoiceProfileStatus.NOT_READY,
                "voice_model_unavailable",
            )

    def inspect(self, target: Path) -> VoiceAnalysisResult:
        """Detect multiple/overlapping speakers before a reference is ready."""

        turns = self._turns(target)
        events = self._speaker_structure_events(turns)
        return VoiceAnalysisResult(
            VoiceProfileValidation(VoiceProfileStatus.COLLECTING),
            tuple(events),
            self.name,
            self.version,
        )

    def analyze(
        self,
        references: tuple[ReferenceAudio, ReferenceAudio],
        target: Path,
    ) -> VoiceAnalysisResult:
        """Return bounded intervals; no result is a hiring decision."""

        profile = self.validate_references(references)
        if profile.status is not VoiceProfileStatus.READY:
            return VoiceAnalysisResult(profile, (), self.name, self.version)

        reference_embeddings = []
        for reference in references:
            turns = self._exclude(
                self._turns(reference.path), reference.excluded_intervals
            )
            embedding = self._embedding(reference.path, turns)
            if embedding is None:
                unavailable = VoiceProfileValidation(
                    VoiceProfileStatus.NOT_READY,
                    "insufficient_clean_reference_audio",
                )
                return VoiceAnalysisResult(unavailable, (), self.name, self.version)
            reference_embeddings.append(embedding)

        reference_embedding = self._mean(reference_embeddings)
        turns = self._turns(target)
        by_speaker: dict[str, list[_SpeakerTurn]] = {}
        for turn in turns:
            by_speaker.setdefault(turn.speaker, []).append(turn)
        similarities: dict[str, float] = {}
        for speaker, speaker_turns in by_speaker.items():
            embedding = self._embedding(target, speaker_turns)
            if embedding is not None:
                similarities[speaker] = self._cosine(reference_embedding, embedding)

        candidate_speaker = (
            max(similarities, key=similarities.get) if similarities else None
        )
        events = self._speaker_structure_events(
            turns, candidate_speaker=candidate_speaker
        )
        for speaker, speaker_turns in by_speaker.items():
            similarity = similarities.get(speaker)
            if similarity is None:
                continue
            mismatch = similarity < self._speaker_similarity_threshold
            kinds = (
                [MonitoringEventKind.SPEAKER_MISMATCH] if mismatch else []
            )
            confidence = min(1.0, max(0.0, 1.0 - similarity)) if mismatch else None
            intervals = merge_intervals(
                [self._interval(turn) for turn in speaker_turns]
            )
            for kind in kinds:
                events.extend(
                    DetectedVoiceEvent(kind, interval, confidence)
                    for interval in intervals
                )

        return VoiceAnalysisResult(profile, tuple(events), self.name, self.version)

    def _speaker_structure_events(
        self,
        turns: list[_SpeakerTurn],
        *,
        candidate_speaker: str | None = None,
    ) -> list[DetectedVoiceEvent]:
        events = [
            DetectedVoiceEvent(
                MonitoringEventKind.OVERLAPPING_SPEECH,
                interval,
            )
            for interval in self._overlaps(turns)
        ]
        by_speaker: dict[str, list[_SpeakerTurn]] = {}
        for turn in turns:
            by_speaker.setdefault(turn.speaker, []).append(turn)
        if len(by_speaker) <= 1:
            return events
        primary = candidate_speaker or max(
            by_speaker,
            key=lambda speaker: sum(
                item.end_seconds - item.start_seconds
                for item in by_speaker[speaker]
            ),
        )
        for speaker, speaker_turns in by_speaker.items():
            if speaker == primary:
                continue
            events.extend(
                DetectedVoiceEvent(
                    MonitoringEventKind.ADDITIONAL_SPEAKER, interval
                )
                for interval in merge_intervals(
                    [self._interval(turn) for turn in speaker_turns]
                )
            )
        return events

    def _load_models(self) -> None:
        if self._pipeline is not None:
            return
        try:
            pyannote_audio = importlib.import_module("pyannote.audio")
            speechbrain = importlib.import_module("speechbrain.inference.speaker")
            self._torch = importlib.import_module("torch")
            self._torchaudio = importlib.import_module("torchaudio")
        except ImportError as error:
            raise RuntimeError(
                "speaker analysis packages are not installed; install the proctoring extra"
            ) from error
        self._pipeline = pyannote_audio.Pipeline.from_pretrained(
            self._diarization_model, token=self._token
        )
        self._speaker_encoder = speechbrain.SpeakerRecognition.from_hparams(
            source=self._embedding_model,
            savedir=self._embedding_cache,
        )

    def _turns(self, path: Path) -> list[_SpeakerTurn]:
        self._load_models()
        if not path.is_file():
            raise FileNotFoundError(path)
        output = self._pipeline(str(path))
        annotation = getattr(output, "speaker_diarization", output)
        return [
            _SpeakerTurn(float(segment.start), float(segment.end), str(speaker))
            for segment, _, speaker in annotation.itertracks(yield_label=True)
            if segment.end > segment.start
        ]

    @staticmethod
    def _exclude(
        turns: list[_SpeakerTurn], intervals: tuple[TimeInterval, ...]
    ) -> list[_SpeakerTurn]:
        clean: list[_SpeakerTurn] = []
        for turn in turns:
            fragments = [(turn.start_seconds, turn.end_seconds)]
            for interval in intervals:
                excluded_start = interval.start_ms / 1000
                excluded_end = interval.end_ms / 1000
                next_fragments = []
                for start, end in fragments:
                    if excluded_end <= start or excluded_start >= end:
                        next_fragments.append((start, end))
                    else:
                        if start < excluded_start:
                            next_fragments.append((start, excluded_start))
                        if excluded_end < end:
                            next_fragments.append((excluded_end, end))
                fragments = next_fragments
            clean.extend(
                _SpeakerTurn(start, end, turn.speaker)
                for start, end in fragments
                if end - start >= 0.5
            )
        return clean

    @staticmethod
    def _overlaps(turns: list[_SpeakerTurn]) -> tuple[TimeInterval, ...]:
        overlaps: list[TimeInterval] = []
        for index, first in enumerate(turns):
            for second in turns[index + 1 :]:
                if first.speaker == second.speaker:
                    continue
                start = max(first.start_seconds, second.start_seconds)
                end = min(first.end_seconds, second.end_seconds)
                if end > start:
                    start_ms = max(0, round(start * 1000))
                    overlaps.append(
                        TimeInterval(
                            start_ms,
                            max(start_ms + 1, round(end * 1000)),
                        )
                    )
        return merge_intervals(overlaps)

    def _embedding(
        self, path: Path, turns: Iterable[_SpeakerTurn]
    ) -> Any | None:
        self._load_models()
        waveform, sample_rate = self._torchaudio.load(str(path))
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        if sample_rate != 16000:
            waveform = self._torchaudio.functional.resample(
                waveform, sample_rate, 16000
            )
            sample_rate = 16000
        chunks = []
        for turn in turns:
            start = max(0, round(turn.start_seconds * sample_rate))
            end = min(waveform.shape[1], round(turn.end_seconds * sample_rate))
            if end > start:
                chunks.append(waveform[:, start:end])
        if not chunks:
            return None
        speech = self._torch.cat(chunks, dim=1)
        if speech.shape[1] < sample_rate:
            return None
        return self._speaker_encoder.encode_batch(speech).squeeze().detach().cpu()

    def _cosine(self, first: Any, second: Any) -> float:
        return float(
            self._torch.nn.functional.cosine_similarity(
                first.flatten(), second.flatten(), dim=0
            ).item()
        )

    def _mean(self, embeddings: list[Any]) -> Any:
        return self._torch.stack(embeddings).mean(dim=0)

    @staticmethod
    def _interval(turn: _SpeakerTurn) -> TimeInterval:
        start_ms = max(0, round(turn.start_seconds * 1000))
        return TimeInterval(
            start_ms,
            max(start_ms + 1, round(turn.end_seconds * 1000)),
        )
