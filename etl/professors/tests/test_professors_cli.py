"""Professors command line arguments."""
from etl.professors.cli import _parse_args


def test_defaults_run_every_step_for_every_faculty() -> None:
    args = _parse_args([])
    assert args.step == "all"
    assert args.faculty is None


def test_one_step_and_one_faculty_are_accepted() -> None:
    args = _parse_args(["--step", "load", "--faculty", "ing"])
    assert (args.step, args.faculty) == ("load", "ing")
