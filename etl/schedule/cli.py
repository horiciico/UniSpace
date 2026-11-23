"""Schedule ETL command line. Runs the steps in order; each step lives in its own module.

Run through the compose profile. One command runs all four steps:
    docker compose --profile etl run --rm etl                          # all faculties, steps 1-4
    docker compose --profile etl run --rm etl --faculty sti            # one faculty, steps 1-4
Partial runs:
    docker compose --profile etl run --rm etl --step sync              # steps 1 and 2 only
    docker compose --profile etl run --rm etl --step schedules         # step 3 only (needs step 2 done)
    docker compose --profile etl run --rm etl --step load              # step 4 only (needs step 3 files)
"""

import argparse
import asyncio

from app.db import SessionLocal
from etl.schedule.download import download_schedules, format_download_summary
from etl.schedule.sync import (
    fetch_faculties,
    format_summary,
    sync_planning_units,
    upsert_faculties,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ULBS schedule ETL")
    parser.add_argument("--step", choices=("all", "sync", "schedules", "load"), default="all",
                        help="all = steps 1-4 (default); sync = faculties and planning units; "
                             "schedules = weekly schedule files; load = write the files to the database")
    parser.add_argument("--faculty", help="one faculty code, e.g. sti (default: all faculties)")
    parser.add_argument("--year", type=int, help="academic year (default: the current year)")
    return parser.parse_args(argv)


async def _run_sync(args: argparse.Namespace) -> bool:
    """Steps 1 and 2. Returns False when a requested faculty is not in the database."""
    payload = await fetch_faculties()
    with SessionLocal() as db:
        codes = upsert_faculties(db, payload)
    print("Faculties stored:", len(codes))

    results = await sync_planning_units(args.faculty, args.year)
    if args.faculty and not results:
        print(f"Faculty '{args.faculty}' is not in the database. Known codes: {', '.join(codes)}")
        return False
    print(format_summary(results))
    return True


async def _run_schedules(args: argparse.Namespace) -> bool:
    """Step 3. Returns False when there is no current planning unit to download."""
    results = await download_schedules(args.faculty)
    if not results:
        print(f"No current planning unit found{' for ' + args.faculty if args.faculty else ''}. "
              "Run the sync step first.")
        return False
    print()
    print(format_download_summary(results))
    return True


async def _run_load(args: argparse.Namespace) -> None:
    """Step 4. Imported here so that the CLI does not depend on the loader at import time."""
    from etl.schedule.loader import format_report, load_all

    report = await load_all(args.faculty)
    if not report.files_loaded and not report.errors:
        print("No schedule files found in data/schedules. Run the schedules step first.")
        return
    print(format_report(report))


async def _main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if args.step in ("all", "sync"):
        if not await _run_sync(args):
            return
    if args.step in ("all", "schedules"):
        if args.step == "all":
            print()
        if not await _run_schedules(args) and args.step == "all":
            return
    if args.step in ("all", "load"):
        if args.step == "all":
            print()
        await _run_load(args)


if __name__ == "__main__":
    asyncio.run(_main())

