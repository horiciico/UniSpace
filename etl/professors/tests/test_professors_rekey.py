"""When the API replaces a stored id by a new id for the same email (pure part). No network, no database."""
from etl.professors.load import plan_rekeys

OLD = "3601532c-3e19-4edf-a41f-d1b996f6487b"
NEW = "99cc2327-bf8e-439a-8d33-c0f9bb2ddb37"
EMAIL = "ana@ulbsibiu.ro"


def kept(id: str, email: str = EMAIL) -> dict:
    return {"id": id, "name": "Popescu Ana", "email": email}


def test_a_stored_id_missing_from_every_file_is_replaced_by_the_new_id() -> None:
    assert plan_rekeys([kept(NEW)], {EMAIL: OLD}, seen_ids={NEW}) == [(OLD, NEW)]


def test_a_stored_id_still_in_a_file_is_not_replaced() -> None:
    assert plan_rekeys([kept(NEW)], {EMAIL: OLD}, seen_ids={NEW, OLD}) == []


def test_the_same_id_or_no_stored_row_needs_no_replacement() -> None:
    assert plan_rekeys([kept(OLD)], {EMAIL: OLD}, seen_ids={OLD}) == []
    assert plan_rekeys([kept(NEW)], {}, seen_ids={NEW}) == []
