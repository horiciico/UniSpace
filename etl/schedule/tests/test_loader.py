"""Loader rules on single schedule entries. Pure: no network, no database."""
from datetime import time

import pytest

from app.models import ActivityType, Parity, Priority
from etl.loader import (
    DIDACTIC_ACTIVITY_NAME,
    NotStored,
    RoomInfo,
    Unparsed,
    activity_values,
    external_id_for,
    group_blocks,
    merge_contiguous,
    parse_item,
    rooms_from_pages,
)


def entry(**overrides) -> dict:
    base = {
        "id": 1,
        "roomId": "room-1",
        "room": "S01",
        "roomFacultyId": "sti",
        "day": "Monday",
        "parity": 0,
        "activityType": {"name": "Curs"},
        "timeSlots": [{"startTime": "08:00", "endTime": "10:00"}],
        "studyFormation": {"id": 7, "name": "INFO_AN1"},
        "subject": "Algebra",
        "professor": "Popescu Ana",
    }
    base.update(overrides)
    return base


def test_day_names_map_to_iso_numbers() -> None:
    assert parse_item(entry(day="Monday"))[0].day == 1
    assert parse_item(entry(day="Thursday"))[0].day == 4
    assert parse_item(entry(day="Sunday"))[0].day == 7


@pytest.mark.parametrize("api_value, expected", [(0, Parity.ALL), (1, Parity.ODD), (2, Parity.EVEN)])
def test_parity_follows_the_api_value(api_value: int, expected: Parity) -> None:
    assert parse_item(entry(parity=api_value))[0].parity == expected


@pytest.mark.parametrize("name, expected", [
    ("Curs", ActivityType.COURSE),
    ("Seminar", ActivityType.SEMINAR),
    ("Laborator", ActivityType.LAB),
    ("Proiect", ActivityType.LAB),
    ("Tutorat", ActivityType.SEMINAR),
    ("C+S", ActivityType.COURSE),
])
def test_activity_types_map_by_name(name: str, expected: ActivityType) -> None:
    assert parse_item(entry(activityType={"name": name}))[0].activity_type == expected


def test_entry_without_room_is_not_stored() -> None:
    with pytest.raises(NotStored):
        parse_item(entry(roomId=None))


@pytest.mark.parametrize("room", ["Sala Online", "Online1", "online", "https://meet.google.com/abc-def-ghi"])
def test_online_entries_are_not_stored(room: str) -> None:
    with pytest.raises(NotStored):
        parse_item(entry(room=room))


@pytest.mark.parametrize("overrides, reason", [
    ({"day": "Funday"}, "unknown day"),
    ({"parity": 9}, "unknown parity"),
    ({"activityType": {"name": "Examen"}}, "unknown activity type"),
    ({"timeSlots": []}, "no time slots"),
    ({"timeSlots": [{"startTime": "10:00", "endTime": "08:00"}]}, "ends before it starts"),
    ({"timeSlots": [{"startTime": None, "endTime": None}]}, "time slot has no start or end time"),
])
def test_bad_entries_are_unparsed_with_a_reason(overrides: dict, reason: str) -> None:
    with pytest.raises(Unparsed, match=reason):
        parse_item(entry(**overrides))


def test_touching_slots_merge_and_gaps_stay_open() -> None:
    touching = [(time(8, 0), time(10, 0)), (time(10, 0), time(12, 0))]
    assert merge_contiguous(touching) == [(time(8, 0), time(12, 0))]

    gap = [(time(8, 0), time(10, 0)), (time(13, 0), time(14, 0))]
    assert merge_contiguous(gap) == gap


def test_multi_slot_entry_gives_one_block_per_contiguous_run() -> None:
    blocks = parse_item(entry(timeSlots=[
        {"startTime": "08:00", "endTime": "10:00"},
        {"startTime": "10:00", "endTime": "11:00"},
        {"startTime": "14:00", "endTime": "15:00"},
    ]))
    assert [(b.start, b.end) for b in blocks] == [(time(8, 0), time(11, 0)), (time(14, 0), time(15, 0))]


def test_same_room_day_parity_and_times_make_one_group() -> None:
    a = parse_item(entry(id=1, studyFormation={"id": 7, "name": "INFO_AN1"}))
    b = parse_item(entry(id=2, studyFormation={"id": 8, "name": "INFO_AN2"}, subject="Analiza"))
    c = parse_item(entry(id=3, parity=1))  # other parity: another row
    groups = group_blocks(a + b + c)
    assert len(groups) == 2
    assert sorted(len(members) for members in groups.values()) == [1, 2]


def test_external_id_is_stable_and_changes_with_the_slot() -> None:
    block = parse_item(entry())[0]
    key = (block.room_id, block.day, block.parity, block.start, block.end)
    assert external_id_for(key) == external_id_for(key)
    assert len(external_id_for(key)) == 40

    later = (block.room_id, block.day, block.parity, time(10, 0), time(12, 0))
    assert external_id_for(key) != external_id_for(later)


def test_merged_row_is_a_didactic_activity_of_priority_five() -> None:
    members = parse_item(entry(id=1, activityType={"name": "Laborator"})) + parse_item(
        entry(id=2, activityType={"name": "Curs"}, professor="Ionescu Ion", studyFormation={"id": 8, "name": "B"})
    )
    values = activity_values(members)
    assert values["name"] == DIDACTIC_ACTIVITY_NAME
    assert values["priority"] == Priority.COURSE == 5
    assert values["type"] == ActivityType.COURSE  # course beats lab in a merged row
    assert values["professor_name"] == "Ionescu Ion / Popescu Ana"


def test_rooms_without_capacity_store_none() -> None:
    rooms = rooms_from_pages([[
        {"id": "a", "name": "Sala A", "capacity": 30, "faculty": "sti"},
        {"id": "b", "name": "Sala B", "capacity": None, "faculty": None},
        {"id": "c", "name": "Sala C", "capacity": 0, "faculty": "ing"},
    ]])
    assert rooms["a"] == RoomInfo("Sala A", 30, "sti")
    assert rooms["b"] == RoomInfo("Sala B", None, None)
    assert rooms["c"].capacity is None


def test_entry_without_study_group_is_stored_unlinked() -> None:
    block = parse_item(entry(studyFormation=None))[0]
    assert block.group_id is None
    values = activity_values([block])
    assert values["group_api_id"] is None
    assert values["group_name"] == ""


def test_group_is_taken_from_a_member_that_has_one() -> None:
    unlinked = parse_item(entry(id=1, studyFormation=None))
    linked = parse_item(entry(id=2, studyFormation={"id": 9, "name": "GR9"}))
    values = activity_values(unlinked + linked)
    assert values["group_api_id"] == 9
    assert values["group_name"] == "GR9"


def test_merged_row_keeps_every_group_of_the_slot() -> None:
    members = parse_item(entry(id=1, studyFormation={"id": 9, "name": "GR9"})) + parse_item(
        entry(id=2, studyFormation={"id": 8, "name": "B"})
    )
    values = activity_values(members)
    assert values["groups"] == {9: "GR9", 8: "B"}
    assert values["group_api_id"] == 8  # the row keeps the lowest id, as before


def test_optional_type_is_stored_as_course() -> None:
    assert parse_item(entry(activityType={"name": "Optional"}))[0].activity_type == ActivityType.COURSE


def test_missing_type_is_stored_as_course_and_flagged() -> None:
    block = parse_item(entry(activityType=None))[0]
    assert block.activity_type == ActivityType.COURSE
    assert block.type_missing is True
    assert parse_item(entry())[0].type_missing is False
