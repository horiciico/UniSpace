import { beforeEach, describe, expect, it, vi } from "vitest";
import { loadI18n, loadScript } from "../helpers.js";

// The exam-session grid (D-027): hourly rows from 08:00 to 22:00, drawn by grid.js. Times inside a row can be half hours (D-030).
describe("grid.js: the hourly grid", () => {
  let grid;
  let container;

  beforeEach(async () => {
    vi.resetModules();
    document.body.innerHTML = '<div id="g"></div>';
    container = document.getElementById("g");
    await loadI18n("en");
    await loadScript("js/modules.js");
    await loadScript("js/grid.js");
    grid = window.UniSpaceGrid;
  });

  const item = (start, end) => ({
    day_of_week: 1,
    start_time: start,
    end_time: end,
    activity_type: "EXAM",
    title: "Algebra",
    room_name: "B110",
  });

  it("draws one time label per hour, 14 in all", () => {
    grid.render(container, [], undefined, [], { hourly: true });

    const labels = [...container.querySelectorAll(".tt-time")];
    expect(labels).toHaveLength(14);
    expect(labels[0].textContent).toBe("08:00–09:00");
    expect(labels[13].textContent).toBe("21:00–22:00");
    expect(labels[1].style.gridRow).toBe("8 / span 6");
    expect(container.classList.contains("tt-grid--hourly")).toBe(true);
    expect(container.querySelector(".tt-day").style.gridRow).toBe("2 / 86");
  });

  it("keeps the module grid when the option is not given", () => {
    grid.render(container, []);

    expect(container.querySelectorAll(".tt-time")).toHaveLength(8);
    expect(container.classList.contains("tt-grid--hourly")).toBe(false);
    expect(container.querySelector(".tt-day").style.gridRow).toBe("2 / 81");
  });

  it("clears the hourly class when a module grid is drawn again", () => {
    grid.render(container, [], undefined, [], { hourly: true });
    grid.render(container, [], undefined, [], { hourly: false });

    expect(container.classList.contains("tt-grid--hourly")).toBe(false);
  });

  it("places a block by its share of the 14 hours", () => {
    grid.render(
      container,
      [item("10:00", "13:00"), item("21:00", "22:00")],
      undefined,
      [],
      { hourly: true },
    );

    const [first, late] = container.querySelectorAll(".tt-block");
    // 10:00 is 120 of 840 minutes from 08:00: 14.28%
    expect(first.style.top).toContain("14.28");
    expect(late.style.top).toContain("92.85");
    expect(late.style.height).toContain("7.14");
  });

  it("places a half-hour exam inside the hourly rows", () => {
    grid.render(container, [item("08:30", "10:00")], undefined, [], {
      hourly: true,
    });

    const block = container.querySelector(".tt-block");
    // 30 of 840 minutes down, 90 minutes tall.
    expect(block.style.top).toContain("3.57");
    expect(block.style.height).toContain("10.71");
  });

  it("cuts a block at 22:00 in the hourly grid and leaves it out of the module grid", () => {
    const night = item("21:30", "22:30");

    grid.render(container, [night], undefined, [], { hourly: true });
    expect(container.querySelectorAll(".tt-block")).toHaveLength(1);

    grid.render(container, [night]);
    expect(container.querySelectorAll(".tt-block")).toHaveLength(0);
  });

  it("places a free hour as a button", () => {
    const clicked = vi.fn();
    grid.render(
      container,
      [],
      undefined,
      [
        {
          day_of_week: 2,
          startMin: 600,
          endMin: 660,
          label: "Book",
          ariaLabel: "Book 10:00–11:00",
          onClick: clicked,
        },
      ],
      { hourly: true },
    );

    const button = container.querySelector(".tt-free");
    button.click();
    expect(clicked).toHaveBeenCalled();
    expect(button.style.top).toContain("14.28");
  });
});
