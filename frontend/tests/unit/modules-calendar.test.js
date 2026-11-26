import { beforeEach, describe, expect, it, vi } from "vitest";
import { loadScript } from "../helpers.js";

// The academic calendar helpers in modules.js (D-027): hours, the type of a date and of a week.
const PERIODS = [
  {
    name: "Semestrul 1",
    type: "TEACHING",
    start_date: "2026-10-05",
    end_date: "2026-12-06",
  },
  {
    name: "Sesiune",
    type: "EXAM_SESSION",
    start_date: "2026-12-10",
    end_date: "2026-12-18",
  },
  {
    name: "Vacanta",
    type: "HOLIDAY",
    start_date: "2026-12-20",
    end_date: "2027-01-03",
  },
];

describe("modules.js: the academic calendar helpers", () => {
  let modules;

  beforeEach(async () => {
    vi.resetModules();
    await loadScript("js/modules.js");
    modules = window.UniSpaceModules;
  });

  it("has fourteen whole hours from 08:00 to 22:00", () => {
    expect(modules.hours).toHaveLength(14);
    expect(modules.hours[0]).toMatchObject({
      number: 1,
      startMin: 480,
      endMin: 540,
      start: "08:00",
      end: "09:00",
    });
    expect(modules.hours[13]).toMatchObject({ start: "21:00", end: "22:00" });
    expect(modules.hoursEndMin).toBe(22 * 60);
  });

  it("gives the hours in an exam session and the modules otherwise", () => {
    expect(modules.slotsFor("EXAM_SESSION")).toBe(modules.hours);
    expect(modules.slotsFor("TEACHING")).toBe(modules.list);
    expect(modules.slotsFor("HOLIDAY")).toBe(modules.list);
  });

  it("finds the type of a date, both ends of a period included", () => {
    expect(modules.typeOnDate(PERIODS, "2026-12-10")).toBe("EXAM_SESSION");
    expect(modules.typeOnDate(PERIODS, "2026-12-18")).toBe("EXAM_SESSION");
    expect(modules.typeOnDate(PERIODS, "2026-12-20")).toBe("HOLIDAY");
    expect(modules.typeOnDate(PERIODS, "2026-11-01")).toBe("TEACHING");
  });

  it("is a teaching day when no period covers the date, or there are none", () => {
    expect(modules.typeOnDate(PERIODS, "2026-12-08")).toBe("TEACHING");
    expect(modules.typeOnDate([], "2026-12-14")).toBe("TEACHING");
    expect(modules.typeOnDate(PERIODS, "")).toBe("TEACHING");
  });

  it("draws a week hourly when any day is in an exam session", () => {
    // Monday 7 Dec: Monday to Wednesday teaching, Thursday 10 starts the session.
    const info = modules.weekInfo(PERIODS, "2026-12-07");
    expect(info.type).toBe("EXAM_SESSION");
    expect(info.hourly).toBe(true);
    expect(info.days).toEqual([
      "TEACHING",
      "TEACHING",
      "TEACHING",
      "EXAM_SESSION",
      "EXAM_SESSION",
      "EXAM_SESSION",
      "EXAM_SESSION",
    ]);
  });

  it("is a holiday week when a day is a holiday and none is an exam day", () => {
    const info = modules.weekInfo(PERIODS, "2026-12-21");
    expect(info.type).toBe("HOLIDAY");
    expect(info.hourly).toBe(false);
  });

  it("keeps a plain week as a teaching week", () => {
    expect(modules.weekInfo(PERIODS, "2026-10-12")).toEqual({
      type: "TEACHING",
      hourly: false,
      days: Array(7).fill("TEACHING"),
    });
  });

  it("counts the days across a month and a year end", () => {
    // Monday 28 Dec 2026 to Sunday 3 Jan 2027: all of it is the holiday.
    expect(modules.weekInfo(PERIODS, "2026-12-28").days).toEqual(
      Array(7).fill("HOLIDAY"),
    );
    // The next week starts after the holiday ends on Sunday 3 Jan.
    expect(modules.weekInfo(PERIODS, "2027-01-04").type).toBe("TEACHING");
  });

  it("finds the current or next exam session", () => {
    expect(modules.nextExamSession(PERIODS, "2026-12-01").name).toBe("Sesiune");
    expect(modules.nextExamSession(PERIODS, "2026-12-18").name).toBe("Sesiune");
    expect(modules.nextExamSession(PERIODS, "2026-12-19")).toBeNull();
    expect(modules.nextExamSession([], "2026-12-01")).toBeNull();
  });
});
