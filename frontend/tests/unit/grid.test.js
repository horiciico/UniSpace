import { beforeEach, describe, expect, it, vi } from "vitest";
import { loadI18n, loadScript } from "../helpers.js";

// One Monday activity with the fields grid.js reads; tests override what they need.
function item(overrides = {}) {
  return {
    id: "a1",
    title: "Algebra",
    activity_type: "COURSE",
    day_of_week: 1,
    start_time: "09:40",
    end_time: "11:10",
    room_name: "Sala 107",
    ...overrides,
  };
}

function blocks(container) {
  return [...container.querySelectorAll(".tt-block")];
}

// The number inside a calc(...) value, e.g. "calc(12.5% + 1px)" -> 12.5.
function pct(value) {
  return Number(/calc\((-?[\d.]+)%/.exec(value)[1]);
}

describe("grid.js: the weekly timetable grid", () => {
  let grid;
  let container;

  beforeEach(async () => {
    vi.resetModules();
    await loadI18n("en");
    await loadScript("js/modules.js");
    await loadScript("js/grid.js");
    grid = window.UniSpaceGrid;
    container = document.createElement("div");
    container.className = "tt-grid";
    document.body.appendChild(container);
  });

  it("draws the corner, seven day headers and the eight module ranges", () => {
    grid.render(container, [], undefined);
    expect(container.querySelector(".tt-corner").textContent).toBe("Time");
    const heads = [...container.querySelectorAll(".tt-head")].map(
      (h) => h.textContent,
    );
    expect(heads).toEqual(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]);
    const times = [...container.querySelectorAll(".tt-time")];
    expect(times).toHaveLength(8);
    expect(times[0].textContent).toBe("08:00–09:30");
    expect(times[7].textContent).toBe("19:40–21:10");
    expect(times[0].style.gridRow).toBe("2 / span 9");
    expect(times[1].style.gridRow).toBe("12 / span 9");
  });

  it("draws one column per day, from row 2 to the end of the 79 slots", () => {
    grid.render(container, [], undefined);
    const days = [...container.querySelectorAll(".tt-day")];
    expect(days).toHaveLength(7);
    expect(days[0].style.gridColumn).toBe("2");
    expect(days[6].style.gridColumn).toBe("8");
    expect(days[0].style.gridRow).toBe("2 / 81");
  });

  it("places a block at its start and height, in the full width of its day", () => {
    grid.render(container, [item()], undefined);
    const [block] = blocks(container);
    expect(block.className).toBe("tt-block tt-block--course");
    expect(pct(block.style.top)).toBeCloseTo((100 / 790) * 100, 2); // the browser rounds to 4 decimals
    expect(block.style.top.endsWith("% + 1px)")).toBe(true);
    expect(pct(block.style.height)).toBeCloseTo((90 / 790) * 100, 2);
    expect(block.style.height.endsWith("% - 2px)")).toBe(true);
    expect(block.style.left).toBe("calc(0% + 2px)");
    expect(block.style.width).toBe("calc(100% - 4px)");
  });

  it("shows the kind, room and times on each block, and records the kind", () => {
    grid.render(container, [item()], undefined);
    const [block] = blocks(container);
    expect(block.dataset.kind).toBe("COURSE");
    expect(block.querySelector("strong").textContent).toBe("Algebra");
    expect(block.querySelectorAll("span")[0].textContent).toBe(
      "Course · Sala 107",
    );
    expect(block.querySelectorAll("span")[1].textContent).toBe("09:40–11:10");
  });

  it("uses a neutral class and the raw type for an activity kind it does not know", () => {
    grid.render(container, [item({ activity_type: "WORKSHOP" })], undefined);
    const [block] = blocks(container);
    expect(block.className).toBe("tt-block tt-block--other");
    expect(block.querySelectorAll("span")[0].textContent).toBe(
      "WORKSHOP · Sala 107",
    );
  });

  it("gives the known kinds their own class and label", () => {
    grid.render(
      container,
      [
        item({
          id: "s",
          activity_type: "SEMINAR",
          day_of_week: 2,
          start_time: "08:00",
          end_time: "09:30",
        }),
        item({
          id: "l",
          activity_type: "LAB",
          day_of_week: 3,
          start_time: "08:00",
          end_time: "09:30",
        }),
        item({
          id: "e",
          activity_type: "EXAM",
          day_of_week: 4,
          start_time: "08:00",
          end_time: "09:30",
        }),
        item({
          id: "r",
          activity_type: "RESERVATION",
          day_of_week: 5,
          start_time: "08:00",
          end_time: "09:30",
        }),
      ],
      undefined,
    );
    const drawn = blocks(container);
    expect(drawn.map((b) => b.className)).toEqual([
      "tt-block tt-block--seminar",
      "tt-block tt-block--lab",
      "tt-block tt-block--other",
      "tt-block tt-block--other",
    ]);
    expect(drawn[2].querySelectorAll("span")[0].textContent).toBe(
      "Exam · Sala 107",
    );
    expect(drawn[3].querySelectorAll("span")[0].textContent).toBe(
      "Reservation · Sala 107",
    );
  });

  it("places overlapping activities side by side, sharing the width", () => {
    grid.render(
      container,
      [
        item({ id: "a", start_time: "10:00", end_time: "11:00" }),
        item({ id: "b", start_time: "10:30", end_time: "12:00" }),
      ],
      undefined,
    );
    const [first, second] = blocks(container);
    expect(first.style.left).toBe("calc(0% + 2px)");
    expect(first.style.width).toBe("calc(50% - 4px)");
    expect(second.style.left).toBe("calc(50% + 2px)");
    expect(second.style.width).toBe("calc(50% - 4px)");
  });

  it("puts the shorter of two activities that start together in the first lane", () => {
    grid.render(
      container,
      [
        item({ id: "long", start_time: "10:00", end_time: "11:10" }),
        item({ id: "short", start_time: "10:00", end_time: "10:30" }),
      ],
      undefined,
    );
    const [short, long] = blocks(container);
    expect(short.style.left).toBe("calc(0% + 2px)");
    expect(long.style.left).toBe("calc(50% + 2px)");
  });

  it("reuses a lane once it is free again, within one cluster", () => {
    // a (08:00-09:30) and b (09:00-10:00) overlap; c (09:40-11:10) starts after a ends, so
    // it takes a's lane. The cluster has two lanes.
    grid.render(
      container,
      [
        item({ id: "a", start_time: "08:00", end_time: "09:30" }),
        item({ id: "b", start_time: "09:00", end_time: "10:00" }),
        item({ id: "c", start_time: "09:40", end_time: "11:10" }),
      ],
      undefined,
    );
    const [a, b, c] = blocks(container);
    expect(a.style.width).toBe("calc(50% - 4px)");
    expect(b.style.width).toBe("calc(50% - 4px)");
    expect(c.style.left).toBe("calc(0% + 2px)");
    expect(c.style.width).toBe("calc(50% - 4px)");
  });

  it("starts a new cluster for activities that do not overlap the previous ones", () => {
    grid.render(
      container,
      [
        item({ id: "a", start_time: "08:00", end_time: "09:30" }),
        item({ id: "b", start_time: "09:40", end_time: "11:10" }),
      ],
      undefined,
    );
    const [a, b] = blocks(container);
    expect(a.style.width).toBe("calc(100% - 4px)");
    expect(b.style.width).toBe("calc(100% - 4px)");
  });

  it("clips times to the grid (08:00 to 21:10)", () => {
    grid.render(
      container,
      [item({ start_time: "07:00", end_time: "23:00" })],
      undefined,
    );
    const [block] = blocks(container);
    expect(block.style.top).toBe("calc(0% + 1px)");
    expect(block.style.height).toBe("calc(100% - 2px)");
  });

  it("leaves out an activity that lies entirely outside the grid", () => {
    grid.render(
      container,
      [item({ start_time: "22:00", end_time: "23:00" })],
      undefined,
    );
    expect(blocks(container)).toHaveLength(0);
  });

  it("leaves out an activity with an unknown day, and keeps Sunday (day 7)", () => {
    grid.render(
      container,
      [
        item({ id: "zero", day_of_week: 0 }),
        item({ id: "eight", day_of_week: 8 }),
        item({ id: "sun", day_of_week: 7 }),
      ],
      undefined,
    );
    const drawn = blocks(container);
    expect(drawn).toHaveLength(1);
    expect(drawn[0].closest(".tt-day").style.gridColumn).toBe("8");
  });

  it("draws no blocks for an empty list", () => {
    grid.render(container, [], undefined);
    expect(blocks(container)).toHaveLength(0);
  });

  it("calls onSelect with the activity when its block is clicked", () => {
    const onSelect = vi.fn();
    const activity = item();
    grid.render(container, [activity], onSelect);
    blocks(container)[0].click();
    expect(onSelect).toHaveBeenCalledWith(activity);
  });

  it("does not fail when a block is clicked and no onSelect was given", () => {
    grid.render(container, [item()], undefined);
    expect(() => blocks(container)[0].click()).not.toThrow();
  });

  it("replaces the previous drawing when it is drawn again", () => {
    grid.render(
      container,
      [item(), item({ id: "b", day_of_week: 2 })],
      undefined,
    );
    grid.render(container, [item()], undefined);
    expect(blocks(container)).toHaveLength(1);
    expect(container.querySelectorAll(".tt-day")).toHaveLength(7);
  });

  it("converts HH:MM to minutes", () => {
    expect(grid.toMinutes("09:40")).toBe(580);
    expect(grid.toMinutes("00:05")).toBe(5);
  });
});
