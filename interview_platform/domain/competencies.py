"""Versioned Napoleon IT competency framework reference model."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .hiring import canonical_hash, required_text, to_primitive


@dataclass(frozen=True, slots=True)
class LevelAnchor:
    level_key: str
    behavior_text: str
    decision_scope: str | None = None
    impact_scope: str | None = None


@dataclass(frozen=True, slots=True)
class Competency:
    id: str
    code: str
    display_name: str
    dimension: str
    source_page: int
    anchors: tuple[LevelAnchor, ...]

    def anchor(self, level_key: str) -> LevelAnchor:
        for anchor in self.anchors:
            if anchor.level_key == level_key:
                return anchor
        raise ValidationError(
            "competency does not define the requested level",
            details={"competency_id": self.id, "level_key": level_key},
        )


@dataclass(frozen=True, slots=True)
class RoleProfile:
    role_key: str
    display_name: str
    profile_kind: str
    description: str
    level_keys: tuple[str, ...]
    source_page: int
    competencies: tuple[Competency, ...]


@dataclass(frozen=True, slots=True)
class CompetencyFramework:
    id: str
    version: int
    name: str
    status: str
    source_reference: str
    common_competencies: tuple[Competency, ...]
    role_profiles: tuple[RoleProfile, ...]
    content_hash: str

    def role(self, role_key: str) -> RoleProfile:
        for role in self.role_profiles:
            if role.role_key == role_key:
                return role
        raise ValidationError("role_key is invalid", details={"field": "role_key"})

    def projection(self, role_key: str | None = None, level_key: str | None = None) -> dict:
        roles = self.role_profiles if role_key is None else (self.role(role_key),)
        if level_key is not None:
            for role in roles:
                if level_key not in role.level_keys:
                    raise ValidationError(
                        "level_key is invalid for role",
                        details={"role_key": role.role_key, "level_key": level_key},
                    )
        payload = self.to_dict()
        payload["role_profiles"] = [
            _role_to_dict(role, level_key=level_key) for role in roles
        ]
        if level_key is not None:
            payload["common_competencies"] = [
                _competency_to_dict(item, level_key=_common_level(level_key))
                for item in self.common_competencies
            ]
        return payload

    def assessment_criteria(self, role_key: str, level_key: str) -> list[dict]:
        role = self.role(role_key)
        if level_key not in role.level_keys:
            raise ValidationError(
                "level_key is invalid for role",
                details={"role_key": role_key, "level_key": level_key},
            )
        common_level = _common_level(level_key)
        criteria = []
        for item in self.common_competencies:
            anchor = item.anchor(common_level)
            criteria.append(_criterion(item, anchor, level_key=common_level))
        for item in role.competencies:
            anchor = item.anchor(level_key)
            criteria.append(_criterion(item, anchor, level_key=level_key))
        return criteria

    def to_dict(self) -> dict[str, Any]:
        result = to_primitive(self)
        return result


def _criterion(item: Competency, anchor: LevelAnchor, *, level_key: str) -> dict:
    return {
        "id": item.id,
        "code": item.code,
        "display_name": item.display_name,
        "description": anchor.behavior_text,
        "dimension": "corporate_competency",
        "target_level_key": level_key,
        "weight": 1,
        "positive_anchors": [anchor.behavior_text],
        "negative_anchors": ["Ответ не показывает ожидаемое рабочее поведение."],
        "insufficient_information_rule": "Нет конкретного примера или личного вклада.",
    }


def _common_level(level_key: str) -> str:
    if level_key in {"lead", "lead_manager", "principal_architect"}:
        return "lead_manager"
    if level_key == "senior_architect":
        return "senior"
    if level_key == "architect":
        return "middle"
    return level_key


def _competency_to_dict(item: Competency, *, level_key: str | None = None) -> dict:
    result = {
        "id": item.id,
        "code": item.code,
        "display_name": item.display_name,
        "dimension": item.dimension,
        "source_page": item.source_page,
        "anchors": [],
    }
    anchors = item.anchors if level_key is None else (item.anchor(level_key),)
    result["anchors"] = [to_primitive(anchor) for anchor in anchors]
    return result


def _role_to_dict(role: RoleProfile, *, level_key: str | None = None) -> dict:
    return {
        "role_key": role.role_key,
        "display_name": role.display_name,
        "profile_kind": role.profile_kind,
        "description": role.description,
        "level_keys": list(role.level_keys),
        "source_page": role.source_page,
        "competencies": [
            _competency_to_dict(item, level_key=level_key) for item in role.competencies
        ],
    }


def _parse_competency(raw: dict, *, dimension: str, source_page: int) -> Competency:
    anchors = []
    for level_key, value in raw.get("anchors", {}).items():
        if isinstance(value, str):
            anchors.append(LevelAnchor(level_key, required_text(value, "behavior_text")))
        elif isinstance(value, dict):
            anchors.append(
                LevelAnchor(
                    level_key,
                    required_text(value.get("behavior_text", ""), "behavior_text"),
                    value.get("decision_scope"),
                    value.get("impact_scope"),
                )
            )
        else:
            raise ValidationError("competency anchor must be text or object")
    if not anchors:
        raise ValidationError("competency requires anchors")
    return Competency(
        id=required_text(raw.get("id", ""), "competency.id", 160),
        code=required_text(raw.get("code", ""), "competency.code", 120),
        display_name=required_text(raw.get("display_name", ""), "display_name", 200),
        dimension=dimension,
        source_page=source_page,
        anchors=tuple(anchors),
    )


def load_framework(path: str | Path) -> CompetencyFramework:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    common = tuple(
        _parse_competency(
            item,
            dimension=item.get("dimension", "soft_skill"),
            source_page=int(item.get("source_page", 0)),
        )
        for item in raw.get("common_competencies", [])
    )
    roles = []
    for item in raw.get("role_profiles", []):
        level_keys = tuple(item.get("level_keys", []))
        competencies = tuple(
            _parse_competency(
                competency,
                dimension="leadership"
                if item.get("profile_kind", "") in {"technical_leadership", "people_leadership"}
                else "hard_skill",
                source_page=int(item.get("source_page", 0)),
            )
            for competency in item.get("competencies", [])
        )
        role = RoleProfile(
            role_key=required_text(item.get("role_key", ""), "role_key", 120),
            display_name=required_text(item.get("display_name", ""), "display_name", 200),
            profile_kind=required_text(item.get("profile_kind", ""), "profile_kind", 80),
            description=required_text(item.get("description", ""), "description", 2_000),
            level_keys=level_keys,
            source_page=int(item.get("source_page", 0)),
            competencies=competencies,
        )
        if not level_keys or not competencies:
            raise ValidationError("role profile requires levels and competencies")
        for competency in competencies:
            if {anchor.level_key for anchor in competency.anchors} != set(level_keys):
                raise ValidationError(
                    "role competency must define every role level",
                    details={"role_key": role.role_key, "competency_id": competency.id},
                )
        roles.append(role)
    if len(common) != 4 or len(roles) != 13:
        raise ValidationError(
            "framework must contain 4 common competencies and 13 role profiles"
        )
    identifiers = [item.id for item in common]
    identifiers.extend(item.id for role in roles for item in role.competencies)
    if len(identifiers) != len(set(identifiers)):
        raise ValidationError("competency IDs must be unique")
    stable = {
        key: value
        for key, value in raw.items()
        if key not in {"content_hash"}
    }
    return CompetencyFramework(
        id=required_text(raw.get("id", ""), "framework.id", 160),
        version=int(raw.get("version", 0)),
        name=required_text(raw.get("name", ""), "framework.name", 200),
        status=required_text(raw.get("status", ""), "framework.status", 40),
        source_reference=required_text(raw.get("source_reference", ""), "source_reference", 500),
        common_competencies=common,
        role_profiles=tuple(roles),
        content_hash=canonical_hash(stable),
    )
