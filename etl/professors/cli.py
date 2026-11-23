"""Professors ETL command line. An admin runs it on demand; the two steps can run on their own.

Run after the schedule sync (it reads the faculty codes from the database). The migrations run first:
    docker compose --profile etl run --rm --entrypoint sh etl -c "alembic upgrade head && python -m etl.professors.cli"
    ... python -m etl.professors.cli --step extract            # only the files
    ... python -m etl.professors.cli --step load --faculty ing  # only the database, one faculty
"""

import argparse
import asyncio

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Faculty
from etl.professors.extract import ExtractResult, extract_faculties
from etl.professors.load import LoadReport, load_professors


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ULBS professors ETL")
    parser.add_argument("--step", choices=("all", "extract", "load"), default="all",
                        help="all = extract then load (default); extract = write the files; load = read the files")
    parser.add_argument("--faculty", help="one faculty code, e.g. ing (default: all faculties)")
    return parser.parse_args(argv)


def _faculty_codes(faculty: str | None) -> list[str]:
    with SessionLocal() as db:
        query = select(Faculty.code).order_by(Faculty.code)
        if faculty is not None:
            query = query.where(Faculty.code == faculty)
        return list(db.scalars(query).all())


def format_extract(results: list[ExtractResult]) -> str:
    lines = []
    for r in results:
        if r.status == "ok":
            lines.append(f"[{r.code}] ok: {r.stored} professors, {r.skipped} skipped -> {r.path}")
        else:
            lines.append(f"[{r.code}] FAILED: {r.note}")
    return "\n".join(lines)


def format_load(report: LoadReport) -> str:
    lines = [
        f"files read: {len(report.files)}   errors: {len(report.errors)}",
        f"distinct professors: {report.records}   same id in several faculties: {report.repeated_ids}",
        f"records left out, same email as another id: {report.merged_emails}",
        f"moved to a new id (same email, full run): {len(report.rekeyed)}",
        f"stored (inserted or updated): {report.stored}",
        f"refused by the database (email held by another stored id): {len(report.email_conflicts)}",
    ]
    lines.extend(f"  error: {error}" for error in report.errors)
    lines.extend(f"  warning: {warning}" for warning in report.warnings)
    lines.extend(f"  refused, id {pid}" for pid in report.email_conflicts)
    return "\n".join(lines)


async def _main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if args.step in ("all", "extract"):
        codes = _faculty_codes(args.faculty)
        if not codes:
            print("No faculty found in the database. Run the schedule sync step first.")
            return
        print(format_extract(await extract_faculties(codes)))
    if args.step in ("all", "load"):
        if args.step == "all":
            print()
        print(format_load(load_professors(faculty=args.faculty)))


if __name__ == "__main__":
    asyncio.run(_main())
