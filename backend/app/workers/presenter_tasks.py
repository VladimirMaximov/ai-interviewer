"""Serialized GPU task entrypoint."""

from uuid import UUID

from app.workers.celery_app import celery_app


@celery_app.task(
    name="app.workers.presenter_tasks.render_presenter",
    autoretry_for=(RuntimeError,), retry_backoff=True, max_retries=2,
)
def render_presenter(asset_id: str) -> None:
    from app.database import presenter_asset_service_factory
    from app.config import settings

    presenter_asset_service_factory().process(
        UUID(asset_id), portrait=__import__("pathlib").Path(settings.presenter_portrait_path)
    )
