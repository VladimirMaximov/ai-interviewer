from __future__ import annotations

import unittest
from pathlib import Path

from interview_platform.domain.competencies import load_framework
from interview_platform.domain.errors import ValidationError


FRAMEWORK_PATH = (
    Path(__file__).resolve().parents[1]
    / "interview_platform"
    / "data"
    / "competency_framework.v1.json"
)


class CompetencyFrameworkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.framework = load_framework(FRAMEWORK_PATH)

    def test_loads_complete_versioned_source_framework(self) -> None:
        self.assertEqual(1, self.framework.version)
        self.assertEqual(4, len(self.framework.common_competencies))
        self.assertEqual(13, len(self.framework.role_profiles))
        self.assertEqual(64, len(self.framework.content_hash))

    def test_role_level_projection_keeps_specific_anchor(self) -> None:
        projection = self.framework.projection("software_engineer", "middle")
        role = projection["role_profiles"][0]

        self.assertEqual("Software Engineer", role["display_name"])
        self.assertEqual(6, len(role["competencies"]))
        self.assertEqual("middle", role["competencies"][0]["anchors"][0]["level_key"])

    def test_leadership_profile_has_its_own_level_vocabulary(self) -> None:
        tech_lead = self.framework.role("tech_lead")
        self.assertEqual(("lead",), tech_lead.level_keys)
        self.assertEqual("technical_leadership", tech_lead.profile_kind)

        with self.assertRaises(ValidationError):
            self.framework.projection("tech_lead", "senior")


if __name__ == "__main__":
    unittest.main()
