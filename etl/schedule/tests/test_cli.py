"""Command-line defaults. No network, no database."""
from etl.schedule.downloader import _parse_args


def test_no_arguments_runs_all_steps_for_all_faculties() -> None:
    args = _parse_args([])
    assert args.step == "all"
    assert args.faculty is None


def test_partial_steps_and_single_faculty_are_accepted() -> None:
    assert _parse_args(["--step", "schedules", "--faculty", "sti"]).step == "schedules"
    assert _parse_args(["--step", "sync"]).step == "sync"
