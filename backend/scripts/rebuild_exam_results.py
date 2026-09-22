"""
Full rebuild of mv_exam_results from the underlying tables (disaster recovery).

    uv run python -m scripts.rebuild_exam_results

Uses a plain (non-concurrent) REFRESH, which takes an exclusive lock and blocks reads
while it runs -- fine for recovery, which is why the day-to-day path is CONCURRENTLY.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db.session import async_session_maker  # noqa: E402
from app.modules.results.refresh_service import rebuild_exam_results  # noqa: E402


async def main() -> None:
    async with async_session_maker() as session:
        await rebuild_exam_results(session)
    print("mv_exam_results rebuilt")


if __name__ == "__main__":
    asyncio.run(main())
