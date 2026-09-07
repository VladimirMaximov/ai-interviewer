from datetime import datetime, timedelta, timezone
from time import perf_counter
import unittest
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models.hiring_context  # noqa: F401
import app.models.manager_brief  # noqa: F401
import app.models.multi_agent  # noqa: F401
from app.domain.hiring_context import VacancyStatus
from app.domain.multi_agent import (
    AGGREGATION_VERSION,
    CRITERIA_VERSION,
    POLICY_VERSION,
    SCALE_VERSION,
    AgentPurpose,
    AgentSessionStatus,
    CandidateProfilePayload,
)
from app.models.hiring_context import Vacancy
from app.models.interview import Base, InterviewInvitation, InvitationStatus
from app.models.multi_agent import AgentArtifact, AgentSession
from app.services.multi_agent_harness import MultiAgentHarness


NOW = datetime(2026, 9, 4, 9, 0, tzinfo=timezone.utc)
CANDIDATE_COUNT = 1_000


class NeverCalledAgent:
    model_id = "test-llm"
    model_version = "test-model-v1"

    def __init__(self, purpose: AgentPurpose) -> None:
        self.purpose = purpose
        self.prompt_id = f"{purpose.value}-scale-test"

    def run(self, _context):
        raise AssertionError("ranking must not invoke a semantic LLM agent")


class MultiAgentScaleTests(unittest.TestCase):
    def test_thousand_isolated_profiles_rank_under_two_seconds(self) -> None:
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        db = sessionmaker(engine, expire_on_commit=False)()
        try:
            harness = MultiAgentHarness(
                db,
                {
                    purpose: NeverCalledAgent(purpose)
                    for purpose in AgentPurpose
                },
            )
            vacancy = Vacancy(
                id=uuid4(),
                title="Synthetic backend role",
                source_filename="synthetic-vacancy.txt",
                media_type="text/plain",
                byte_size=18,
                extracted_text="Python PostgreSQL",
                content_hash="a" * 64,
                status=VacancyStatus.ACTIVE,
                created_by="scale-test",
                idempotency_key="scale-test-vacancy",
                created_at=NOW,
            )
            db.add(vacancy)
            compatibility_key = harness._compatibility_key(
                vacancy_id=vacancy.id,
                vacancy_hash=vacancy.content_hash,
                policy_payload=harness.policy,
            )
            invitations = []
            sessions = []
            artifacts = []
            for index in range(CANDIDATE_COUNT):
                readiness = (-0.5, 0.0, 0.5)[index % 3]
                invitation_id = uuid4()
                session_id = uuid4()
                invitation = InterviewInvitation(
                    id=invitation_id,
                    token_digest=f"{index:064x}",
                    vacancy_id=vacancy.id,
                    candidate_alias=f"synthetic-{index:04d}",
                    created_by="scale-test",
                    expires_at=NOW + timedelta(days=1),
                    status=InvitationStatus.ACTIVE,
                )
                session = AgentSession(
                    id=session_id,
                    invitation_id=invitation_id,
                    vacancy_id=vacancy.id,
                    interview_session_id=None,
                    resume_id=None,
                    resume_version=None,
                    resume_hash=None,
                    manager_brief_id=None,
                    manager_brief_version=None,
                    manager_brief_hash=None,
                    vacancy_hash=vacancy.content_hash,
                    criteria_version=CRITERIA_VERSION,
                    scale_version=SCALE_VERSION,
                    aggregation_version=AGGREGATION_VERSION,
                    policy_version=POLICY_VERSION,
                    policy_payload=harness.policy,
                    input_hash=f"{index + CANDIDATE_COUNT:064x}",
                    status=AgentSessionStatus.READY,
                    created_by="scale-test",
                    idempotency_key=f"scale-session-{index:04d}",
                    created_at=NOW,
                    updated_at=NOW,
                )
                profile = CandidateProfilePayload(
                    selected_assessment_artifact_ids=[],
                    resume_positions=[],
                    resume_claims=[],
                    criterion_summaries=[],
                    dimension_summaries=[],
                    overall_readiness=readiness,
                    overall_confidence=0.8,
                    overall_coverage=0.5,
                    strong_pool_eligible=True,
                    eligibility_reason_codes=[],
                    integrity_review_required=False,
                    compatibility_key=compatibility_key,
                )
                artifact = AgentArtifact(
                    id=uuid4(),
                    agent_session_id=session_id,
                    operation_id=None,
                    kind="candidate_profile",
                    schema_version=AGGREGATION_VERSION,
                    payload=profile.model_dump(mode="json"),
                    content_hash=f"{index + 2 * CANDIDATE_COUNT:064x}",
                    created_at=NOW,
                )
                invitations.append(invitation)
                sessions.append(session)
                artifacts.append(artifact)
            db.add_all(invitations)
            db.add_all(sessions)
            db.add_all(artifacts)
            db.commit()

            started = perf_counter()
            ranking = harness.build_ranking(vacancy_id=vacancy.id)
            elapsed = perf_counter() - started

            self.assertLess(elapsed, 2.0)
            self.assertEqual(len(ranking.entries), CANDIDATE_COUNT)
            self.assertEqual(
                len({item.agent_session_id for item in ranking.entries}),
                CANDIDATE_COUNT,
            )
            self.assertEqual(
                len({item.candidate_alias for item in ranking.entries}),
                CANDIDATE_COUNT,
            )
            values = [item.overall_value for item in ranking.entries]
            self.assertEqual(values, sorted(values, reverse=True))
        finally:
            db.close()
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
