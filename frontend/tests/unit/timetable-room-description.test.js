import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  flush,
  loadI18n,
  loadScript,
  mountPage,
  response,
  stubFetch,
} from "../helpers.js";

// The room description above the timetable (Liber acum opens the room view with a room id in the URL).
const NOW = new Date(2026, 10, 23, 10, 0);

const FACULTIES = [{ id: "f1", code: "dre", name: "Facultatea de Drept" }];
const CLASSROOMS = [
  {
    id: "r1",
    name: "Sala 107",
    faculty_id: "f1",
    capacity: 30,
    is_bookable: true,
    is_field_verified: true,
    access_notes: "Cheia la portar, parterul",
  },
  {
    id: "r2",
    name: "Lab 2",
    faculty_id: "f1",
    capacity: 20,
    is_bookable: true,
    is_field_verified: false,
    access_notes: null,
  },
];
const GROUPS = [{ id: "g1", name: "Grupa 1", faculty_id: "f1" }];
const ROOM_SCHEDULE = {
  week_start: "2026-11-23",
  week_end: "2026-11-29",
  week_number: 9,
  parity: "ODD",
  entity_type: "room",
  entity_label: "Sala 107",
  items: [],
};
const GROUP_SCHEDULE = {
  week_start: "2026-11-23",
  week_end: "2026-11-29",
  week_number: 9,
  parity: "ODD",
  entity_type: "group",
  entity_label: "Grupa 1",
  items: [],
};

async function setup(search) {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  window.history.replaceState(null, "", `/timetable?${search}`);
  mountPage("pages/student/timetable.html");
  await loadI18n("en");
  await loadScript("js/modules.js");
  await loadScript("js/api.js");
  await loadScript("js/grid.js");
  await loadScript("js/bookings.js");
  stubFetch({
    "/api/faculties": () => response(FACULTIES),
    "/api/classrooms": () => response(CLASSROOMS),
    "/api/groups": () => response(GROUPS),
    "/api/schedule": (url) =>
      response(
        new URL(url, "http://x").searchParams.has("room_id")
          ? ROOM_SCHEDULE
          : GROUP_SCHEDULE,
      ),
  });
  await loadScript("js/pages/timetable.js");
  await flush();
  await flush();
}

const $ = (id) => document.getElementById(id);

describe("timetable.js: the room description above the timetable", () => {
  beforeEach(() => vi.resetModules());

  it("shows the access notes of the room, above the grid and inside the timetable", async () => {
    await setup("mode=room&faculty_id=f1&id=r1&date=2026-11-23");

    const room = $("tt-room");
    expect(room.hidden).toBe(false);
    expect($("tt-room-access").textContent).toBe("Cheia la portar, parterul");
    expect($("tt-body").contains(room)).toBe(true);
    expect(
      room.compareDocumentPosition($("tt-grid")) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("says unspecified when the room has no access notes", async () => {
    await setup("mode=room&faculty_id=f1&id=r2&date=2026-11-23");

    expect($("tt-room").hidden).toBe(false);
    expect($("tt-room-access").textContent).toBe("Unspecified");
  });

  it("is hidden for a group timetable", async () => {
    await setup("mode=group&faculty_id=f1&id=g1&date=2026-11-23");

    expect($("tt-body").hidden).toBe(false);
    expect($("tt-room").hidden).toBe(true);
  });
});
