"""
Rebuild student_skill_state from the immutable `responses` log.

    uv run python -m scripts.recompute_mastery --student <uuid> --skill <uuid> [--dry-run]
    uv run python -m scripts.recompute_mastery --all [--dry-run]

--dry-run reports what would change (and any place where the log disagrees with
itself) without writing. Run it before a deploy as a consistency check.
"""
import argparse
import asyncio
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db.session import async_session_maker  # noqa: E402
from app.modules.quiz_engine.mastery_recompute import list_student_skill_pairs, recompute_student_skill_state  # noqa: E402


async def main(student: str | None, skill: str | None, all_pairs: bool, dry_run: bool) -> int:
    problems = 0
    async with async_session_maker() as session:
        pairs = await list_student_skill_pairs(session) if all_pairs else [(UUID(student), UUID(skill))]
        for student_id, skill_id in pairs:
            r = await recompute_student_skill_state(session, student_id, skill_id, apply=not dry_run)
            if r.mastery is None:
                status = "no responses - left alone"
            elif r.changed:
                status = f"{'WOULD REPAIR' if dry_run else 'REPAIRED'} {r.previous_mastery} -> {r.mastery}"
                problems += 1
            else:
                status = f"ok ({r.mastery})"
            print(f"student={student_id} skill={skill_id}: {status} [{r.total_attempts} responses]")
            for line in r.divergences:
                print(f"    DIVERGENCE: {line}")
                problems += 1
    print(f"done: {len(pairs)} pair(s), {problems} problem(s)" + (" (dry run, nothing written)" if dry_run else ""))
    return 1 if problems and dry_run else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--student")
    parser.add_argument("--skill")
    parser.add_argument("--all", action="store_true", dest="all_pairs")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.all_pairs and not (args.student and args.skill):
        parser.error("give --student and --skill, or --all")
    raise SystemExit(asyncio.run(main(args.student, args.skill, args.all_pairs, args.dry_run)))
