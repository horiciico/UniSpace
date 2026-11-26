import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  deferred,
  flush,
  loadI18n,
  loadScript,
  mountPage,
  response,
  stubFetch,
} from "../helpers.js";

// The timetable follows the academic calendar (D-027, C-010): an exam-session week is drawn by the
// hour with a banner, a holiday week has a banner and no booking links, and the "Sesiune" chip
// jumps to the first week of the next exam session. Today is Monday 23 November 2026, 10:00.
const NOW = new Date(2026, 10, 23, 10, 0);

const PERIODS = [
  {
    id: "p1",
    name: "Sesiune",
    type: "EXAM_SESSION",
    start_date: "2026-12-10",
    end_date: "2026-12-18",
  },
  {
    id: "p2",
    name: "Vacanta",
    type: "HOLIDAY",
    start_date: "2026-12-20",
    end_date: "2027-01-03",
  },
];
const FACULTIES = [{ id: "f1", code: "dre", name: "Facultatea de Drept" }];
const CLASSROOMS = [
  { id: "r1", name: "Sala 107", faculty_id: "f1", is_bookable: true },
];

function schedule(date) {
  return {
    week_start: date,
    week_end: date,
    week_number: 3,
    parity: "ODD",
    entity_type: "room",
    entity_label: "Sala 107",
    items: [],
  };
}

async function setup({
  date = "2026-12-14",
  periods = () => response(PERIODS),
  entity = true,
  language = "en",
} = {}) {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  const id = entity ? "&id=r1" : "";
  window.history.replaceState(
    null,
    "",
    "/timetable?mode=room&faculty_id=f1" + id + "&date=" + date,
  );
  mountPage("pages/student/timetable.html");
  await loadI18n(language);
  window.UniSpaceI18n.setLanguage(language);
  window.UniSpaceI18n.apply(document.body);
  await loadScript("js/modules.js");
  await loadScript("js/api.js");
  await loadScript("js/grid.js");
  await loadScript("js/bookings.js");
  const fetch = stubFetch({
    "/api/faculties": () => response(FACULTIES),
    "/api/classrooms": () => response(CLASSROOMS),
    "/api/schedule": (url) =>
      response(schedule(new URL(url, "http://x").searchParams.get("date"))),
    "/api/academic-periods": periods,
  });
  await loadScript("js/pages/timetable.js");
  await flush();
  await flush();
  return { fetch };
}

const $ = (id) => document.getElementById(id);
const hourLabels = () => document.querySelectorAll("#tt-grid .tt-time");
const freeSlots = () => document.querySelectorAll("#tt-grid .tt-free");

describe("timetable.js: the academic calendar", () => {
  beforeEach(() => vi.resetModules());

  it("draws an exam-session week by the hour, with its banner", async () => {
    await setup({ date: "2026-12-14" });

    expect($("tt-period").hidden).toBe(false);
    expect($("tt-period-pill").textContent).toBe("Exam session");
    expect($("tt-period-pill").className).toBe("pill pill--pending");
    expect($("tt-period-text").textContent).toContain("08:00 to 22:00");
    expect(hourLabels()).toHaveLength(14);
    expect($("tt-grid").classList.contains("tt-grid--hourly")).toBe(true);
  });

  it("offers every free hour of an exam-session week, but not on a holiday day", async () => {
    await setup({ date: "2026-12-14" });

    // Monday to Saturday: 6 days of 14 hours. Sunday 20 December is a holiday.
    expect(freeSlots()).toHaveLength(6 * 14);
    const first = freeSlots()[0];
    expect(first.getAttribute("aria-label")).toBe("Book 08:00–09:00, Mon");
  });

  it("links a free hour to the booking page with the hour as the window", async () => {
    await setup({ date: "2026-12-14" });
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });

    freeSlots()[0].click();

    expect(assign).toHaveBeenCalledWith(
      expect.stringContaining("date=2026-12-14&start=08%3A00&end=09%3A00"),
    );
  });

  it("shows the holiday banner, keeps the modules and offers no booking", async () => {
    await setup({ date: "2026-12-21" });

    expect($("tt-period").hidden).toBe(false);
    expect($("tt-period-pill").textContent).toBe("Holiday");
    expect($("tt-period-pill").className).toBe("pill pill--busy");
    expect($("tt-period-text").textContent).toContain("closed");
    expect(hourLabels()).toHaveLength(8);
    expect(freeSlots()).toHaveLength(0);
  });

  it("shows no banner and the modules in a teaching week", async () => {
    await setup({ date: "2026-11-30" });

    expect($("tt-period").hidden).toBe(true);
    expect(hourLabels()).toHaveLength(8);
    expect(freeSlots()).toHaveLength(7 * 8);
  });

  it("shows the hourly grid for a week that only starts the session", async () => {
    await setup({ date: "2026-12-07" });

    expect(hourLabels()).toHaveLength(14);
    expect($("tt-period-pill").textContent).toBe("Exam session");
  });

  it("translates the banner and the chip when the language changes", async () => {
    await setup({ date: "2026-12-14" });

    window.UniSpaceI18n.setLanguage("ro");
    await flush();

    expect($("tt-period-pill").textContent).toBe("Sesiune de examene");
    expect($("tt-period-text").textContent).toContain("08:00 și 22:00");
  });

  it("shows the Sesiune chip while an exam session is current or coming", async () => {
    await setup({ date: "2026-11-23" });

    expect($("tt-exam").hidden).toBe(false);
    expect($("tt-exam").textContent).toBe("Exam session");
  });

  it("jumps to the first week of the exam session", async () => {
    const { fetch } = await setup({ date: "2026-11-23" });

    $("tt-exam").click();
    await flush();

    // The session starts on Thursday 10 December; its week starts on Monday 7 December.
    expect(window.location.search).toContain("date=2026-12-07");
    const last = fetch.mock.calls
      .filter((c) => String(c[0]).includes("/api/schedule"))
      .at(-1);
    expect(String(last[0])).toContain("date=2026-12-07");
    expect(hourLabels()).toHaveLength(14);
  });

  it("hides the chip when no exam session is left", async () => {
    await setup({
      date: "2026-11-23",
      periods: () => response([PERIODS[1]]),
    });
    expect($("tt-exam").hidden).toBe(true);
  });

  it("hides the chip after the last session has ended", async () => {
    await setup({
      date: "2026-11-23",
      periods: () =>
        response([
          {
            ...PERIODS[0],
            start_date: "2026-06-01",
            end_date: "2026-06-30",
          },
        ]),
    });
    expect($("tt-exam").hidden).toBe(true);
  });

  it("treats every week as a teaching week when the periods cannot be loaded", async () => {
    await setup({
      date: "2026-12-14",
      periods: () => response({ detail: "boom" }, 500),
    });

    expect($("tt-period").hidden).toBe(true);
    expect($("tt-exam").hidden).toBe(true);
    expect(hourLabels()).toHaveLength(8);
  });

  it("draws the grid again when the periods arrive after the schedule", async () => {
    const periods = deferred();
    await setup({ date: "2026-12-14", periods: () => periods.promise });
    expect(hourLabels()).toHaveLength(8);

    periods.resolve(response(PERIODS));
    await flush();
    await flush();

    expect(hourLabels()).toHaveLength(14);
    expect($("tt-period").hidden).toBe(false);
  });

  it("only shows the banner when no timetable is chosen yet", async () => {
    await setup({ date: "2026-12-14", entity: false });

    expect($("tt-period").hidden).toBe(false);
    expect($("tt-body").hidden).toBe(true);
    expect($("tt-exam").hidden).toBe(false);
  });
});
