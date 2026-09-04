"""FastAPI entrypoint for the interview application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.candidate import router as candidate_router
from app.api.hiring_context import candidate_document_router
from app.api.hiring_context import hiring_context_exception_handler
from app.api.hiring_context import recruiter_router
from app.api.manager import manager_brief_exception_handler
from app.api.manager import router as manager_router
from app.api.multi_agent import candidate_router as candidate_question_router
from app.api.multi_agent import multi_agent_exception_handler
from app.api.multi_agent import router as multi_agent_router
from app.database import (
    hiring_context_service_factory,
    manager_brief_service_factory,
    multi_agent_harness_factory,
    workflow_factory,
)
from app.domain.hiring_context import HiringContextError
from app.domain.manager_brief import ManagerBriefError
from app.domain.multi_agent import MultiAgentError

app = FastAPI(title="AI Interviewer API", version="0.5.0")
app.state.workflow_factory = workflow_factory
app.state.manager_brief_service_factory = manager_brief_service_factory
app.state.hiring_context_service_factory = hiring_context_service_factory
app.state.multi_agent_harness_factory = multi_agent_harness_factory
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(candidate_router)
app.include_router(candidate_document_router)
app.include_router(candidate_question_router)
app.include_router(recruiter_router)
app.include_router(manager_router)
app.include_router(multi_agent_router)
app.add_exception_handler(HiringContextError, hiring_context_exception_handler)
app.add_exception_handler(ManagerBriefError, manager_brief_exception_handler)
app.add_exception_handler(MultiAgentError, multi_agent_exception_handler)


@app.get("/health")
def health() -> dict[str, str]:
    """Return a dependency-free liveness response."""
    return {"status": "ok"}
