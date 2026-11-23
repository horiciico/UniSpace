import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { deferred, flush, loadI18n, loadScript, mountPage, queryOf, response, stubFetch } from "../helpers.js";

// Monday 23 November 2026, 14:35 local: the current module is 14:40-16:10 (module 5).
const NOON_ISH = new Date(2026, 10, 23, 14, 35);

const FACULTIES = [
  { id: "f1", code: "dre", name: "Facultatea de Drept" },
  { id: "f2", code: "ing", name: "Facultatea de Inginerie" }
];

const ROOMS = [
  {
    id: "r1", name: "Sala 101", faculty_id: "f1", faculty_name: "Facultatea de Drept", capacity: 30,
    has_projector: true, has_outlets: true, is_field_verified: true, free_until: "16:20"
  },
  {
    id: "r2", name: "Aula", faculty_id: null, faculty_name: null, capacity: null,
    has_projector: false, has_outlets: false, is_field_verified: false, free_until: "21:10"
  }
];

// Mounts the real free-rooms page, loads its scripts as the browser does, and waits for the
// faculty list. `freeRoute` replaces the free-room answer (for example to hold it back).
async function setup({ at = NOON_ISH, language = "en", freeRoute, faculties = () => response(FACULTIES),
  withoutList = false } = {}) {
  vi.useFakeTimers({ toFake: ["Date", "setInterval", "clearInterval"] });
  vi.setSystemTime(at);
  mountPage("pages/student/rooms/free.html");
  if (withoutList) document.getElementById("free-list").remove();
  await loadI18n(language);
  await loadScript("js/modules.js");
  await loadScript("js/api.js");
  const fetch = stubFetch({
    "/api/faculties": faculties,
    "/api/classrooms/free": freeRoute || (() => response(ROOMS))
  });
  await loadScript("js/pages/free.js");
  await flush();
  return { fetch };
}

const $ = (id) => document.getElementById(id);
const status = () => $("free-status").textContent;
const cards = () => [...document.querySelectorAll(".room-card")];
const freeCalls = (fetch) => fetch.mock.calls.map((c) => c[0]).filter((u) => u.startsWith("/api/classrooms/free"));

// Sets a control's value and fires its change event, as a user would.
function pick(element, value) {
  element.value = value;
  element.dispatchEvent(new Event("change", { bubbles: true }));
}

function tab(mode) {
  document.querySelector(`[data-free-mode="${mode}"]`).click();
}

// Chooses the faculty of the first request; most tests start here.
async function chooseFaculty(id = "f1") {
  pick($("free-faculty"), id);
  await flush();
}

