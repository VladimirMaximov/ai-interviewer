from __future__ import annotations

import ast
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ROOT = REPOSITORY_ROOT / "prototypes" / "interview-platform" / "interview_platform"
BACKEND_ROOT = REPOSITORY_ROOT / "apps" / "api" / "app"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_domain_does_not_depend_on_outer_layers(self) -> None:
        imports = set().union(*(imported_modules(path) for path in (ROOT / "domain").glob("*.py")))
        self.assertFalse(
            {name for name in imports if name.startswith("interview_platform.application")},
            imports,
        )
        self.assertFalse(
            {name for name in imports if name.startswith("interview_platform.infrastructure")},
            imports,
        )
        self.assertFalse(
            {name for name in imports if name.startswith("interview_platform.web")},
            imports,
        )

    def test_backend_multi_agent_domain_has_no_outer_layer_dependency(self) -> None:
        imports = imported_modules(BACKEND_ROOT / "domain" / "multi_agent.py")
        forbidden = {
            name
            for name in imports
            if name.startswith(
                ("app.api", "app.adapters", "app.database", "app.models", "app.services")
            )
        }
        self.assertFalse(forbidden, imports)

    def test_backend_multi_agent_adapter_and_models_do_not_depend_on_delivery(self) -> None:
        paths = [
            BACKEND_ROOT / "adapters" / "openai_interview_agents.py",
            BACKEND_ROOT / "models" / "multi_agent.py",
        ]
        imports = set().union(*(imported_modules(path) for path in paths))
        forbidden = {
            name
            for name in imports
            if name.startswith(("app.api", "app.database", "app.services"))
        }
        self.assertFalse(forbidden, imports)

    def test_application_does_not_depend_on_delivery_or_infrastructure(self) -> None:
        imports = set().union(
            *(imported_modules(path) for path in (ROOT / "application").glob("*.py"))
        )
        forbidden = {
            name
            for name in imports
            if name.startswith(("interview_platform.infrastructure", "interview_platform.web"))
        }
        self.assertFalse(forbidden, imports)

    def test_infrastructure_does_not_depend_on_web(self) -> None:
        imports = set().union(
            *(imported_modules(path) for path in (ROOT / "infrastructure").glob("*.py"))
        )
        self.assertFalse(
            {name for name in imports if name.startswith("interview_platform.web")},
            imports,
        )


if __name__ == "__main__":
    unittest.main()
