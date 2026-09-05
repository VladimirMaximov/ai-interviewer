"""Queue a local demo clarification; this represents a future agent's output."""

import argparse
from uuid import UUID

from app.database import workflow_factory
from app.services.follow_up_queue import enqueue_clarification, enqueue_final_clarification


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--response-id", type=UUID, help="Source response for a per-answer clarification.")
    parser.add_argument("--session-id", type=UUID, help="Session for a whole-interview clarification.")
    parser.add_argument("text")
    args = parser.parse_args()
    if bool(args.response_id) == bool(args.session_id):
        parser.error("provide exactly one of --response-id or --session-id")
    workflow = workflow_factory()
    follow_up = (
        enqueue_clarification(workflow, args.response_id, args.text)
        if args.response_id
        else enqueue_final_clarification(workflow, args.session_id, args.text)
    )
    print(follow_up.id)


if __name__ == "__main__":
    main()
