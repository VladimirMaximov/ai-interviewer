"""Vacancy/resume matching and bounded context assembly."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any
from urllib.parse import quote
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.document_extraction import extract_document_text
from app.config import settings
from app.domain.hiring_context import (
    AgentAnswerContext,
    AgentDocumentContext,
    ApplicationView,
    ApprovedBriefContext,
    CandidateConsentRequiredError,
    HiringContextConflictError,
    HiringContextNotFoundError,
    HiringContextValidationError,
    InterviewAgentContext,
    InvitationCreated,
    ResumeUploaderRole,
    ResumeView,
    VacancyStatus,
    VacancyView,
)
from app.domain.manager_brief import ConfirmationStatus, ManagerBriefStatus
from app.models.hiring_context import CandidateResume, Vacancy
from app.models.interview import (
    CandidateResponse,
    InterviewInvitation,
    InterviewSession,
    InvitationStatus,
    TranscriptionStatus,
)
from app.models.manager_brief import ManagerBriefDraft
from app.interview_config import InterviewInput
from app.services.interview_configuration import (
    invitation_snapshot,
    read_configuration,
    save_configuration,
)
from app.security.invitations import create_invitation_secret, digest_invitation_secret


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return _hash_text(payload)


def _required_text(value: str, name: str, maximum: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise HiringContextValidationError(f"{name} is required")
    if len(normalized) > maximum:
        raise HiringContextValidationError(f"{name} exceeds {maximum} characters")
    return normalized


def _is_expired(value: datetime) -> bool:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value <= _now()


class HiringContextService:
    """Own document records and expose only candidate-scoped downstream context."""

    def __init__(self, session: Session, presenter_dispatcher: object | None = None) -> None:
        self.db = session
        self.presenter_dispatcher = presenter_dispatcher

    def close(self) -> None:
        self.db.close()

    @staticmethod
    def _vacancy_view(vacancy: Vacancy) -> VacancyView:
        return VacancyView(
            id=vacancy.id,
            title=vacancy.title,
            status=vacancy.status,
            source_filename=vacancy.source_filename,
            media_type=vacancy.media_type,
            content_hash=vacancy.content_hash,
            created_at=vacancy.created_at,
        )

    @staticmethod
    def _resume_view(resume: CandidateResume) -> ResumeView:
        return ResumeView(
            id=resume.id,
            vacancy_id=resume.vacancy_id,
            version=resume.version,
            source_filename=resume.source_filename,
            media_type=resume.media_type,
            content_hash=resume.content_hash,
            uploaded_by_role=ResumeUploaderRole(resume.uploaded_by_role),
            created_at=resume.created_at,
        )

    def create_vacancy(
        self,
        *,
        title: str,
        document: bytes,
        filename: str,
        media_type: str,
        actor_id: str,
        idempotency_key: str,
    ) -> VacancyView:
        normalized_title = _required_text(title, "vacancy title", 200)
        actor = _required_text(actor_id, "actor id", 120)
        key = _required_text(idempotency_key, "idempotency key", 128)
        extracted_text, safe_filename, normalized_type = extract_document_text(
            data=document,
            filename=filename,
            media_type=media_type,
        )
        content_hash = _hash_text(extracted_text)
        existing = self.db.scalar(
            select(Vacancy).where(
                Vacancy.created_by == actor,
                Vacancy.idempotency_key == key,
            )
        )
        if existing is not None:
            same_request = (
                existing.title == normalized_title
                and existing.content_hash == content_hash
                and existing.media_type == normalized_type
            )
            if not same_request:
                raise HiringContextConflictError(
                    "idempotency key was already used for another vacancy document"
                )
            return self._vacancy_view(existing)

        vacancy = Vacancy(
            title=normalized_title,
            source_filename=safe_filename,
            media_type=normalized_type,
            byte_size=len(document),
            extracted_text=extracted_text,
            content_hash=content_hash,
            status=VacancyStatus.ACTIVE,
            created_by=actor,
            idempotency_key=key,
            created_at=_now(),
        )
        self.db.add(vacancy)
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            concurrent = self.db.scalar(
                select(Vacancy).where(
                    Vacancy.created_by == actor,
                    Vacancy.idempotency_key == key,
                )
            )
            if (
                concurrent is not None
                and concurrent.title == normalized_title
                and concurrent.content_hash == content_hash
                and concurrent.media_type == normalized_type
            ):
                return self._vacancy_view(concurrent)
            raise HiringContextConflictError(
                "vacancy upload conflicted with a concurrent request"
            ) from error
        self.db.refresh(vacancy)
        return self._vacancy_view(vacancy)

    def list_vacancies(self) -> list[VacancyView]:
        vacancies = self.db.scalars(
            select(Vacancy).order_by(Vacancy.created_at.desc(), Vacancy.id.desc())
        )
        return [self._vacancy_view(vacancy) for vacancy in vacancies]

    def get_vacancy(self, vacancy_id: UUID) -> VacancyView:
        vacancy = self.db.get(Vacancy, vacancy_id)
        if vacancy is None:
            raise HiringContextNotFoundError("vacancy was not found")
        return self._vacancy_view(vacancy)

    def get_interview_configuration(self, vacancy_id: UUID) -> InterviewInput:
        return read_configuration(self.db, vacancy_id)

    def set_interview_configuration(
        self, vacancy_id: UUID, configuration: InterviewInput
    ) -> InterviewInput:
        return save_configuration(self.db, vacancy_id, configuration)

    def create_invitation(
        self,
        *,
        vacancy_id: UUID,
        actor_id: str,
        candidate_alias: str | None,
        expires_in_hours: int,
    ) -> InvitationCreated:
        vacancy = self.db.get(Vacancy, vacancy_id)
        if vacancy is None:
            raise HiringContextNotFoundError("vacancy was not found")
        if vacancy.status is not VacancyStatus.ACTIVE:
            raise HiringContextConflictError("vacancy is not active")
        actor = _required_text(actor_id, "actor id", 120)
        alias = candidate_alias.strip() if candidate_alias else None
        if alias is not None and len(alias) > 120:
            raise HiringContextValidationError(
                "candidate alias exceeds 120 characters"
            )
        if not 1 <= expires_in_hours <= 720:
            raise HiringContextValidationError(
                "invitation expiry must be between 1 and 720 hours"
            )

        secret = create_invitation_secret()
        invitation = InterviewInvitation(
            token_digest=digest_invitation_secret(secret),
            vacancy_id=vacancy.id,
            candidate_alias=alias,
            created_by=actor,
            expires_at=_now() + timedelta(hours=expires_in_hours),
            status=InvitationStatus.ACTIVE,
            question_config=invitation_snapshot(vacancy),
            follow_up_after_all_answers=False,
        )
        self.db.add(invitation)
        self.db.commit()
        self.db.refresh(invitation)
        if self.presenter_dispatcher is not None:
            try:
                self.presenter_dispatcher.prewarm(invitation)
            except Exception:
                # Presenter media is an enhancement; invitation creation is authoritative.
                pass
        return InvitationCreated(
            invitation_id=invitation.id,
            vacancy_id=vacancy.id,
            candidate_token=secret,
            candidate_url=(
                f"{settings.public_base_url.rstrip('/')}/interview"
                f"?token={quote(secret, safe='')}"
            ),
            expires_at=invitation.expires_at,
        )

    def _active_invitation(self, secret: str) -> InterviewInvitation | None:
        if not secret:
            return None
        invitation = self.db.scalar(
            select(InterviewInvitation).where(
                InterviewInvitation.token_digest == digest_invitation_secret(secret)
            )
        )
        if (
            invitation is None
            or invitation.status is not InvitationStatus.ACTIVE
            or _is_expired(invitation.expires_at)
            or invitation.vacancy_id is None
        ):
            return None
        return invitation

    def upload_resume(
        self,
        *,
        secret: str,
        document: bytes,
        filename: str,
        media_type: str,
        idempotency_key: str,
    ) -> ResumeView | None:
        invitation = self._active_invitation(secret)
        if invitation is None:
            return None
        session = self.db.scalar(
            select(InterviewSession).where(
                InterviewSession.invitation_id == invitation.id
            )
        )
        if session is None or session.consented_at is None:
            raise CandidateConsentRequiredError(
                "consent is required before uploading a resume"
            )

        return self._store_resume(
            invitation=invitation,
            document=document,
            filename=filename,
            media_type=media_type,
            idempotency_key=idempotency_key,
            uploaded_by_role=ResumeUploaderRole.CANDIDATE,
            uploaded_by_actor_id=None,
        )

    def recruiter_upload_resume(
        self,
        *,
        vacancy_id: UUID,
        invitation_id: UUID,
        actor_id: str,
        document: bytes,
        filename: str,
        media_type: str,
        idempotency_key: str,
    ) -> ResumeView:
        actor = _required_text(actor_id, "actor id", 120)
        vacancy = self.db.get(Vacancy, vacancy_id)
        invitation = self.db.get(InterviewInvitation, invitation_id)
        if (
            vacancy is None
            or invitation is None
            or invitation.vacancy_id != vacancy.id
        ):
            raise HiringContextNotFoundError("application was not found")
        if (
            vacancy.status is not VacancyStatus.ACTIVE
            or invitation.status is not InvitationStatus.ACTIVE
            or _is_expired(invitation.expires_at)
        ):
            raise HiringContextConflictError("application is not active")

        return self._store_resume(
            invitation=invitation,
            document=document,
            filename=filename,
            media_type=media_type,
            idempotency_key=idempotency_key,
            uploaded_by_role=ResumeUploaderRole.RECRUITER,
            uploaded_by_actor_id=actor,
        )

    def _store_resume(
        self,
        *,
        invitation: InterviewInvitation,
        document: bytes,
        filename: str,
        media_type: str,
        idempotency_key: str,
        uploaded_by_role: ResumeUploaderRole,
        uploaded_by_actor_id: str | None,
    ) -> ResumeView:
        key = _required_text(idempotency_key, "idempotency key", 128)
        extracted_text, safe_filename, normalized_type = extract_document_text(
            data=document,
            filename=filename,
            media_type=media_type,
            maximum_characters=50_000,
        )
        content_hash = _hash_text(extracted_text)
        locked_invitation = self.db.scalar(
            select(InterviewInvitation)
            .where(InterviewInvitation.id == invitation.id)
            .with_for_update()
        )
        if (
            locked_invitation is None
            or locked_invitation.status is not InvitationStatus.ACTIVE
            or _is_expired(locked_invitation.expires_at)
        ):
            self.db.rollback()
            raise HiringContextConflictError("application is no longer active")
        existing = self.db.scalar(
            select(CandidateResume).where(
                CandidateResume.invitation_id == invitation.id,
                CandidateResume.idempotency_key == key,
            )
        )
        if existing is not None:
            if (
                existing.content_hash != content_hash
                or existing.media_type != normalized_type
                or existing.uploaded_by_role != uploaded_by_role.value
                or existing.uploaded_by_actor_id != uploaded_by_actor_id
            ):
                raise HiringContextConflictError(
                    "idempotency key was already used for another resume document"
                )
            return self._resume_view(existing)

        current_version = self.db.scalar(
            select(func.max(CandidateResume.version)).where(
                CandidateResume.invitation_id == invitation.id
            )
        )
        resume = CandidateResume(
            invitation_id=invitation.id,
            vacancy_id=invitation.vacancy_id,
            version=(current_version or 0) + 1,
            source_filename=safe_filename,
            media_type=normalized_type,
            byte_size=len(document),
            extracted_text=extracted_text,
            content_hash=content_hash,
            idempotency_key=key,
            uploaded_by_role=uploaded_by_role.value,
            uploaded_by_actor_id=uploaded_by_actor_id,
            created_at=_now(),
        )
        self.db.add(resume)
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            concurrent = self.db.scalar(
                select(CandidateResume).where(
                    CandidateResume.invitation_id == invitation.id,
                    CandidateResume.idempotency_key == key,
                )
            )
            if (
                concurrent is not None
                and concurrent.content_hash == content_hash
                and concurrent.media_type == normalized_type
                and concurrent.uploaded_by_role == uploaded_by_role.value
                and concurrent.uploaded_by_actor_id == uploaded_by_actor_id
            ):
                return self._resume_view(concurrent)
            raise HiringContextConflictError(
                "resume upload conflicted with a concurrent request; retry it"
            ) from error
        self.db.refresh(resume)
        return self._resume_view(resume)

    def candidate_resume(self, secret: str) -> ResumeView | None:
        invitation = self._active_invitation(secret)
        if invitation is None:
            return None
        resume = self._latest_resume(invitation.id)
        if resume is None:
            raise HiringContextNotFoundError("resume has not been uploaded")
        return self._resume_view(resume)

    def _latest_resume(self, invitation_id: UUID) -> CandidateResume | None:
        return self.db.scalar(
            select(CandidateResume)
            .where(CandidateResume.invitation_id == invitation_id)
            .order_by(CandidateResume.version.desc())
            .limit(1)
        )

    def list_applications(self, vacancy_id: UUID) -> list[ApplicationView]:
        if self.db.get(Vacancy, vacancy_id) is None:
            raise HiringContextNotFoundError("vacancy was not found")
        invitations = self.db.scalars(
            select(InterviewInvitation)
            .where(InterviewInvitation.vacancy_id == vacancy_id)
            .order_by(InterviewInvitation.expires_at.desc())
        )
        result: list[ApplicationView] = []
        for invitation in invitations:
            session = self.db.scalar(
                select(InterviewSession).where(
                    InterviewSession.invitation_id == invitation.id
                )
            )
            resume = self._latest_resume(invitation.id)
            result.append(
                ApplicationView(
                    invitation_id=invitation.id,
                    vacancy_id=vacancy_id,
                    candidate_alias=invitation.candidate_alias,
                    invitation_status=invitation.status.value,
                    session_id=session.id if session else None,
                    resume=self._resume_view(resume) if resume else None,
                )
            )
        return result

    def build_agent_context(
        self, *, vacancy_id: UUID, invitation_id: UUID
    ) -> InterviewAgentContext:
        invitation = self.db.get(InterviewInvitation, invitation_id)
        if invitation is None or invitation.vacancy_id != vacancy_id:
            raise HiringContextNotFoundError("application was not found")
        vacancy = self.db.get(Vacancy, vacancy_id)
        if vacancy is None:
            raise HiringContextNotFoundError("vacancy was not found")

        session = self.db.scalar(
            select(InterviewSession).where(
                InterviewSession.invitation_id == invitation.id
            )
        )
        resume = self._latest_resume(invitation.id)
        answers: list[AgentAnswerContext] = []
        if session is not None:
            response_models = list(
                self.db.scalars(
                    select(CandidateResponse).where(
                        CandidateResponse.session_id == session.id
                    )
                )
            )
            response_models.sort(
                key=lambda response: (
                    response.created_at.isoformat() if response.created_at else "",
                    str(response.id),
                )
            )
            for response in response_models:
                text = (
                    response.transcript_text
                    if response.transcription_status is TranscriptionStatus.COMPLETED
                    else None
                )
                answers.append(
                    AgentAnswerContext(
                        response_id=response.id,
                        question_id=response.question_id,
                        status=response.transcription_status.value,
                        untrusted_text=text,
                    )
                )

        approved_brief = self._approved_brief(vacancy_id)
        vacancy_context = AgentDocumentContext(
            document_id=vacancy.id,
            source_kind="vacancy",
            media_type=vacancy.media_type,
            content_hash=vacancy.content_hash,
            untrusted_text=vacancy.extracted_text,
        )
        resume_context = (
            AgentDocumentContext(
                document_id=resume.id,
                source_kind="resume",
                media_type=resume.media_type,
                content_hash=resume.content_hash,
                untrusted_text=resume.extracted_text,
                version=resume.version,
                uploaded_by_role=ResumeUploaderRole(resume.uploaded_by_role),
            )
            if resume is not None
            else None
        )
        hash_input = {
            "schema_version": "interview_agent_context_v1",
            "invitation_id": invitation.id,
            "session_id": session.id if session else None,
            "vacancy": {"id": vacancy.id, "content_hash": vacancy.content_hash},
            "approved_brief_hash": (
                approved_brief.content_hash if approved_brief else None
            ),
            "resume": (
                {
                    "id": resume.id,
                    "content_hash": resume.content_hash,
                    "version": resume.version,
                    "uploaded_by_role": resume.uploaded_by_role,
                }
                if resume
                else None
            ),
            "answers": [answer.model_dump(mode="json") for answer in answers],
        }
        return InterviewAgentContext(
            invitation_id=invitation.id,
            session_id=session.id if session else None,
            vacancy=vacancy_context,
            approved_brief=approved_brief,
            resume=resume_context,
            answers=answers,
            context_hash=_canonical_hash(hash_input),
        )

    def _approved_brief(self, vacancy_id: UUID) -> ApprovedBriefContext | None:
        draft = self.db.scalar(
            select(ManagerBriefDraft)
            .where(
                ManagerBriefDraft.vacancy_id == vacancy_id,
                ManagerBriefDraft.status == ManagerBriefStatus.APPROVED,
            )
            .order_by(ManagerBriefDraft.version.desc())
            .limit(1)
        )
        if draft is None:
            return None
        confirmed_fields = [
            {
                "id": item["id"],
                "field_key": item["field_key"],
                "value": item["value"],
                "origin": item["origin"],
                "source_fragment_ids": item.get("source_fragment_ids", []),
            }
            for item in draft.fields_payload
            if item.get("confirmation_status") == ConfirmationStatus.CONFIRMED.value
        ]
        return ApprovedBriefContext(
            profile_id=draft.id,
            version=draft.version,
            content_hash=draft.content_hash,
            confirmed_fields=confirmed_fields,
        )
