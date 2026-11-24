import { beforeEach, describe, expect, it, vi } from "vitest";
import { loadI18n, loadScript } from "../helpers.js";

// The free modules of a bookable room, drawn by grid.js as buttons under the activities.
describe("grid.js: free modules of a bookable room", () => {
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

  it("draws each free module as a button in its day column, with its label and name", () => {
    const onClick = vi.fn();
    grid.render(container, [], undefined, [
      { day_of_week: 2, startMin: 600, endMin: 690, label: "Book 10:00–11:30", ariaLabel: "Book 10:00–11:30, Tue", disabled: false, onClick }
    ]);

    const button = container.querySelector(".tt-free");
    expect(button.tagName).toBe("BUTTON");
    expect(button.type).toBe("button");
    expect(button.textContent).toBe("Book 10:00–11:30");
    expect(button.getAttribute("aria-label")).toBe("Book 10:00–11:30, Tue");
    expect(button.disabled).toBe(false);
    expect(button.parentElement.classList.contains("tt-day")).toBe(true);
    expect(button.parentElement.style.gridColumn).toBe("3");
    expect(button.style.top.startsWith("calc(15.18")).toBe(true);
    button.click();
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("draws a disabled slot that cannot be clicked, and a slot with no name without an aria label", () => {
    const onClick = vi.fn();
    grid.render(container, [], undefined, [
      { day_of_week: 1, startMin: 480, endMin: 570, label: "Past", disabled: true, onClick }
    ]);

    const button = container.querySelector(".tt-free");
    expect(button.disabled).toBe(true);
    expect(button.hasAttribute("aria-label")).toBe(false);
    button.click();
    expect(onClick).not.toHaveBeenCalled();
  });

  it("draws nothing extra when no free slots are given", () => {
    grid.render(container, [], undefined);
    expect(container.querySelectorAll(".tt-free")).toHaveLength(0);
  });
});
