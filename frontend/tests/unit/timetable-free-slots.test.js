import { beforeEach, describe, expect, it, vi } from "vitest";
import { flush, loadI18n, loadScript, mountPage, response, stubFetch } from "../helpers.js";

// Monday 23 November 2026 at 10:00, the week shown. The Monday 08:00 module has started, so it is
// shown but disabled.
const NOW = new Date(2026, 10, 23, 10, 0);

const FACULTIES = [{ id: "f1", code: "dre", name: "Facultatea de Drept" }];
const SCHEDULE = {
  week_start: "2026-11-23", week_end: "2026-11-29", week_number: 9, parity: "ODD",
  entity_type: "room", entity_label: "Sala 107", items: [
    {
      id: "i1", title: "Algebra", activity_type: "COURSE", priority: 5, day_of_week: 1, date: "2026-11-23",
      start_time: "09:40", end_time: "11:10", parity: "ODD", room_id: "r1", room_name: "Sala 107",
      professor: null, groups: [], is_recurring: true
    }
  ]
};

function rooms(bookable) {
  return [{ id: "r1", name: "Sala 107", faculty_id: "f1", capacity: 30, is_bookable: bookable, is_field_verified: true }];
}

// Mounts the timetable on the room view of room r1 and waits for its week.
async function setup({ bookable = true } = {}) {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  window.history.replaceState(null, "", "/timetable?mode=room&faculty_id=f1&id=r1&date=2026-11-23");
  mountPage("pages/student/timetable.html");
  await loadI18n("en");
  await loadScript("js/modules.js");
  await loadScript("js/api.js");
  await loadScript("js/grid.js");
  await loadScript("js/bookings.js");
  const fetch = stubFetch({
    "/api/faculties": () => response(FACULTIES),
    "/api/classrooms": () => response(rooms(bookable)),
    "/api/schedule": () => response(SCHEDULE)
  });
  await loadScript("js/pages/timetable.js");
  await flush();
  await flush();
  return { fetch };
}

const freeButtons = () => [...document.querySelectorAll(".tt-free")];

describe("timetable.js: free modules of a bookable room", () => {
  beforeEach(() => vi.resetModules());

  it("offers each free module of the week, and no module where a class runs", async () => {
    await setup();

    // 7 days x 8 modules, less the one Monday module that the course takes (09:40-11:10).
    expect(freeButtons()).toHaveLength(7 * 8 - 1);
    const labels = freeButtons().map((b) => b.textContent);
    expect(labels.filter((label) => label === "Book 09:40–11:10")).toHaveLength(6);
  });

  it("disables the modules that have already started today", async () => {
    await setup();

    const disabled = freeButtons().filter((b) => b.disabled);
    expect(disabled.map((b) => b.textContent)).toEqual(["Past"]);
  });

  it("opens the Bookings page for the room and the module that was clicked", async () => {
    await setup();
    const original = window.location;
    const assign = vi.fn();
    Object.defineProperty(window, "location", { configurable: true, value: { ...original, assign } });
    try {
      const wednesdayModule = freeButtons().find((b) => b.getAttribute("aria-label") === "Book 11:20–12:50, Wed");
      wednesdayModule.click();
      expect(assign).toHaveBeenCalledWith("/bookings/?faculty_id=f1&room=r1&date=2026-11-25&start=11%3A20&end=12%3A50");
    } finally {
      Object.defineProperty(window, "location", { configurable: true, value: original });
    }
  });

  it("offers no booking action for a room that cannot be booked", async () => {
    await setup({ bookable: false });

    expect(freeButtons()).toHaveLength(0);
    expect(document.querySelectorAll(".tt-block")).toHaveLength(1);
  });
});
