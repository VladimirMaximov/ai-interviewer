import unittest
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain.manager_brief import (
    AgentFieldProposal,
    AgentRunStatus,
    AgentOutputError,
    ConfirmationStatus,
    FieldKey,
    FieldOrigin,
    ManagerBriefAgentResult,
    ManagerBriefConflictError,
    ManagerBriefValidationError,
    UnresolvedField,
)
from app.models.interview import Base
from app.models.manager_brief import ManagerBriefAgentRun
from app.services.manager_brief import ManagerBriefService


class StubManagerBriefAgent:
    model_id = "manager-brief-stub"
    model_version = "1"
    prompt_id = "manager-brief-v1"

    def __init__(self, result: ManagerBriefAgentResult) -> None:
        self.result = result
        self.calls = 0
        self.last_fragments: list[dict] = []

    def draft(
        self, *, vacancy_id: str, fragments: list[dict]
    ) -> ManagerBriefAgentResult:
        self.calls += 1
        self.last_fragments = fragments
        return self.result


class RetryAgent(StubManagerBriefAgent):
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.calls = 0
        self.last_fragments = []

    def draft(
        self, *, vacancy_id: str, fragments: list[dict]
    ) -> ManagerBriefAgentResult:
        self.calls += 1
        self.last_fragments = fragments
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return ManagerBriefAgentResult.model_validate(outcome)


def sourced_result(fragment_id: str) -> ManagerBriefAgentResult:
    return ManagerBriefAgentResult(
        schema_version="manager_brief_v1",
        purpose="manager_brief_draft",
        fields=[
            AgentFieldProposal(
                field_key=FieldKey.ROLE,
                value="Backend-разработчик",
                origin=FieldOrigin.MANAGER_SOURCE,
                source_fragment_ids=[fragment_id],
                source_quotes=["Backend-разработчик"],
                confidence=0.98,
            ),
            AgentFieldProposal(
                field_key=FieldKey.MUST_HAVE_COMPETENCIES,
                value=["Python", "PostgreSQL"],
                origin=FieldOrigin.MANAGER_SOURCE,
                source_fragment_ids=[fragment_id],
                source_quotes=["Python и PostgreSQL"],
                confidence=0.92,
            ),
            AgentFieldProposal(
                field_key=FieldKey.NICE_TO_HAVE_COMPETENCIES,
                value=["Опыт с очередями сообщений"],
                origin=FieldOrigin.AGENT_SUGGESTION,
                source_fragment_ids=[],
                source_quotes=[],
                confidence=0.55,
            ),
        ],
        unresolved_fields=[
            UnresolvedField(
                field_key=FieldKey.SENIORITY,
                question="Какой уровень специалиста нужен?",
            )
        ],
    )


class ManagerBriefServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.db = sessionmaker(engine, expire_on_commit=False)()
        self.vacancy_id = uuid4()

    def tearDown(self) -> None:
        self.db.close()

    def _service(self) -> tuple[ManagerBriefService, StubManagerBriefAgent]:
        # Fragment identifiers are deterministic, so obtain one from the same source.
        fragments = ManagerBriefService.fragment_source(
            "Ищем Backend-разработчика. Обязательны Python и PostgreSQL."
        )
        agent = StubManagerBriefAgent(sourced_result(fragments[0]["id"]))
        return ManagerBriefService(self.db, agent), agent

    def test_agent_draft_preserves_sources_and_marks_suggestions(self) -> None:
        service, _ = self._service()

        draft = service.create_draft(
            vacancy_id=self.vacancy_id,
            source_text="Ищем Backend-разработчика. Обязательны Python и PostgreSQL.",
            actor_id="manager-1",
            idempotency_key="brief-create-001",
        )

        by_key = {field.field_key: field for field in draft.fields}
        self.assertEqual(
            by_key[FieldKey.ROLE].confirmation_status,
            ConfirmationStatus.CONFIRMED,
        )
        self.assertEqual(by_key[FieldKey.ROLE].confirmed_by, "manager-1")
        self.assertIsNotNone(by_key[FieldKey.ROLE].confirmed_at)
        self.assertTrue(by_key[FieldKey.ROLE].source_fragment_ids)
        self.assertEqual(
            by_key[FieldKey.NICE_TO_HAVE_COMPETENCIES].confirmation_status,
            ConfirmationStatus.PROPOSED,
        )
        self.assertIsNone(by_key[FieldKey.NICE_TO_HAVE_COMPETENCIES].confirmed_by)
        self.assertEqual(draft.unresolved_fields[0].field_key, FieldKey.SENIORITY)

    def test_same_idempotency_key_returns_the_same_draft(self) -> None:
        service, agent = self._service()
        arguments = {
            "vacancy_id": self.vacancy_id,
            "source_text": "Ищем Backend-разработчика. Обязательны Python и PostgreSQL.",
            "actor_id": "manager-1",
            "idempotency_key": "brief-create-002",
        }

        first = service.create_draft(**arguments)
        second = service.create_draft(**arguments)

        self.assertEqual(first.id, second.id)
        self.assertEqual(agent.calls, 1)

    def test_reusing_key_for_other_input_is_a_conflict(self) -> None:
        service, _ = self._service()
        service.create_draft(
            vacancy_id=self.vacancy_id,
            source_text="Ищем Backend-разработчика. Обязательны Python и PostgreSQL.",
            actor_id="manager-1",
            idempotency_key="brief-create-003",
        )

        with self.assertRaises(ManagerBriefConflictError):
            service.create_draft(
                vacancy_id=self.vacancy_id,
                source_text="Теперь ищем другого специалиста.",
                actor_id="manager-1",
                idempotency_key="brief-create-003",
            )

    def test_unsupported_source_quote_is_rejected_before_draft_persistence(
        self,
    ) -> None:
        result = ManagerBriefAgentResult(
            schema_version="manager_brief_v1",
            purpose="manager_brief_draft",
            fields=[
                AgentFieldProposal(
                    field_key=FieldKey.ROLE,
                    value="Data Scientist",
                    origin=FieldOrigin.MANAGER_SOURCE,
                    source_fragment_ids=["unknown-fragment"],
                    source_quotes=["Data Scientist"],
                    confidence=0.9,
                )
            ],
            unresolved_fields=[],
        )
        service = ManagerBriefService(self.db, StubManagerBriefAgent(result))

        with self.assertRaises(AgentOutputError):
            service.create_draft(
                vacancy_id=self.vacancy_id,
                source_text="Нужен backend-разработчик.",
                actor_id="manager-1",
                idempotency_key="brief-invalid-001",
            )
        self.assertEqual(service.list_drafts(self.vacancy_id), [])

    def test_failed_output_can_retry_without_losing_attempt_lineage(self) -> None:
        source = "Ищем Backend-разработчика. Обязательны Python и PostgreSQL."
        fragment_id = ManagerBriefService.fragment_source(source)[0]["id"]
        agent = RetryAgent(
            [AgentOutputError("invalid structured output"), sourced_result(fragment_id)]
        )
        service = ManagerBriefService(self.db, agent)
        arguments = {
            "vacancy_id": self.vacancy_id,
            "source_text": source,
            "actor_id": "manager-1",
            "idempotency_key": "brief-retry-001",
        }

        with self.assertRaises(AgentOutputError):
            service.create_draft(**arguments)
        draft = service.create_draft(**arguments)
        runs = self.db.scalars(
            select(ManagerBriefAgentRun).order_by(ManagerBriefAgentRun.attempt)
        ).all()

        self.assertEqual(draft.version, 1)
        self.assertEqual(
            [run.status for run in runs],
            [AgentRunStatus.INVALID_OUTPUT, AgentRunStatus.SUCCEEDED],
        )

    def test_retry_limit_prevents_unbounded_provider_calls(self) -> None:
        source = "Ищем Backend-разработчика."
        agent = RetryAgent(
            [
                AgentOutputError("invalid output 1"),
                AgentOutputError("invalid output 2"),
                sourced_result(ManagerBriefService.fragment_source(source)[0]["id"]),
            ]
        )
        service = ManagerBriefService(self.db, agent, max_attempts=2)
        arguments = {
            "vacancy_id": self.vacancy_id,
            "source_text": source,
            "actor_id": "manager-1",
            "idempotency_key": "brief-retry-limit",
        }

        with self.assertRaises(AgentOutputError):
            service.create_draft(**arguments)
        with self.assertRaises(AgentOutputError):
            service.create_draft(**arguments)
        with self.assertRaises(ManagerBriefConflictError) as raised:
            service.create_draft(**arguments)

        self.assertEqual(raised.exception.code, "retry_limit_reached")
        self.assertEqual(agent.calls, 2)

    def test_manager_can_edit_confirm_reject_and_approve(self) -> None:
        service, _ = self._service()
        draft = service.create_draft(
            vacancy_id=self.vacancy_id,
            source_text="Ищем Backend-разработчика. Обязательны Python и PostgreSQL.",
            actor_id="manager-1",
            idempotency_key="brief-create-004",
        )

        updated = service.update_draft(
            vacancy_id=self.vacancy_id,
            draft_id=draft.id,
            expected_revision=draft.revision,
            actor_id="manager-1",
            updates=[
                {
                    "field_key": FieldKey.SENIORITY,
                    "value": "middle",
                    "confirmation_status": ConfirmationStatus.CONFIRMED,
                },
                {
                    "field_key": FieldKey.NICE_TO_HAVE_COMPETENCIES,
                    "value": ["Опыт с очередями сообщений"],
                    "confirmation_status": ConfirmationStatus.REJECTED,
                },
            ],
        )
        approved = service.approve_draft(
            vacancy_id=self.vacancy_id,
            draft_id=draft.id,
            expected_revision=updated.revision,
            actor_id="manager-1",
            confirm_no_automatic_rejection=True,
        )
        context = service.get_approved_context(self.vacancy_id)

        self.assertEqual(approved.status.value, "approved")
        self.assertNotIn("source_text", context.model_dump())
        self.assertNotIn("confidence", context.fields[0].model_dump())
        self.assertNotIn("source_quotes", context.fields[0].model_dump())
        self.assertNotIn(
            FieldKey.NICE_TO_HAVE_COMPETENCIES,
            {field.field_key for field in context.fields},
        )
        self.assertEqual(
            next(
                field
                for field in context.fields
                if field.field_key is FieldKey.SENIORITY
            ).origin,
            FieldOrigin.MANAGER_EDITED,
        )

    def test_stale_revision_and_approved_mutation_are_rejected(self) -> None:
        service, _ = self._service()
        draft = service.create_draft(
            vacancy_id=self.vacancy_id,
            source_text="Ищем Backend-разработчика. Обязательны Python и PostgreSQL.",
            actor_id="manager-1",
            idempotency_key="brief-create-005",
        )
        updated = service.update_draft(
            vacancy_id=self.vacancy_id,
            draft_id=draft.id,
            expected_revision=draft.revision,
            actor_id="manager-1",
            updates=[
                {
                    "field_key": FieldKey.NICE_TO_HAVE_COMPETENCIES,
                    "value": [],
                    "confirmation_status": ConfirmationStatus.REJECTED,
                }
            ],
        )
        with self.assertRaises(ManagerBriefConflictError):
            service.update_draft(
                vacancy_id=self.vacancy_id,
                draft_id=draft.id,
                expected_revision=draft.revision,
                actor_id="manager-1",
                updates=[],
            )
        approved = service.approve_draft(
            vacancy_id=self.vacancy_id,
            draft_id=draft.id,
            expected_revision=updated.revision,
            actor_id="manager-1",
            confirm_no_automatic_rejection=True,
        )
        with self.assertRaises(ManagerBriefConflictError):
            service.update_draft(
                vacancy_id=self.vacancy_id,
                draft_id=draft.id,
                expected_revision=approved.revision,
                actor_id="manager-1",
                updates=[],
            )

    def test_sensitive_criterion_blocks_approval(self) -> None:
        service, _ = self._service()
        draft = service.create_draft(
            vacancy_id=self.vacancy_id,
            source_text="Ищем Backend-разработчика. Обязательны Python и PostgreSQL.",
            actor_id="manager-1",
            idempotency_key="brief-create-006",
        )
        updated = service.update_draft(
            vacancy_id=self.vacancy_id,
            draft_id=draft.id,
            expected_revision=draft.revision,
            actor_id="manager-1",
            updates=[
                {
                    "field_key": FieldKey.CONSTRAINTS,
                    "value": ["Оценивать акцент кандидата"],
                    "confirmation_status": ConfirmationStatus.CONFIRMED,
                },
                {
                    "field_key": FieldKey.NICE_TO_HAVE_COMPETENCIES,
                    "value": [],
                    "confirmation_status": ConfirmationStatus.REJECTED,
                },
            ],
        )

        with self.assertRaises(ManagerBriefValidationError) as raised:
            service.approve_draft(
                vacancy_id=self.vacancy_id,
                draft_id=draft.id,
                expected_revision=updated.revision,
                actor_id="manager-1",
                confirm_no_automatic_rejection=True,
            )
        self.assertIn(
            "prohibited_trait", {issue["code"] for issue in raised.exception.issues}
        )

    def test_new_approval_supersedes_previous_version(self) -> None:
        service, _ = self._service()
        source = "Ищем Backend-разработчика. Обязательны Python и PostgreSQL."

        approved_ids = []
        for number in (1, 2):
            draft = service.create_draft(
                vacancy_id=self.vacancy_id,
                source_text=source,
                actor_id="manager-1",
                idempotency_key=f"brief-version-{number}",
            )
            draft = service.update_draft(
                vacancy_id=self.vacancy_id,
                draft_id=draft.id,
                expected_revision=draft.revision,
                actor_id="manager-1",
                updates=[
                    {
                        "field_key": FieldKey.NICE_TO_HAVE_COMPETENCIES,
                        "value": [],
                        "confirmation_status": ConfirmationStatus.REJECTED,
                    }
                ],
            )
            approved = service.approve_draft(
                vacancy_id=self.vacancy_id,
                draft_id=draft.id,
                expected_revision=draft.revision,
                actor_id="manager-1",
                confirm_no_automatic_rejection=True,
            )
            approved_ids.append(approved.id)

        first = service.get_draft(self.vacancy_id, approved_ids[0])
        active = service.get_approved_context(self.vacancy_id)
        self.assertEqual(first.status.value, "superseded")
        self.assertEqual(active.profile_id, approved_ids[1])
        self.assertEqual(active.version, 2)

    def test_no_extra_manager_wishes_can_approve_empty_context(self) -> None:
        agent = StubManagerBriefAgent(
            ManagerBriefAgentResult(
                schema_version="manager_brief_v1",
                purpose="manager_brief_draft",
                fields=[],
                unresolved_fields=[],
            )
        )
        service = ManagerBriefService(self.db, agent)
        draft = service.create_draft(
            vacancy_id=self.vacancy_id,
            source_text="Дополнительных пожеланий нет.",
            actor_id="manager-1",
            idempotency_key="brief-empty-context",
        )

        approved = service.approve_draft(
            vacancy_id=self.vacancy_id,
            draft_id=draft.id,
            expected_revision=draft.revision,
            actor_id="manager-1",
            confirm_no_automatic_rejection=True,
        )

        self.assertEqual(approved.status.value, "approved")
        self.assertEqual(service.get_approved_context(self.vacancy_id).fields, [])


if __name__ == "__main__":
    unittest.main()
