"""Use cases for vacancy context authoring, approval, and snapshots."""

from __future__ import annotations

from typing import Any

from interview_platform.domain.competencies import CompetencyFramework
from interview_platform.domain.errors import ConflictError, NotFoundError, ValidationError
from interview_platform.domain.hiring import canonical_hash, new_id, normalized_code, utc_now
from interview_platform.domain.vacancies import (
    AssessmentContextSnapshot,
    ContextSource,
    CriterionCategory,
    ProfileStatus,
    SourceType,
    Vacancy,
    VacancyCriterion,
    VacancyProfileVersion,
    VacancyStatus,
)

from .source_processing import extract_text_source


class VacancyService:
    def __init__(
        self,
        repository,
        framework: CompetencyFramework,
        *,
        max_context_bytes: int = 1_000_000,
        max_context_chars: int = 50_000,
        minimum_evidence_coverage: float = 0.5,
        interview_service=None,
    ) -> None:
        self.repository = repository
        self.framework = framework
        self.max_context_bytes = max_context_bytes
        self.max_context_chars = max_context_chars
        self.minimum_evidence_coverage = minimum_evidence_coverage
        self.interview_service = interview_service
        self.repository.save_framework(framework.to_dict())

    def get_framework(self, role_key: str | None = None, level_key: str | None = None) -> dict:
        return self.framework.projection(role_key, level_key)

    def create_vacancy(
        self,
        *,
        title: str,
        role_key: str,
        target_level_key: str,
        owner_actor_id: str,
    ) -> dict:
        role = self.framework.role(role_key)
        if target_level_key not in role.level_keys:
            raise ValidationError(
                "target_level_key is invalid for role",
                details={"role_key": role_key, "target_level_key": target_level_key},
            )
        now = utc_now()
        vacancy = Vacancy(
            id=new_id(),
            title=title,
            role_key=role_key,
            target_level_key=target_level_key,
            owner_actor_id=owner_actor_id,
            status=VacancyStatus.DRAFT,
            framework_id=self.framework.id,
            active_profile_version_id=None,
            created_at=now,
            updated_at=now,
        )
        self.repository.save_vacancy(vacancy.to_dict())
        return vacancy.to_dict()

    def list_vacancies(self) -> list[dict]:
        return self.repository.list_vacancies()

    def get_vacancy(self, vacancy_id: str) -> dict:
        value = self.repository.get_vacancy(vacancy_id)
        if value is None:
            raise NotFoundError("vacancy not found")
        return value

    def add_context_source(
        self,
        vacancy_id: str,
        *,
        source_type: str,
        display_name: str,
        text: str | bytes,
        actor_id: str,
        media_type: str | None = None,
    ) -> dict:
        self.get_vacancy(vacancy_id)
        try:
            kind = SourceType(source_type)
        except ValueError as exc:
            raise ValidationError("source_type is invalid", details={"field": "source_type"}) from exc
        normalized, content_hash, fragments = extract_text_source(
            text=text,
            display_name=display_name,
            source_type=kind.value,
            max_bytes=self.max_context_bytes,
            max_chars=self.max_context_chars,
        )
        source_id = new_id()
        owned_fragments = tuple(
            {**fragment, "context_source_id": source_id} for fragment in fragments
        )
        source = ContextSource(
            id=source_id,
            vacancy_id=vacancy_id,
            source_type=kind,
            display_name=display_name.strip() or kind.value,
            media_type=media_type,
            extracted_text=normalized,
            content_hash=content_hash,
            status="ready",
            fragments=owned_fragments,
            created_by=actor_id,
            created_at=utc_now(),
        )
        self.repository.save_context_source(source.to_dict())
        return source.to_dict()

    def list_context_sources(self, vacancy_id: str) -> list[dict]:
        self.get_vacancy(vacancy_id)
        return self.repository.list_context_sources(vacancy_id)

    def draft_profile(
        self,
        vacancy_id: str,
        *,
        source_ids: list[str],
        actor_id: str,
        idempotency_key: str | None = None,
    ) -> dict:
        scope = f"draft_profile:{vacancy_id}"
        existing = self._idempotent_result(idempotency_key, scope)
        if existing is not None:
            return existing
        vacancy = Vacancy.from_dict(self.get_vacancy(vacancy_id))
        if vacancy.status is VacancyStatus.CLOSED:
            raise ConflictError("closed vacancy cannot create a profile")
        sources = []
        for source_id in source_ids:
            source_data = self.repository.get_context_source(source_id)
            if source_data is None or source_data["vacancy_id"] != vacancy_id:
                raise ValidationError(
                    "context source does not belong to vacancy",
                    details={"source_id": source_id},
                )
            source = ContextSource.from_dict(source_data)
            if source.status != "ready":
                raise ConflictError("context source is not ready")
            sources.append(source)
        if not sources:
            raise ValidationError("at least one context source is required")

        fragments = [fragment for source in sources for fragment in source.fragments]
        criteria = tuple(
            self._criterion_from_fragment(fragment, position=index)
            for index, fragment in enumerate(fragments[:10], start=1)
        )
        versions = self.repository.list_profiles(vacancy_id)
        version = max((item["version"] for item in versions), default=0) + 1
        summary = " ".join(source.extracted_text for source in sources)[:4_000]
        payload_for_hash = {
            "vacancy_id": vacancy_id,
            "framework_id": self.framework.id,
            "version": version,
            "summary": summary,
            "criteria": [item.to_dict() for item in criteria],
        }
        profile = VacancyProfileVersion(
            id=new_id(),
            vacancy_id=vacancy_id,
            framework_id=self.framework.id,
            version=version,
            status=ProfileStatus.DRAFT,
            summary=summary,
            criteria=criteria,
            validation_issues=(),
            source_ids=tuple(source_ids),
            content_hash=canonical_hash(payload_for_hash),
            created_by=actor_id,
            created_at=utc_now(),
        )
        self.repository.save_profile(profile.to_dict())
        result = profile.to_dict()
        self._save_idempotent_result(idempotency_key, scope, result)
        return result

    def _criterion_from_fragment(self, fragment: dict, *, position: int) -> VacancyCriterion:
        text = fragment["text"].strip()
        is_must = any(word in text.casefold() for word in ("обяз", "must", "критич"))
        short = text if len(text) <= 80 else text[:77].rstrip() + "..."
        code = normalized_code(short)
        return VacancyCriterion(
            id=new_id(),
            code=f"{code}_{position}",
            display_name=short,
            description=text,
            category=CriterionCategory.MUST_HAVE if is_must else CriterionCategory.PRIORITY,
            weight=5 if is_must else 3,
            target_depth="Кандидат приводит конкретный рабочий пример, личный вклад и результат.",
            positive_anchors=(
                "Есть конкретная ситуация, действие кандидата, компромисс и проверяемый результат.",
            ),
            negative_anchors=(
                "Ответ ограничивается названием технологии или общими словами без личного вклада.",
            ),
            accepted_alternatives=(
                "Эквивалентный подход допустим, если кандидат объясняет переносимые принципы.",
            ),
            insufficient_information_rule="Нет конкретного примера, роли кандидата или результата.",
            linked_competency_ids=(),
            source_fragment_ids=(fragment["id"],),
            suggestion_confirmed=False,
            question_prompt=f"Приведите конкретный рабочий пример по ожиданию: {text}",
        )

    def get_profile(self, profile_id: str) -> dict:
        value = self.repository.get_profile(profile_id)
        if value is None:
            raise NotFoundError("vacancy profile not found")
        return value

    def update_profile(
        self,
        profile_id: str,
        *,
        summary: str,
        criteria: list[dict[str, Any]],
        actor_id: str,
    ) -> dict:
        del actor_id  # Current POC stores the original author and audit is added at publication.
        profile = VacancyProfileVersion.from_dict(self.get_profile(profile_id))
        if profile.status not in {ProfileStatus.DRAFT, ProfileStatus.VALIDATION_FAILED}:
            raise ConflictError("approved profile is immutable; create a new draft")
        profile.summary = summary
        profile.criteria = tuple(VacancyCriterion.from_dict(item) for item in criteria)
        profile.status = ProfileStatus.DRAFT
        profile.validation_issues = ()
        profile.content_hash = canonical_hash(
            {"summary": profile.summary, "criteria": [item.to_dict() for item in profile.criteria]}
        )
        self.repository.save_profile(profile.to_dict())
        return profile.to_dict()

    def approve_profile(
        self,
        vacancy_id: str,
        profile_id: str,
        *,
        actor_id: str,
        idempotency_key: str | None = None,
    ) -> dict:
        scope = f"approve_profile:{profile_id}"
        existing = self._idempotent_result(idempotency_key, scope)
        if existing is not None:
            return existing
        vacancy = Vacancy.from_dict(self.get_vacancy(vacancy_id))
        profile = VacancyProfileVersion.from_dict(self.get_profile(profile_id))
        if profile.vacancy_id != vacancy_id:
            raise ValidationError("profile does not belong to vacancy")
        now = utc_now()
        try:
            profile.approve(actor_id=actor_id, approved_at=now)
        except ValidationError:
            self.repository.save_profile(profile.to_dict())
            raise
        previous_id = vacancy.active_profile_version_id
        if previous_id and previous_id != profile.id:
            previous = VacancyProfileVersion.from_dict(self.get_profile(previous_id))
            previous.status = ProfileStatus.SUPERSEDED
            self.repository.save_profile(previous.to_dict())
        self.repository.save_profile(profile.to_dict())
        vacancy.active_profile_version_id = profile.id
        vacancy.status = VacancyStatus.ACTIVE
        vacancy.updated_at = now
        self.repository.save_vacancy(vacancy.to_dict())
        result = profile.to_dict()
        self._save_idempotent_result(idempotency_key, scope, result)
        return result

    def create_snapshot(
        self,
        vacancy_id: str,
        *,
        profile_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        scope = f"create_snapshot:{vacancy_id}"
        existing = self._idempotent_result(idempotency_key, scope)
        if existing is not None:
            return existing
        vacancy = Vacancy.from_dict(self.get_vacancy(vacancy_id))
        selected_profile_id = profile_id or vacancy.active_profile_version_id
        if selected_profile_id is None:
            raise ConflictError("vacancy has no approved profile")
        profile = VacancyProfileVersion.from_dict(self.get_profile(selected_profile_id))
        if profile.vacancy_id != vacancy_id or profile.status is not ProfileStatus.APPROVED:
            raise ConflictError("assessment snapshot requires the active approved profile")

        corporate = self.framework.assessment_criteria(
            vacancy.role_key,
            vacancy.target_level_key,
        )
        vacancy_criteria = [
            {
                **criterion.to_dict(),
                "dimension": "vacancy_fit",
                "target_level_key": vacancy.target_level_key,
            }
            for criterion in profile.criteria
        ]
        criteria = corporate + vacancy_criteria
        questions = []
        enriched = []
        for position, criterion in enumerate(criteria, start=1):
            prompt = criterion.get("question_prompt") or (
                f"Приведите конкретный пример, который показывает: {criterion['description']}"
            )
            questions.append({"position": position, "prompt": prompt, "required": True})
            enriched.append({**criterion, "question_position": position})
        ranking_policy = {
            "version": 1,
            "primary_dimension": "vacancy_fit",
            "secondary_dimension": "corporate_competency",
            "minimum_evidence_coverage": self.minimum_evidence_coverage,
            "display_precision": 2,
        }
        feedback_policy = {
            "version": 1,
            "require_human_publication": True,
            "candidate_visible_sections": [
                "assessment_scope",
                "strengths",
                "growth_areas",
                "evidence_gaps",
                "limitations",
                "next_steps",
            ],
        }
        stable = {
            "vacancy_id": vacancy.id,
            "framework_id": self.framework.id,
            "framework_version": self.framework.version,
            "role_key": vacancy.role_key,
            "target_level_key": vacancy.target_level_key,
            "profile_version_id": profile.id,
            "profile_version": profile.version,
            "ranking_policy": ranking_policy,
            "feedback_policy": feedback_policy,
            "criteria": enriched,
            "questions": questions,
        }
        snapshot = AssessmentContextSnapshot(
            id=new_id(),
            **stable,
            context_hash=canonical_hash(stable),
            created_at=utc_now(),
        )
        self.repository.save_snapshot(snapshot.to_dict())
        result = snapshot.to_dict()
        self._save_idempotent_result(idempotency_key, scope, result)
        return result

    def get_snapshot(self, snapshot_id: str) -> dict:
        value = self.repository.get_snapshot(snapshot_id)
        if value is None:
            raise NotFoundError("assessment context snapshot not found")
        return value

    def list_snapshots(self, vacancy_id: str) -> list[dict]:
        self.get_vacancy(vacancy_id)
        return self.repository.list_snapshots(vacancy_id)

    def create_interview(
        self,
        vacancy_id: str,
        *,
        snapshot_id: str,
        candidate_alias: str,
        invitation_token: str | None = None,
    ) -> dict:
        if self.interview_service is None:
            raise ConflictError("interview service is not configured")
        vacancy = Vacancy.from_dict(self.get_vacancy(vacancy_id))
        snapshot = AssessmentContextSnapshot.from_dict(self.get_snapshot(snapshot_id))
        if snapshot.vacancy_id != vacancy_id:
            raise ValidationError("assessment snapshot does not belong to vacancy")
        created = self.interview_service.create_interview(
            candidate_alias=candidate_alias,
            position_title=vacancy.title,
            questions=list(snapshot.questions),
            invitation_token=invitation_token,
        )
        self.repository.assign_interview(
            created.interview.id,
            vacancy_id,
            snapshot_id,
            utc_now(),
        )
        return {
            "interview": created.interview,
            "invitation_token": created.invitation_token,
            "vacancy_id": vacancy_id,
            "assessment_context_snapshot_id": snapshot_id,
        }

    def _idempotent_result(self, key: str | None, scope: str) -> dict | None:
        if key is None:
            return None
        if len(key.strip()) < 8 or len(key) > 128:
            raise ValidationError("idempotency key must contain 8 to 128 characters")
        return self.repository.get_idempotent_result(key, scope)

    def _save_idempotent_result(
        self, key: str | None, scope: str, payload: dict
    ) -> None:
        if key is not None:
            self.repository.save_idempotent_result(key, scope, payload)
