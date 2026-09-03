"""Queue a local demo clarification; this represents a future agent's output."""

import argparse
from uuid import UUID

from app.database import workflow_factory
from app.services.follow_up_queue import enqueue_clarification


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("response_id", type=UUID)
    parser.add_argument("text")
    args = parser.parse_args()
    follow_up = enqueue_clarification(workflow_factory(), args.response_id, args.text)
    print(follow_up.id)


if __name__ == "__main__":
    main()
