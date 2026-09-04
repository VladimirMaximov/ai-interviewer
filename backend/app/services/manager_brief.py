"""Manager-brief orchestration, form editing, approval, and safe projection."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.manager_brief import (
    FIELD_LABELS,
    SINGLE_VALUE_FIELDS,
    UNRESOLVED_QUESTIONS,
    AgentFieldProposal,
    AgentFieldOrigin,
    AgentOperationStatus,
    AgentOutputError,
    AgentProviderError,
    AgentRunStatus,
    ApprovedManagerBriefField,
    ApprovedManagerBriefContext,
    ConfirmationStatus,
    FieldKey,
    FieldOrigin,
    ManagerBriefAgentResult,
    ManagerBriefConflictError,
    ManagerBriefDraftView,
    ManagerBriefField,
    ManagerBriefFieldUpdate,
    ManagerBriefNotFoundError,
    ManagerBriefStatus,
    ManagerBriefValidationError,
    UnresolvedField,
)
from app.models.manager_brief import (
    ManagerBriefAgentRun,
    ManagerBriefDraft,
    ManagerBriefOperation,
)


MAX_SOURCE_CHARS = 50_000
MAX_FRAGMENT_CHARS = 4_000
MAX_LIST_ITEMS = 30
MAX_VALUE_CHARS = 2_000

PROHIBITED_TRAIT_PATTERNS = {
    "appearance": re.compile(r"\b(appearance|внешност\w*|привлекательн\w*)\b", re.I),
    "age": re.compile(r"\b(age|возраст\w*)\b", re.I),
    "sex_or_gender": re.compile(r"\b(gender|sex|пол|гендер\w*)\b", re.I),
    "nationality": re.compile(r"\b(nationality|национальност\w*)\b", re.I),
    "accent": re.compile(r"\b(accent|акцент\w*)\b", re.I),
    "emotion": re.compile(r"\b(emotion|эмоци\w*)\b", re.I),
    "voice_confidence": re.compile(
        r"(voice confidence|уверенн\w*\s+(?:в\s+)?голос\w*)", re.I
    ),
    "family_status": re.compile(
        r"\b(marital status|семейн\w+\s+положен\w*|детей|беременн\w*)\b", re.I
    ),
    "religion": re.compile(r"\b(religion|религи\w*|вероисповед\w*)\b", re.I),
    "disability": re.compile(r"\b(disability|инвалидност\w*)\b", re.I),
}


class ManagerBriefAgent(Protocol):
    model_id: str
    model_version: str
    prompt_id: str

    def draft(
        self, *, vacancy_id: str, fragments: list[dict]
    ) -> ManagerBriefAgentResult: ...


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ManagerBriefService:
    """Keep LLM suggestions editable and outside evaluation until approval."""

    def __init__(
        self,
        db: Session,
        agent: ManagerBriefAgent,
        *,
        max_attempts: int = 3,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.db = db
        self.agent = agent
        self.max_attempts = max_attempts

    @staticmethod
    def fragment_source(source_text: str) -> list[dict]:
        """Build deterministic bounded fragments for provenance validation."""
        normalized = source_text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            raise ManagerBriefValidationError("source_text must not be empty")
        if len(normalized) > MAX_SOURCE_CHARS:
            raise ManagerBriefValidationError(
                f"source_text must contain at most {MAX_SOURCE_CHARS} characters"
            )

        chunks: list[str] = []
        for paragraph in re.split(r"\n\s*\n", normalized):
            paragraph = paragraph.strip()
            while paragraph:
                chunks.append(paragraph[:MAX_FRAGMENT_CHARS])
                paragraph = paragraph[MAX_FRAGMENT_CHARS:].lstrip()
        source_hash = _canonical_hash(normalized)
        return [
            {
                "id": f"manager-source:{source_hash[:16]}:{index}",
                "text": text,
            }
            for index, text in enumerate(chunks, start=1)
        ]

    def create_draft(
        self,
        *,
        vacancy_id: UUID,
        source_text: str,
        actor_id: str,
        idempotency_key: str,
    ) -> ManagerBriefDraftView:
        actor = self._required_actor(actor_id)
        operation_key = self._required_idempotency_key(idempotency_key)
        fragments = self.fragment_source(source_text)
        normalized_source = "\n\n".join(fragment["text"] for fragment in fragments)
        input_hash = _canonical_hash(
            {
                "vacancy_id": str(vacancy_id),
                "actor_id": actor,
                "source_fragments": fragments,
                "prompt_id": self.agent.prompt_id,
            }
        )
        operation = self.db.scalar(
            select(ManagerBriefOperation).where(
                ManagerBriefOperation.vacancy_id == vacancy_id,
                ManagerBriefOperation.idempotency_key == operation_key,
            )
        )
        if operation is not None:
            if operation.input_hash != input_hash:
                raise ManagerBriefConflictError(
                    "idempotency key was already used for different input",
                    code="idempotency_conflict",
                )
            if (
                operation.status is AgentOperationStatus.SUCCEEDED
                and operation.output_draft_id is not None
            ):
                return self.get_draft(vacancy_id, operation.output_draft_id)
            if operation.status is AgentOperationStatus.RUNNING:
                raise ManagerBriefConflictError(
                    "manager brief generation is already running",
                    code="operation_in_progress",
                )
            operation.status = AgentOperationStatus.RUNNING
            operation.updated_at = _now()
        else:
            operation = ManagerBriefOperation(
                vacancy_id=vacancy_id,
                actor_id=actor,
                idempotency_key=operation_key,
                input_hash=input_hash,
                status=AgentOperationStatus.RUNNING,
                created_at=_now(),
                updated_at=_now(),
            )
            self.db.add(operation)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            operation = self.db.scalar(
                select(ManagerBriefOperation).where(
                    ManagerBriefOperation.vacancy_id == vacancy_id,
                    ManagerBriefOperation.idempotency_key == operation_key,
                )
            )
            if operation is None:
                raise
            if operation.input_hash != input_hash:
                raise ManagerBriefConflictError(
                    "idempotency key was already used for different input",
                    code="idempotency_conflict",
                )
            if (
                operation.status is AgentOperationStatus.SUCCEEDED
                and operation.output_draft_id is not None
            ):
                return self.get_draft(vacancy_id, operation.output_draft_id)
            raise ManagerBriefConflictError(
                "manager brief generation is already running",
                code="operation_in_progress",
            )
        self.db.refresh(operation)

        attempts = self.db.scalar(
            select(func.count(ManagerBriefAgentRun.id)).where(
                ManagerBriefAgentRun.operation_id == operation.id
            )
        )
        if int(attempts or 0) >= self.max_attempts:
            operation.status = AgentOperationStatus.FAILED
            operation.updated_at = _now()
            self.db.commit()
            raise ManagerBriefConflictError(
                "manager brief retry limit reached; use a new idempotency key",
                code="retry_limit_reached",
            )
        run = ManagerBriefAgentRun(
            operation_id=operation.id,
            attempt=int(attempts or 0) + 1,
            status=AgentRunStatus.RUNNING,
            model_id=self.agent.model_id,
            model_version=self.agent.model_version,
            prompt_id=self.agent.prompt_id,
            input_hash=input_hash,
            started_at=_now(),
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        try:
            raw_result = self.agent.draft(
                vacancy_id=str(vacancy_id),
                fragments=fragments,
            )
            result = ManagerBriefAgentResult.model_validate(raw_result)
            fields, unresolved = self._validate_agent_result(
                result,
                fragments,
                actor_id=actor,
            )
        except PydanticValidationError as error:
            invalid = AgentOutputError("manager brief output does not match schema")
            self._fail_attempt(
                operation,
                run,
                AgentRunStatus.INVALID_OUTPUT,
                invalid.code,
            )
            raise invalid from error
        except AgentOutputError as error:
            self._fail_attempt(
                operation, run, AgentRunStatus.INVALID_OUTPUT, error.code
            )
            raise
        except AgentProviderError as error:
            self._fail_attempt(
                operation, run, AgentRunStatus.PROVIDER_FAILED, error.code
            )
            raise
        except Exception as error:
            self._fail_attempt(
                operation,
                run,
                AgentRunStatus.PROVIDER_FAILED,
                "provider_error",
            )
            raise AgentProviderError("manager brief agent failed") from error

        version = (
            int(
                self.db.scalar(
                    select(func.max(ManagerBriefDraft.version)).where(
                        ManagerBriefDraft.vacancy_id == vacancy_id
                    )
                )
                or 0
            )
            + 1
        )
        issues = self._validation_issues(fields)
        stable_form = {
            "fields": [field.model_dump(mode="json") for field in fields],
            "unresolved_fields": [item.model_dump(mode="json") for item in unresolved],
        }
        draft = ManagerBriefDraft(
            vacancy_id=vacancy_id,
            version=version,
            revision=1,
            status=ManagerBriefStatus.DRAFT,
            source_text=normalized_source,
            source_fragments=fragments,
            fields_payload=stable_form["fields"],
            unresolved_fields=stable_form["unresolved_fields"],
            validation_issues=issues,
            content_hash=_canonical_hash(stable_form),
            agent_run_id=run.id,
            created_by=actor,
            created_at=_now(),
            updated_at=_now(),
        )
        self.db.add(draft)
        self.db.flush()
        run.status = AgentRunStatus.SUCCEEDED
        run.output_hash = _canonical_hash(result.model_dump(mode="json"))
        run.completed_at = _now()
        operation.status = AgentOperationStatus.SUCCEEDED
        operation.output_draft_id = draft.id
        operation.updated_at = _now()
        self.db.commit()
        self.db.refresh(draft)
        return self._view(draft)

    def list_drafts(self, vacancy_id: UUID) -> list[ManagerBriefDraftView]:
        drafts = self.db.scalars(
            select(ManagerBriefDraft)
            .where(ManagerBriefDraft.vacancy_id == vacancy_id)
            .order_by(ManagerBriefDraft.version)
        ).all()
        return [self._view(draft) for draft in drafts]

    def get_draft(self, vacancy_id: UUID, draft_id: UUID) -> ManagerBriefDraftView:
        draft = self.db.get(ManagerBriefDraft, draft_id)
        if draft is None or draft.vacancy_id != vacancy_id:
            raise ManagerBriefNotFoundError("manager brief draft not found")
        return self._view(draft)

    def update_draft(
        self,
        *,
        vacancy_id: UUID,
        draft_id: UUID,
        expected_revision: int,
        actor_id: str,
        updates: list[ManagerBriefFieldUpdate | dict],
    ) -> ManagerBriefDraftView:
        actor = self._required_actor(actor_id)
        draft = self._draft_model(vacancy_id, draft_id, lock=True)
        self._ensure_mutable(draft)
        if draft.revision != expected_revision:
            raise ManagerBriefConflictError(
                "draft was changed; reload it before saving",
                code="revision_conflict",
            )

        fields = {
            field.field_key: field
            for field in (
                ManagerBriefField.model_validate(item) for item in draft.fields_payload
            )
        }
        unresolved = {
            item.field_key: item
            for item in (
                UnresolvedField.model_validate(value)
                for value in draft.unresolved_fields
            )
        }
        seen_updates: set[FieldKey] = set()
        for raw_update in updates:
            update = ManagerBriefFieldUpdate.model_validate(raw_update)
            if update.field_key in seen_updates:
                raise ManagerBriefValidationError(
                    f"field {update.field_key.value} is updated more than once"
                )
            seen_updates.add(update.field_key)
            value = self._normalize_value(update.field_key, update.value)
            previous = fields.get(update.field_key)
            if previous is None or previous.value != value:
                changed = True
                origin = FieldOrigin.MANAGER_EDITED
            else:
                changed = False
                origin = previous.origin
            confirmed = update.confirmation_status is ConfirmationStatus.CONFIRMED
            fields[update.field_key] = ManagerBriefField(
                id=previous.id if previous is not None else uuid4(),
                field_key=update.field_key,
                label=FIELD_LABELS[update.field_key],
                value=value,
                origin=origin,
                source_fragment_ids=(
                    previous.source_fragment_ids
                    if previous is not None and not changed
                    else []
                ),
                source_quotes=(
                    previous.source_quotes
                    if previous is not None and not changed
                    else []
                ),
                confidence=(
                    previous.confidence
                    if previous is not None and not changed
                    else None
                ),
                confirmation_status=update.confirmation_status,
                confirmed_by=actor if confirmed else None,
                confirmed_at=_now() if confirmed else None,
            )
            unresolved.pop(update.field_key, None)

        ordered_fields = [fields[key] for key in FieldKey if key in fields]
        issues = self._validation_issues(ordered_fields)
        unresolved_values = [unresolved[key] for key in FieldKey if key in unresolved]
        stable_form = {
            "fields": [field.model_dump(mode="json") for field in ordered_fields],
            "unresolved_fields": [
                item.model_dump(mode="json") for item in unresolved_values
            ],
        }
        draft.fields_payload = stable_form["fields"]
        draft.unresolved_fields = stable_form["unresolved_fields"]
        draft.validation_issues = issues
        draft.content_hash = _canonical_hash(stable_form)
        draft.status = ManagerBriefStatus.DRAFT
        draft.revision += 1
        draft.updated_at = _now()
        self.db.commit()
        self.db.refresh(draft)
        return self._view(draft)

    def approve_draft(
        self,
        *,
        vacancy_id: UUID,
        draft_id: UUID,
        expected_revision: int,
        actor_id: str,
        confirm_no_automatic_rejection: bool,
    ) -> ManagerBriefDraftView:
        actor = self._required_actor(actor_id)
        draft = self._draft_model(vacancy_id, draft_id, lock=True)
        if draft.status is ManagerBriefStatus.APPROVED:
            if draft.revision != expected_revision:
                raise ManagerBriefConflictError(
                    "approved version does not match expected revision",
                    code="revision_conflict",
                )
            return self._view(draft)
        self._ensure_mutable(draft)
        if draft.revision != expected_revision:
            raise ManagerBriefConflictError(
                "draft was changed; reload it before approval",
                code="revision_conflict",
            )
        if not confirm_no_automatic_rejection:
            raise ManagerBriefValidationError(
                "confirm_no_automatic_rejection must be true"
            )

        fields = [
            ManagerBriefField.model_validate(item) for item in draft.fields_payload
        ]
        issues = self._validation_issues(fields)
        draft.validation_issues = issues
        if issues:
            draft.status = ManagerBriefStatus.VALIDATION_FAILED
            draft.updated_at = _now()
            self.db.commit()
            raise ManagerBriefValidationError(
                "manager brief has blocking validation issues",
                issues=issues,
            )

        previous = self.db.scalars(
            select(ManagerBriefDraft).where(
                ManagerBriefDraft.vacancy_id == vacancy_id,
                ManagerBriefDraft.status == ManagerBriefStatus.APPROVED,
                ManagerBriefDraft.id != draft.id,
            )
        ).all()
        for item in previous:
            item.status = ManagerBriefStatus.SUPERSEDED
            item.updated_at = _now()

        confirmed = [
            self._approved_field(field)
            for field in fields
            if field.confirmation_status is ConfirmationStatus.CONFIRMED
        ]
        draft.content_hash = _canonical_hash(
            {
                "vacancy_id": str(vacancy_id),
                "version": draft.version,
                "fields": [field.model_dump(mode="json") for field in confirmed],
            }
        )
        draft.status = ManagerBriefStatus.APPROVED
        draft.approved_by = actor
        draft.approved_at = _now()
        draft.updated_at = draft.approved_at
        self.db.commit()
        self.db.refresh(draft)
        return self._view(draft)

    def get_approved_context(self, vacancy_id: UUID) -> ApprovedManagerBriefContext:
        draft = self.db.scalar(
            select(ManagerBriefDraft)
            .where(
                ManagerBriefDraft.vacancy_id == vacancy_id,
                ManagerBriefDraft.status == ManagerBriefStatus.APPROVED,
            )
            .order_by(ManagerBriefDraft.version.desc())
        )
        if draft is None:
            raise ManagerBriefNotFoundError("approved manager brief not found")
        fields = []
        for item in draft.fields_payload:
            field = ManagerBriefField.model_validate(item)
            if field.confirmation_status is ConfirmationStatus.CONFIRMED:
                fields.append(self._approved_field(field))
        return ApprovedManagerBriefContext(
            profile_id=draft.id,
            vacancy_id=draft.vacancy_id,
            version=draft.version,
            content_hash=draft.content_hash,
            fields=fields,
        )

    def close(self) -> None:
        self.db.close()

    def _validate_agent_result(
        self,
        result: ManagerBriefAgentResult,
        fragments: list[dict],
        *,
        actor_id: str,
    ) -> tuple[list[ManagerBriefField], list[UnresolvedField]]:
        fragment_text = {item["id"]: item["text"] for item in fragments}
        fields: list[ManagerBriefField] = []
        seen: set[FieldKey] = set()
        for proposal in result.fields:
            if proposal.field_key in seen:
                raise AgentOutputError(
                    f"agent returned duplicate field {proposal.field_key.value}"
                )
            seen.add(proposal.field_key)
            self._validate_provenance(proposal, fragment_text)
            fields.append(
                ManagerBriefField(
                    id=uuid4(),
                    field_key=proposal.field_key,
                    label=FIELD_LABELS[proposal.field_key],
                    value=self._normalize_value(
                        proposal.field_key,
                        proposal.value,
                        agent_output=True,
                    ),
                    origin=FieldOrigin(proposal.origin.value),
                    source_fragment_ids=proposal.source_fragment_ids,
                    source_quotes=proposal.source_quotes,
                    confidence=proposal.confidence,
                    confirmation_status=(
                        ConfirmationStatus.CONFIRMED
                        if proposal.origin is AgentFieldOrigin.MANAGER_SOURCE
                        else ConfirmationStatus.PROPOSED
                    ),
                    confirmed_by=(
                        actor_id
                        if proposal.origin is AgentFieldOrigin.MANAGER_SOURCE
                        else None
                    ),
                    confirmed_at=(
                        _now()
                        if proposal.origin is AgentFieldOrigin.MANAGER_SOURCE
                        else None
                    ),
                )
            )

        unresolved_by_key: dict[FieldKey, UnresolvedField] = {}
        for item in result.unresolved_fields:
            if item.field_key in seen or item.field_key in unresolved_by_key:
                continue
            unresolved_by_key[item.field_key] = item
        for key in FieldKey:
            if key not in seen and key not in unresolved_by_key:
                unresolved_by_key[key] = UnresolvedField(
                    field_key=key,
                    question=UNRESOLVED_QUESTIONS[key],
                )
        unresolved = [
            unresolved_by_key[key] for key in FieldKey if key in unresolved_by_key
        ]
        return fields, unresolved

    @staticmethod
    def _validate_provenance(
        proposal: AgentFieldProposal,
        fragment_text: dict[str, str],
    ) -> None:
        if proposal.origin is AgentFieldOrigin.AGENT_SUGGESTION:
            if proposal.source_fragment_ids or proposal.source_quotes:
                raise AgentOutputError(
                    "agent suggestion cannot claim manager provenance"
                )
            return
        if not proposal.source_fragment_ids or not proposal.source_quotes:
            raise AgentOutputError("manager-derived field requires source provenance")
        try:
            referenced = [fragment_text[item] for item in proposal.source_fragment_ids]
        except KeyError as error:
            raise AgentOutputError(
                "agent referenced an unknown source fragment"
            ) from error
        referenced_folded = [value.casefold() for value in referenced]
        for quote in proposal.source_quotes:
            cleaned = quote.strip()
            if not cleaned or not any(
                cleaned.casefold() in source for source in referenced_folded
            ):
                raise AgentOutputError(
                    "agent source quote is not present in referenced input"
                )

    @staticmethod
    def _normalize_value(
        key: FieldKey,
        value: str | list[str],
        *,
        agent_output: bool = False,
    ) -> str | list[str]:
        error_type = AgentOutputError if agent_output else ManagerBriefValidationError
        if key in SINGLE_VALUE_FIELDS:
            if not isinstance(value, str):
                raise error_type(f"field {key.value} must be a string")
            normalized = value.strip()
            if not normalized or len(normalized) > MAX_VALUE_CHARS:
                raise error_type(
                    f"field {key.value} must contain 1 to {MAX_VALUE_CHARS} characters"
                )
            return normalized
        if not isinstance(value, list) or isinstance(value, str):
            raise error_type(f"field {key.value} must be a list of strings")
        if len(value) > MAX_LIST_ITEMS:
            raise error_type(f"field {key.value} has too many items")
        normalized_items: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise error_type(f"field {key.value} must contain only strings")
            cleaned = item.strip()
            if cleaned and cleaned not in normalized_items:
                if len(cleaned) > MAX_VALUE_CHARS:
                    raise error_type(f"field {key.value} item is too long")
                normalized_items.append(cleaned)
        return normalized_items

    @staticmethod
    def _validation_issues(fields: list[ManagerBriefField]) -> list[dict]:
        issues: list[dict] = []
        for field in fields:
            if field.confirmation_status is ConfirmationStatus.REJECTED:
                continue
            if field.confirmation_status is ConfirmationStatus.PROPOSED:
                issues.append(
                    {
                        "code": "unconfirmed_suggestion",
                        "severity": "blocking",
                        "field_key": field.field_key.value,
                        "message": "Подтвердите или отклоните предложение агента.",
                    }
                )
            text = (
                field.value if isinstance(field.value, str) else " ".join(field.value)
            )
            matches = [
                name
                for name, pattern in PROHIBITED_TRAIT_PATTERNS.items()
                if pattern.search(text)
            ]
            if matches:
                issues.append(
                    {
                        "code": "prohibited_trait",
                        "severity": "blocking",
                        "field_key": field.field_key.value,
                        "message": "Нельзя оценивать чувствительные или нерабочие признаки: "
                        + ", ".join(matches),
                    }
                )
        return issues

    def _draft_model(
        self,
        vacancy_id: UUID,
        draft_id: UUID,
        *,
        lock: bool = False,
    ) -> ManagerBriefDraft:
        statement = select(ManagerBriefDraft).where(
            ManagerBriefDraft.id == draft_id,
            ManagerBriefDraft.vacancy_id == vacancy_id,
        )
        if lock:
            statement = statement.with_for_update()
        draft = self.db.scalar(statement)
        if draft is None:
            raise ManagerBriefNotFoundError("manager brief draft not found")
        return draft

    @staticmethod
    def _ensure_mutable(draft: ManagerBriefDraft) -> None:
        if draft.status in {
            ManagerBriefStatus.APPROVED,
            ManagerBriefStatus.SUPERSEDED,
        }:
            raise ManagerBriefConflictError(
                "approved manager brief is immutable; create a new draft"
            )

    @staticmethod
    def _required_actor(actor_id: str) -> str:
        value = actor_id.strip()
        if not value or len(value) > 120:
            raise ManagerBriefValidationError("manager actor id is invalid")
        return value

    @staticmethod
    def _required_idempotency_key(idempotency_key: str) -> str:
        value = idempotency_key.strip()
        if not 8 <= len(value) <= 128:
            raise ManagerBriefValidationError(
                "idempotency key must contain 8 to 128 characters"
            )
        return value

    def _fail_attempt(
        self,
        operation: ManagerBriefOperation,
        run: ManagerBriefAgentRun,
        status: AgentRunStatus,
        failure_code: str,
    ) -> None:
        run.status = status
        run.failure_code = failure_code
        run.completed_at = _now()
        operation.status = AgentOperationStatus.FAILED
        operation.updated_at = _now()
        self.db.commit()

    @staticmethod
    def _approved_field(field: ManagerBriefField) -> ApprovedManagerBriefField:
        return ApprovedManagerBriefField(
            id=field.id,
            field_key=field.field_key,
            value=field.value,
            origin=field.origin,
            source_fragment_ids=field.source_fragment_ids,
        )

    @staticmethod
    def _view(draft: ManagerBriefDraft) -> ManagerBriefDraftView:
        return ManagerBriefDraftView(
            id=draft.id,
            vacancy_id=draft.vacancy_id,
            version=draft.version,
            revision=draft.revision,
            status=draft.status,
            source_text=draft.source_text,
            fields=[
                ManagerBriefField.model_validate(item) for item in draft.fields_payload
            ],
            unresolved_fields=[
                UnresolvedField.model_validate(item) for item in draft.unresolved_fields
            ],
            validation_issues=draft.validation_issues,
            content_hash=draft.content_hash,
            agent_run_id=draft.agent_run_id,
            created_by=draft.created_by,
            created_at=draft.created_at,
            updated_at=draft.updated_at,
            approved_by=draft.approved_by,
            approved_at=draft.approved_at,
        )
