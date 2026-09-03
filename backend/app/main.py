"""FastAPI entrypoint for the interview application."""

from fastapi import FastAPI

app = FastAPI(title="AI Interviewer API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Return a dependency-free liveness response."""
    return {"status": "ok"}
