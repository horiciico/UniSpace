"""Professors load rules on documents already read from disk. Pure: no network, no database."""
from etl.professors.load import MergeResult, merge_records

UUID_A = "3601532c-3e19-4edf-a41f-d1b996f6487b"  # the smaller id
UUID_B = "99cc2327-bf8e-439a-8d33-c0f9bb2ddb37"


def record(id: str, name: str = "Popescu Ana", email: str = "ana@ulbsibiu.ro") -> dict:
    return {"id": id, "name": name, "email": email}


def test_the_same_professor_under_two_faculties_is_kept_once() -> None:
    docs = [
        ("ing.json", {"professors": [record(UUID_A), record(UUID_B, email="b@ulbsibiu.ro")]}),
        ("sti.json", {"professors": [record(UUID_A)]}),
    ]
    result = merge_records(docs)
    assert [r["id"] for r in result.records] == sorted([UUID_A, UUID_B])
    assert result.repeated_ids == 1
    assert result.dropped == []


def test_the_first_occurrence_wins_when_the_same_id_differs() -> None:
    docs = [
        ("ing.json", {"professors": [record(UUID_A, name="Old name")]}),
        ("sti.json", {"professors": [record(UUID_A, name="New name")]}),
    ]
    result = merge_records(docs)
    assert result.records == [record(UUID_A, name="Old name")]
    assert result.repeated_ids == 1


def test_records_come_out_sorted_by_id() -> None:
    docs = [("ing.json", {"professors": [record(UUID_B, email="b@x.ro"), record(UUID_A)]})]
    assert [r["id"] for r in merge_records(docs).records] == sorted([UUID_A, UUID_B])


def test_no_documents_gives_nothing() -> None:
    assert merge_records([]) == MergeResult([], 0, [])


def test_two_ids_with_one_email_keep_the_smallest_id_and_report_the_other() -> None:
    docs = [("ing.json", {"professors": [record(UUID_B), record(UUID_A)]})]
    result = merge_records(docs)
    assert result.records == [record(UUID_A)]
    assert result.dropped == [(UUID_B, UUID_A)]


def test_an_id_used_by_an_activity_is_preferred_over_a_smaller_id() -> None:
    docs = [("ing.json", {"professors": [record(UUID_A), record(UUID_B)]})]
    result = merge_records(docs, used={UUID_B})
    assert result.records == [record(UUID_B)]
    assert result.dropped == [(UUID_A, UUID_B)]


def test_the_id_already_stored_for_the_email_is_kept_first() -> None:
    docs = [("ing.json", {"professors": [record(UUID_A), record(UUID_B)]})]
    result = merge_records(docs, stored={"ana@ulbsibiu.ro": UUID_B}, used={UUID_A})
    assert result.records == [record(UUID_B)]
    assert result.dropped == [(UUID_A, UUID_B)]


def test_emails_are_compared_after_normalization() -> None:
    docs = [("ing.json", {"professors": [record(UUID_A, email="Ana@ULBSibiu.ro "), record(UUID_B)]})]
    result = merge_records(docs)
    assert result.records == [record(UUID_A)]
    assert result.dropped == [(UUID_B, UUID_A)]
