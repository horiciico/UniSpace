"""Professors load: reading the files. Pure: no network, no database."""
import json

from etl.professors.load import read_documents


def test_unreadable_files_are_reported_and_the_others_are_read(tmp_path) -> None:
    (tmp_path / "ing.json").write_text(json.dumps({"professors": []}), encoding="utf-8")
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")

    docs, errors = read_documents(tmp_path)

    assert [name for name, _ in docs] == ["ing.json"]
    assert len(errors) == 1
    assert errors[0].startswith("bad.json: cannot read")


def test_only_the_asked_faculty_is_read(tmp_path) -> None:
    (tmp_path / "ing.json").write_text("{}", encoding="utf-8")
    (tmp_path / "sti.json").write_text("{}", encoding="utf-8")

    docs, errors = read_documents(tmp_path, faculty="sti")

    assert [name for name, _ in docs] == ["sti.json"]
    assert errors == []
