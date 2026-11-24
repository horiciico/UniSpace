import { beforeEach, describe, expect, it, vi } from "vitest";
import { flush, loadI18n, loadScript, mountPage, response, stubFetch } from "../helpers.js";

// Monday 23 November 2026 at 10:00. An approved room booking on Monday 13:00-14:30 shows as a block.
const NOW = new Date(2026, 10, 23, 10, 0);

const FACULTIES = [{ id: "f1", code: "dre", name: "Facultatea de Drept" }];
const CLASSROOMS = [{ id: "r1", name: "Sala 107", faculty_id: "f1", capacity: 30, is_bookable: true, is_field_verified: true }];
const SCHEDULE = {
  week_start: "2026-11-23", week_end: "2026-11-29", week_number: 9, parity: "ODD",
  entity_type: "room", entity_label: "Sala 107", items: [
    {
      id: "bk1", title: "Seara jocurilor", activity_type: "BOOKING", priority: null, day_of_week: 1,
      date: "2026-11-23", start_time: "13:00", end_time: "14:30", parity: "ALL", room_id: "r1",
      room_name: "Sala 107", professor: null, groups: [], is_recurring: false
    }
  ]
};

async function setup() {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  window.history.replaceState(null, "", "/timetable?mode=room&faculty_id=f1&id=r1&date=2026-11-23");
  mountPage("pages/student/timetable.html");
  await loadI18n("en");
  await loadScript("js/modules.js");
  await loadScript("js/api.js");
  await loadScript("js/grid.js");
  await loadScript("js/bookings.js");
  stubFetch({
    "/api/faculties": () => response(FACULTIES),
    "/api/classrooms": () => response(CLASSROOMS),
    "/api/schedule": () => response(SCHEDULE)
  });
  await loadScript("js/pages/timetable.js");
  await flush();
  await flush();
}

describe("timetable.js: approved bookings in the room view", () => {
  beforeEach(() => vi.resetModules());

  it("draws an approved booking as a block labelled Booking, with no booking action over it", async () => {
    await setup();

    const block = document.querySelector(".tt-block--booking");
    expect(block).not.toBeNull();
    expect(block.textContent).toContain("Seara jocurilor");
    expect(block.textContent).toContain("Booking · Sala 107");
    const freeOver = [...document.querySelectorAll(".tt-free")].filter((b) => b.getAttribute("aria-label")?.startsWith("Book 13:00–14:30, Mon"));
    expect(freeOver).toHaveLength(0);
  });

  it("opens the details of a booking without a priority", async () => {
    await setup();

    document.querySelector(".tt-block--booking").click();

    expect(document.getElementById("tt-d-kind").textContent).toBe("Booking");
    expect(document.getElementById("tt-d-priority").textContent).toBe("Not specified");
    expect(document.getElementById("tt-d-recurring").textContent).toBe("One-off event");
  });
});
