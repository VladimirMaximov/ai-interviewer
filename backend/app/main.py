"""FastAPI entrypoint for the interview application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.candidate import router as candidate_router
from app.database import workflow_factory

app = FastAPI(title="AI Interviewer API", version="0.1.0")
app.state.workflow_factory = workflow_factory
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
app.include_router(candidate_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Return a dependency-free liveness response."""
    return {"status": "ok"}
