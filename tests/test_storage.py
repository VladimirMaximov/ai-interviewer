import tempfile
import unittest
from pathlib import Path

from product_engineering.storage import StageStore, slugify


class StorageTests(unittest.TestCase):
    def test_cached_stage_runs_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = StageStore(Path(temporary))
            calls = []

            def producer():
                calls.append(True)
                return {"value": 1}

            self.assertEqual(store.cached("stage.json", producer), {"value": 1})
            self.assertEqual(store.cached("stage.json", producer), {"value": 1})
            self.assertEqual(len(calls), 1)

    def test_slugify(self) -> None:
        self.assertEqual(slugify("Hello, World!"), "hello-world")


if __name__ == "__main__":
    unittest.main()
