import unittest

from app.adapters.pyannote_voice import PyannoteVoiceAnalyzer, _SpeakerTurn
from app.domain.proctoring import MonitoringEventKind, TimeInterval


class PyannoteVoiceAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = PyannoteVoiceAnalyzer(huggingface_token=None)

    def test_overlapping_and_additional_speaker_intervals_are_separate(self) -> None:
        events = self.analyzer._speaker_structure_events(
            [
                _SpeakerTurn(0.0, 4.0, "speaker-0"),
                _SpeakerTurn(2.0, 3.0, "speaker-1"),
            ]
        )

        self.assertEqual(
            [event.kind for event in events],
            [
                MonitoringEventKind.OVERLAPPING_SPEECH,
                MonitoringEventKind.ADDITIONAL_SPEAKER,
            ],
        )
        self.assertEqual(events[0].interval, TimeInterval(2_000, 3_000))
        self.assertEqual(events[1].interval, TimeInterval(2_000, 3_000))

    def test_camera_flagged_ranges_are_removed_from_reference_speech(self) -> None:
        clean = self.analyzer._exclude(
            [_SpeakerTurn(0.0, 10.0, "speaker-0")],
            (TimeInterval(2_000, 7_000),),
        )

        self.assertEqual(
            clean,
            [
                _SpeakerTurn(0.0, 2.0, "speaker-0"),
                _SpeakerTurn(7.0, 10.0, "speaker-0"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
