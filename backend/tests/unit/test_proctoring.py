import unittest

from app.domain.proctoring import TimeInterval, merge_intervals


class ProctoringDomainTests(unittest.TestCase):
    def test_adjacent_model_fragments_are_merged(self) -> None:
        merged = merge_intervals(
            [TimeInterval(2_000, 3_000), TimeInterval(1_000, 1_900)],
            maximum_gap_ms=100,
        )

        self.assertEqual(merged, (TimeInterval(1_000, 3_000),))

    def test_invalid_interval_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TimeInterval(5_000, 5_000)


if __name__ == "__main__":
    unittest.main()
