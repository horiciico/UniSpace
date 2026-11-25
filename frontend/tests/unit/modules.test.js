import { beforeEach, describe, expect, it, vi } from "vitest";
import { loadScript } from "../helpers.js";

describe("modules.js: the module schedule", () => {
  beforeEach(async () => {
    vi.resetModules();
    await loadScript("js/modules.js");
  });

  it("lists eight modules of 90 minutes, one every 100 minutes, from 08:00", () => {
    const { list } = window.UniSpaceModules;
    expect(list).toHaveLength(8);
    expect(list.map((m) => m.number)).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
    expect(list[0]).toMatchObject({
      start: "08:00",
      end: "09:30",
      startMin: 480,
      endMin: 570,
    });
    expect(list[1]).toMatchObject({ start: "09:40", end: "11:10" });
    expect(list[7]).toMatchObject({ start: "19:40", end: "21:10" });
  });

  it("ends the booking day with the last module (21:10)", () => {
    expect(window.UniSpaceModules.end).toBe("21:10");
    expect(window.UniSpaceModules.endMin).toBe(21 * 60 + 10);
  });

  it("formats minutes as HH:MM, padding both parts", () => {
    expect(window.UniSpaceModules.clock(0)).toBe("00:00");
    expect(window.UniSpaceModules.clock(9 * 60 + 5)).toBe("09:05");
    expect(window.UniSpaceModules.clock(13 * 60 + 30)).toBe("13:30");
  });
});
