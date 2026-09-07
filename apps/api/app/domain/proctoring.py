"""Evidence-first interview monitoring contracts and deterministic interval rules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class MonitoringEventKind(StrEnum):
    """Observable conditions that require human review, never automatic rejection."""

    FACE_MISSING = "face_missing"
    MULTIPLE_FACES = "multiple_faces"
    FACE_DETECTION_UNAVAILABLE = "face_detection_unavailable"
    OVERLAPPING_SPEECH = "overlapping_speech"
    ADDITIONAL_SPEAKER = "additional_speaker"
    SPEAKER_MISMATCH = "speaker_mismatch"


class MonitoringReviewStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"


class VoiceProfileStatus(StrEnum):
    COLLECTING = "collecting"
    READY = "ready"
    NOT_READY = "not_ready"


@dataclass(frozen=True)
class TimeInterval:
    start_ms: int
    end_ms: int

    def __post_init__(self) -> None:
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise ValueError("monitoring interval must be positive and ordered")


@dataclass(frozen=True)
class ReferenceAudio:
    path: Path
    excluded_intervals: tuple[TimeInterval, ...] = ()


@dataclass(frozen=True)
class VoiceProfileValidation:
    status: VoiceProfileStatus
    reason_code: str | None = None


@dataclass(frozen=True)
class DetectedVoiceEvent:
    kind: MonitoringEventKind
    interval: TimeInterval
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.kind not in {
            MonitoringEventKind.OVERLAPPING_SPEECH,
            MonitoringEventKind.ADDITIONAL_SPEAKER,
            MonitoringEventKind.SPEAKER_MISMATCH,
        }:
            raise ValueError("voice analysis returned a non-voice event")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("event confidence must be between zero and one")


@dataclass(frozen=True)
class VoiceAnalysisResult:
    profile: VoiceProfileValidation
    events: tuple[DetectedVoiceEvent, ...]
    detector_name: str
    detector_version: str


def merge_intervals(
    intervals: list[TimeInterval], *, maximum_gap_ms: int = 250
) -> tuple[TimeInterval, ...]:
    """Merge adjacent model fragments into stable reviewer-facing intervals."""

    if maximum_gap_ms < 0:
        raise ValueError("maximum gap cannot be negative")
    ordered = sorted(intervals, key=lambda item: (item.start_ms, item.end_ms))
    if not ordered:
        return ()
    merged = [ordered[0]]
    for item in ordered[1:]:
        previous = merged[-1]
        if item.start_ms <= previous.end_ms + maximum_gap_ms:
            merged[-1] = TimeInterval(
                previous.start_ms, max(previous.end_ms, item.end_ms)
            )
        else:
            merged.append(item)
    return tuple(merged)