describe("free.js: the free-rooms page", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe("faculty gate and the faculty list", () => {
    it("lists no rooms and asks for a faculty before one is chosen", async () => {
      const { fetch } = await setup();
      expect(status()).toBe("Choose a faculty to see the free rooms.");
      expect(cards()).toHaveLength(0);
      expect(freeCalls(fetch)).toHaveLength(0);
      expect(document.activeElement).toBe($("free-faculty"));
    });

    it("offers a placeholder, Campus, and every faculty", async () => {
      await setup();
      const options = [...$("free-faculty").options].map((o) => [o.value, o.textContent]);
      expect(options).toEqual([
        ["", "Choose a faculty"],
        ["campus", "Campus"],
        ["f1", "Facultatea de Drept"],
        ["f2", "Facultatea de Inginerie"]
      ]);
    });

    it("shows an error when the faculty list cannot be loaded", async () => {
      await setup({ faculties: () => response({ detail: "down" }, 500) });
      expect(status()).toBe("Could not load the rooms. Try again.");
      expect($("free-status").className).toBe("notice notice--error");
    });

    it("keeps the chosen faculty when the list is loaded again (after a language change)", async () => {
      await setup();
      await chooseFaculty("f2");
      window.UniSpaceI18n.setLanguage("ro");
      await flush();
      expect($("free-faculty").value).toBe("f2");
    });
  });

  describe("free now", () => {
    it("asks for the current module with the local date, and says which module it is", async () => {
      const { fetch } = await setup();
      await chooseFaculty("f1");
      expect(queryOf(freeCalls(fetch)[0])).toEqual({
        date: "2026-11-23", start_time: "14:40", end_time: "16:10", faculty_id: "f1"
      });
      expect(status()).toBe("2 free rooms · In module 14:40–16:10");
    });

    it("sends Campus as the campus filter", async () => {
      const { fetch } = await setup();
      await chooseFaculty("campus");
      expect(queryOf(freeCalls(fetch)[0]).faculty_id).toBe("campus");
    });

    it("draws a card per room with its availability, verification, seats and equipment", async () => {
      await setup();
      await chooseFaculty("f1");
      const [first, second] = cards();
      expect(first.querySelector("h2").textContent).toBe("Sala 101");
      expect(first.querySelector(".room-card__faculty").textContent).toBe("Facultatea de Drept");
      const [until, verified] = first.querySelectorAll(".room-card__badges span");
      expect(until.textContent).toBe("Free until 16:20");
      expect(verified.textContent).toBe("Verified on site");
      expect(verified.className).toBe("pill pill--confirmed");
      expect(first.querySelector(".room-card__details").textContent).toBe("30 seats");
      expect([...first.querySelectorAll(".tag")].map((t) => t.textContent)).toEqual(["Projector", "Outlets"]);
      expect(first.getAttribute("aria-label")).toBe("View the timetable of room Sala 101");
      expect(first.getAttribute("href")).toBe("/timetable?mode=room&faculty_id=f1&id=r1&date=2026-11-23");

      expect(second.querySelector("h2").textContent).toBe("Aula");
      expect(second.querySelector(".room-card__faculty").textContent).toBe("Campus");
      const [freeUntil, estimate] = second.querySelectorAll(".room-card__badges span");
      expect(freeUntil.textContent).toBe("Free until 21:10");
      expect(estimate.textContent).toBe("Estimated data");
      expect(estimate.className).toBe("pill pill--pending");
      expect(second.querySelector(".room-card__details").textContent).toBe("Unknown capacity");
      expect(second.querySelector(".tag")).toBeNull();
      expect(second.getAttribute("href")).toBe("/timetable?mode=room&faculty_id=campus&id=r2&date=2026-11-23");
    });

    it("treats a missing capacity field the same as an empty one", async () => {
      const rooms = [{ id: "r3", name: "Lab", faculty_id: "f2", faculty_name: "Inginerie", has_projector: false,
        has_outlets: true, is_field_verified: false, free_until: "21:10" }];
      await setup({ freeRoute: () => response(rooms) });
      await chooseFaculty("f2");
      expect(cards()[0].querySelector(".room-card__details").textContent).toBe("Unknown capacity");
      expect([...cards()[0].querySelectorAll(".tag")].map((t) => t.textContent)).toEqual(["Outlets"]);
    });

    it("says so when no room is free", async () => {
      await setup({ freeRoute: () => response([]) });
      await chooseFaculty("f1");
      expect(cards()).toHaveLength(0);
      expect(status()).toBe("No free room matches these filters. · In module 14:40–16:10");
      expect($("free-status").className).toBe("muted");
    });

    it("shows an error and no rooms when the search fails", async () => {
      await setup({ freeRoute: () => response({ detail: "down" }, 500) });
      await chooseFaculty("f1");
      expect(cards()).toHaveLength(0);
      expect(status()).toBe("Could not load the rooms. Try again.");
      expect($("free-status").className).toBe("notice notice--error");
    });

    it("shows the range message when the server refuses the window", async () => {
      await setup({ freeRoute: () => response({ detail: "bad" }, 400) });
      await chooseFaculty("f1");
      expect(status()).toBe("Choose whole modules: from the start of one module to the end of another.");
    });

    it("says that no room can be booked after the last module, and does not ask", async () => {
      const { fetch } = await setup({ at: new Date(2026, 10, 23, 21, 12) });
      await chooseFaculty("f1");
      expect(freeCalls(fetch)).toHaveLength(0);
      expect(status()).toBe("The last module ends at 21:10: no room can be booked after that.");
      expect($("free-status").className).toBe("notice notice--error");
    });

    it("offers the first module when the page opens after the last one", async () => {
      await setup({ at: new Date(2026, 10, 23, 22, 0) });
      expect($("free-from").value).toBe("0");
      expect($("free-to").value).toBe("0");
    });

    it("ignores an answer that arrives after a newer request", async () => {
      const calls = [];
      await setup({ freeRoute: () => { const d = deferred(); calls.push(d); return d.promise; } });
      pick($("free-faculty"), "f1");       // request 1
      pick($("free-capacity"), "10");      // request 2
      calls[1].resolve(response(ROOMS));
      await flush();
      expect(cards()).toHaveLength(2);
      calls[0].resolve(response([]));      // the older answer comes last
      await flush();
      expect(cards()).toHaveLength(2);
      expect(status()).toBe("2 free rooms · In module 14:40–16:10");
    });

    it("ignores a failure from a request that is no longer the latest", async () => {
      const calls = [];
      await setup({ freeRoute: () => { const d = deferred(); calls.push(d); return d.promise; } });
      pick($("free-faculty"), "f1");
      pick($("free-capacity"), "10");
      calls[1].resolve(response(ROOMS));
      await flush();
      calls[0].resolve(response({ detail: "late" }, 500));
      await flush();
      expect(status()).toBe("2 free rooms · In module 14:40–16:10");
      expect($("free-status").className).toBe("muted");
    });
  });

  describe("custom interval", () => {
    it("shows the module pickers and searches the chosen modules on the chosen date", async () => {
      const { fetch } = await setup();
      await chooseFaculty("f1");
      tab("custom");
      await flush();
      expect($("free-custom").hidden).toBe(false);
      expect(document.querySelector('[data-free-mode="custom"]').getAttribute("aria-selected")).toBe("true");
      expect(document.querySelector('[data-free-mode="now"]').getAttribute("aria-selected")).toBe("false");
      // The defaults are the current module, and the date is today.
      expect(queryOf(freeCalls(fetch).at(-1))).toEqual({
        date: "2026-11-23", start_time: "14:40", end_time: "16:10", faculty_id: "f1"
      });
      expect(status()).toBe("2 free rooms");

      pick($("free-from"), "2");
      pick($("free-to"), "3");
      expect(queryOf(freeCalls(fetch).at(-1))).toMatchObject({ start_time: "11:20", end_time: "14:30" });
      pick($("free-date"), "2026-11-25");
      expect(queryOf(freeCalls(fetch).at(-1))).toMatchObject({ date: "2026-11-25" });
    });

    it("uses today when the date is cleared", async () => {
      const { fetch } = await setup();
      await chooseFaculty("f1");
      tab("custom");
      pick($("free-date"), "");
      expect(queryOf(freeCalls(fetch).at(-1)).date).toBe("2026-11-23");
    });

    it("refuses a range that ends before it starts, without asking", async () => {
      const { fetch } = await setup();
      await chooseFaculty("f1");
      tab("custom");
      pick($("free-from"), "3");
      const before = freeCalls(fetch).length;
      pick($("free-to"), "1");
      expect(freeCalls(fetch)).toHaveLength(before);
      expect(status()).toBe("Choose whole modules: from the start of one module to the end of another.");
    });

    it("sends the capacity and equipment filters only when they are set", async () => {
      const { fetch } = await setup();
      await chooseFaculty("f1");
      tab("custom");
      pick($("free-capacity"), "20");
      $("free-projector").checked = true;
      $("free-projector").dispatchEvent(new Event("change"));
      $("free-verified").checked = true;
      $("free-verified").dispatchEvent(new Event("change"));
      expect(queryOf(freeCalls(fetch).at(-1))).toMatchObject({
        min_capacity: "20", has_projector: "true", only_verified: "true"
      });
      $("free-projector").checked = false;
      $("free-projector").dispatchEvent(new Event("change"));
      $("free-verified").checked = false;
      $("free-verified").dispatchEvent(new Event("change"));
      const last = queryOf(freeCalls(fetch).at(-1));
      expect(last.has_projector).toBeUndefined();
      expect(last.only_verified).toBeUndefined();
    });

    it("leaves out the capacity when the field is empty", async () => {
      const { fetch } = await setup();
      await chooseFaculty("f1");
      tab("custom");
      pick($("free-capacity"), "");
      expect(queryOf(freeCalls(fetch).at(-1)).min_capacity).toBeUndefined();
    });

    it("does not repeat a request when no control changes", async () => {
      const { fetch } = await setup();
      await chooseFaculty("f1");
      tab("custom");
      const before = freeCalls(fetch).length;
      await flush();
      expect(freeCalls(fetch)).toHaveLength(before);
    });
  });

  describe("returning to free now", () => {
    it("asks again for the current module when the tab is clicked", async () => {
      const { fetch } = await setup();
      await chooseFaculty("f1");
      tab("custom");
      tab("now");
      expect($("free-custom").hidden).toBe(true);
      expect(queryOf(freeCalls(fetch).at(-1))).toMatchObject({ start_time: "14:40", end_time: "16:10" });
    });

    it("asks again when the page is shown again (back button)", async () => {
      const { fetch } = await setup();
      await chooseFaculty("f1");
      const before = freeCalls(fetch).length;
      window.dispatchEvent(new Event("pageshow"));
      expect(freeCalls(fetch)).toHaveLength(before + 1);
    });

    it("does not ask again on page show while the custom interval is shown", async () => {
      const { fetch } = await setup();
      await chooseFaculty("f1");
      tab("custom");
      const before = freeCalls(fetch).length;
      window.dispatchEvent(new Event("pageshow"));
      expect(freeCalls(fetch)).toHaveLength(before);
    });

    it("asks again when the tab becomes visible, but not when it is hidden", async () => {
      let hidden = true;
      Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden });
      const { fetch } = await setup();
      await chooseFaculty("f1");
      const before = freeCalls(fetch).length;
      document.dispatchEvent(new Event("visibilitychange"));
      expect(freeCalls(fetch)).toHaveLength(before);
      hidden = false;
      document.dispatchEvent(new Event("visibilitychange"));
      expect(freeCalls(fetch)).toHaveLength(before + 1);
      tab("custom");
      const customBefore = freeCalls(fetch).length;
      document.dispatchEvent(new Event("visibilitychange"));
      expect(freeCalls(fetch)).toHaveLength(customBefore);
      delete document.hidden;
    });

    it("follows the module while the page is open", async () => {
      const { fetch } = await setup();
      await chooseFaculty("f1");
      const before = freeCalls(fetch).length;
      // Still the same module: nothing is asked.
      vi.advanceTimersByTime(30000);
      expect(freeCalls(fetch)).toHaveLength(before);
      // The clock moves into the next module (16:20-17:50): the list follows it.
      vi.setSystemTime(new Date(2026, 10, 23, 16, 25));
      vi.advanceTimersByTime(30000);
      await flush();
      expect(freeCalls(fetch)).toHaveLength(before + 1);
      expect(queryOf(freeCalls(fetch).at(-1))).toMatchObject({ start_time: "16:20", end_time: "17:50" });
      expect(status()).toBe("2 free rooms · In module 16:20–17:50");
    });

    it("does not follow the module while a custom interval is shown", async () => {
      const { fetch } = await setup();
      await chooseFaculty("f1");
      tab("custom");
      const before = freeCalls(fetch).length;
      vi.setSystemTime(new Date(2026, 10, 23, 16, 25));
      vi.advanceTimersByTime(30000);
      expect(freeCalls(fetch)).toHaveLength(before);
    });
  });

  describe("language", () => {
    it("writes the status and the module labels again in the new language", async () => {
      await setup();
      await chooseFaculty("f1");
      window.UniSpaceI18n.setLanguage("ro");
      await flush();
      expect(status()).toBe("2 săli libere · În modulul 14:40–16:10");
      expect($("free-from").options[0].textContent).toBe("1 · 08:00–09:30");
      expect(cards()[0].querySelector(".room-card__faculty").textContent).toBe("Facultatea de Drept");
    });

    it("prints the Campus label of a room with no faculty in the new language", async () => {
      await setup({ language: "ro" });
      await chooseFaculty("f1");
      expect(cards()[1].querySelector(".room-card__faculty").textContent).toBe("Campus");
    });
  });

  describe("page without a room list", () => {
    it("does nothing, and asks for nothing", async () => {
      const { fetch } = await setup({ withoutList: true });
      expect(freeCalls(fetch)).toHaveLength(0);
      expect(document.getElementById("free-faculty")).not.toBeNull();
    });
  });
});
