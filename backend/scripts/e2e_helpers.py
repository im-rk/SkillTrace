"""
Out-of-band helpers for browser E2E tests -- things a real user can't do through
the UI but a test needs (e.g. time travel).

    uv run python -m scripts.e2e_helpers backdate-session <session_id> <minutes>
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import update  # noqa: E402

from app.core.db.session import async_session_maker  # noqa: E402
from app.modules.live_session_gateway.models import ExamSession  # noqa: E402


async def backdate_session(session_id: str, minutes: int) -> None:
    """Pretend the student started `minutes` ago, so the auto-submit sweep sees them out of time."""
    async with async_session_maker() as session:
        await session.execute(
            update(ExamSession)
            .where(ExamSession.id == UUID(session_id))
            .values(started_at=datetime.now(timezone.utc) - timedelta(minutes=minutes))
        )
        await session.commit()


if __name__ == "__main__":
    command, *args = sys.argv[1:]
    if command == "backdate-session":
        asyncio.run(backdate_session(args[0], int(args[1])))
    else:
        raise SystemExit(f"unknown command {command!r}")
