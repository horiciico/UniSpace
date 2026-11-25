import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  deferred,
  flush,
  loadI18n,
  loadScript,
  mountPage,
  queryOf,
  response,
  stubFetch,
} from "../helpers.js";

// Monday 23 November 2026: the default week when no date is given.
const MONDAY = new Date(2026, 10, 23, 10, 0);

const FACULTIES = [
  { id: "f1", code: "dre", name: "Facultatea de Drept" },
  { id: "f2", code: "ing", name: "Facultatea de Inginerie" },
];
const GROUPS = [{ id: "g1", name: "EFS_AN1", faculty_id: "f1" }];
const PROFESSORS = [{ name: "Ana Pop" }, { name: "Ion Ionescu" }];
const CLASSROOMS = [
  {
    id: "r1",
    name: "Sala 107",
    faculty_id: "f1",
    capacity: 30,
    is_bookable: true,
    is_field_verified: true,
  },
];

const ITEMS = [
  {
    id: "i1",
    title: "Algebra",
    activity_type: "COURSE",
    priority: 5,
    day_of_week: 1,
    date: "2026-11-23",
    start_time: "09:40",
    end_time: "11:10",
    parity: "ODD",
    room_id: "r1",
    room_name: "Sala 107",
    professor: "Ana Pop / Ion Ionescu",
    groups: ["EFS_AN1"],
    is_recurring: true,
  },
  {
    id: "i2",
    title: "Seminar X",
    activity_type: "SEMINAR",
    priority: 3,
    day_of_week: 2,
    date: "2026-11-24",
    start_time: "08:00",
    end_time: "09:30",
    parity: "ALL",
    room_id: "r1",
    room_name: "Sala 107",
    professor: null,
    groups: [],
    is_recurring: false,
  },
];

const SCHEDULE = {
  week_start: "2026-11-23",
  week_end: "2026-11-29",
  week_number: 9,
  parity: "ODD",
  entity_type: "group",
  entity_label: "EFS_AN1",
  items: ITEMS,
};

// Mounts the real timetable page at `url`, loads its scripts as the browser does, and waits
// for the faculty list. `routes` replaces individual answers.
async function setup({
  url = "/timetable",
  language = "en",
  routes = {},
  withoutGrid = false,
} = {}) {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(MONDAY);
  window.history.replaceState(null, "", url);
  mountPage("pages/student/timetable.html");
  if (withoutGrid) document.getElementById("tt-grid").remove();
  await loadI18n(language);
  await loadScript("js/modules.js");
  await loadScript("js/api.js");
  await loadScript("js/grid.js");
  const fetch = stubFetch({
    "/api/faculties": () => response(FACULTIES),
    "/api/groups": () => response(GROUPS),
    "/api/professors": () => response(PROFESSORS),
    "/api/classrooms": () => response(CLASSROOMS),
    "/api/schedule": () => response(SCHEDULE),
    ...routes,
  });
  await loadScript("js/pages/timetable.js");
  await flush();
  return { fetch };
}

const $ = (id) => document.getElementById(id);
const text = (id) => $(id).textContent;
const status = () => text("tt-status");
const blocks = () => [...document.querySelectorAll(".tt-block")];
const calls = (fetch, path) =>
  fetch.mock.calls.map((c) => c[0]).filter((u) => u.startsWith(path));
const lastSchedule = (fetch) => queryOf(calls(fetch, "/api/schedule").at(-1));
const entityNames = () => [...$("entity-list").options].map((o) => o.value);

function pick(element, value, type = "change") {
  element.value = value;
  element.dispatchEvent(new Event(type, { bubbles: true }));
}

function chooseTab(mode) {
  document.querySelector(`[role="tab"][data-mode="${mode}"]`).click();
}

// Faculty, then entity: the usual way in, as a user would do it.
async function chooseGroup(name = "EFS_AN1") {
  pick($("tt-faculty"), "f1");
  await flush();
  pick($("tt-entity"), name, "input");
  await flush();
}

describe("timetable.js: the timetable page", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  describe("starting point", () => {
    it("opens on the group view with nothing chosen, and no grid", async () => {
      const { fetch } = await setup();
      expect(
        document.querySelector('[role="tab"][aria-selected="true"]').dataset
          .mode,
      ).toBe("group");
      expect(text("tt-entity-label")).toBe("Group");
      expect(status()).toBe("");
      expect($("tt-empty").hidden).toBe(false);
      expect($("tt-body").hidden).toBe(true);
      expect($("tt-entity").disabled).toBe(true);
      expect(text("tt-week-label")).toBe("23 Nov – 29 Nov");
      expect(calls(fetch, "/api/schedule")).toHaveLength(0);
    });

    it("offers only the placeholder in the faculty list for the group view", async () => {
      await setup();
      expect([...$("tt-faculty").options].map((o) => o.value)).toEqual([
        "",
        "f1",
        "f2",
      ]);
      expect($("tt-faculty").options[0].textContent).toBe("Choose a faculty");
    });

    it("uses the faculty, group and week from the address", async () => {
      const { fetch } = await setup({
        url: "/timetable?mode=group&faculty_id=f1&id=g1&date=2026-11-16",
      });
      expect($("tt-entity").value).toBe("EFS_AN1");
      expect(lastSchedule(fetch)).toEqual({
        date: "2026-11-16",
        faculty_id: "f1",
        group_id: "g1",
      });
      expect(blocks()).toHaveLength(2);
    });

    it("falls back to the group view and today for an unknown mode and a bad date", async () => {
      const { fetch } = await setup({
        url: "/timetable?mode=planet&date=yesterday",
      });
      expect(
        document.querySelector('[role="tab"][aria-selected="true"]').dataset
          .mode,
      ).toBe("group");
      expect(text("tt-week-label")).toBe("23 Nov – 29 Nov");
      expect(calls(fetch, "/api/schedule")).toHaveLength(0);
    });

    it("shows an error when the faculty list cannot be loaded", async () => {
      await setup({ routes: { "/api/faculties": () => response({}, 500) } });
      expect(status()).toBe("Could not load the timetable. Try again.");
      expect($("tt-status").className).toBe("notice notice--error");
    });

    it("does nothing when the page has no grid", async () => {
      const { fetch } = await setup({ withoutGrid: true });
      expect(fetch).not.toHaveBeenCalled();
    });
  });

  describe("faculty and entity", () => {
    it("lists the groups of the faculty and enables the entity box", async () => {
      const { fetch } = await setup();
      pick($("tt-faculty"), "f1");
      await flush();
      expect(calls(fetch, "/api/groups")).toHaveLength(1);
      expect(entityNames()).toEqual(["EFS_AN1"]);
      expect($("tt-entity").disabled).toBe(false);
      expect(calls(fetch, "/api/schedule")).toHaveLength(0);
    });

    it("shows the timetable of the chosen group, and writes the choice to the address", async () => {
      const { fetch } = await setup();
      await chooseGroup();
      expect(lastSchedule(fetch)).toEqual({
        date: "2026-11-23",
        faculty_id: "f1",
        group_id: "g1",
      });
      expect($("tt-body").hidden).toBe(false);
      expect($("tt-empty").hidden).toBe(true);
      expect(blocks()).toHaveLength(2);
      expect(text("tt-week-label")).toBe("23 Nov – 29 Nov · Week 9 · Odd");
      expect(status()).toBe("");
      expect(window.location.search).toBe(
        "?mode=group&faculty_id=f1&id=g1&date=2026-11-23",
      );
    });

    it("does not ask again for the group that is already shown", async () => {
      const { fetch } = await setup();
      await chooseGroup();
      const before = calls(fetch, "/api/schedule").length;
      pick($("tt-entity"), "EFS_AN1", "input");
      await flush();
      expect(calls(fetch, "/api/schedule")).toHaveLength(before);
    });

    it("says that a name not in the list is not found, when the box is left", async () => {
      await setup();
      await chooseGroup();
      pick($("tt-entity"), "Nobody", "input");
      expect(status()).toBe("");
      pick($("tt-entity"), "Nobody", "change");
      expect(status()).toBe(
        "That entry was not found. Choose one from the list.",
      );
      expect($("tt-status").className).toBe("notice notice--error");
      expect($("tt-body").hidden).toBe(true);
    });

    it("clears the timetable when the entity is cleared, and asks nothing", async () => {
      const { fetch } = await setup();
      await chooseGroup();
      const before = calls(fetch, "/api/schedule").length;
      pick($("tt-entity"), "", "input");
      expect($("tt-body").hidden).toBe(true);
      expect($("tt-empty").hidden).toBe(false);
      expect(text("tt-week-label")).toBe("23 Nov – 29 Nov");
      expect(calls(fetch, "/api/schedule")).toHaveLength(before);
      pick($("tt-entity"), "  ", "change");
      expect(calls(fetch, "/api/schedule")).toHaveLength(before);
    });

    it("ignores an empty entity box when nothing was chosen", async () => {
      const { fetch } = await setup();
      pick($("tt-faculty"), "f1");
      await flush();
      pick($("tt-entity"), "", "input");
      expect(calls(fetch, "/api/schedule")).toHaveLength(0);
    });

    it("clears the entity and the timetable when the faculty changes", async () => {
      const { fetch } = await setup();
      await chooseGroup();
      pick($("tt-faculty"), "f2");
      await flush();
      expect($("tt-entity").value).toBe("");
      expect($("tt-body").hidden).toBe(true);
      expect(calls(fetch, "/api/groups").at(-1)).toBe(
        "/api/groups?faculty_id=f2",
      );
    });

    it("shows an error and no names when the group list cannot be loaded", async () => {
      await setup({ routes: { "/api/groups": () => response({}, 500) } });
      pick($("tt-faculty"), "f1");
      await flush();
      expect(entityNames()).toEqual([]);
      expect(status()).toBe("Could not load the timetable. Try again.");
    });

    it("ignores a group list that arrives after a newer faculty was chosen", async () => {
      const pending = [];
      await setup({
        routes: {
          "/api/groups": (url) => {
            if (url.includes("f1")) {
              const d = deferred();
              pending.push(d);
              return d.promise;
            }
            return response(GROUPS);
          },
        },
      });
      pick($("tt-faculty"), "f1");
      pick($("tt-faculty"), "f2");
      await flush();
      expect(entityNames()).toEqual(["EFS_AN1"]);
      pending[0].resolve(
        response([{ id: "old", name: "OLD", faculty_id: "f1" }]),
      );
      await flush();
      expect(entityNames()).toEqual(["EFS_AN1"]);
    });

    it("ignores a failed group list that is no longer the latest", async () => {
      const pending = [];
      await setup({
        routes: {
          "/api/groups": (url) => {
            if (url.includes("f1")) {
              const d = deferred();
              pending.push(d);
              return d.promise;
            }
            return response(GROUPS);
          },
        },
      });
      pick($("tt-faculty"), "f1");
      pick($("tt-faculty"), "f2");
      await flush();
      pending[0].resolve(response({}, 500));
      await flush();
      expect(status()).toBe("");
      expect(entityNames()).toEqual(["EFS_AN1"]);
    });
  });

  describe("the three views", () => {
    it("shows professors in the professor view, and sends the name", async () => {
      const { fetch } = await setup();
      chooseTab("professor");
      expect(text("tt-entity-label")).toBe("Professor");
      pick($("tt-faculty"), "f1");
      await flush();
      expect(calls(fetch, "/api/professors")).toHaveLength(1);
      expect(entityNames()).toEqual(["Ana Pop", "Ion Ionescu"]);
      pick($("tt-entity"), "Ana Pop", "input");
      await flush();
      expect(lastSchedule(fetch)).toEqual({
        date: "2026-11-23",
        faculty_id: "f1",
        professor: "Ana Pop",
      });
      expect(window.location.search).toBe(
        "?mode=professor&faculty_id=f1&id=Ana+Pop&date=2026-11-23",
      );
    });

    it("shows rooms in the room view, with Campus among the faculties", async () => {
      const { fetch } = await setup();
      chooseTab("room");
      expect(text("tt-entity-label")).toBe("Room");
      expect([...$("tt-faculty").options].map((o) => o.value)).toEqual([
        "",
        "campus",
        "f1",
        "f2",
      ]);
      pick($("tt-faculty"), "campus");
      await flush();
      expect(calls(fetch, "/api/classrooms").at(-1)).toBe(
        "/api/classrooms?faculty_id=campus",
      );
      pick($("tt-entity"), "Sala 107", "input");
      await flush();
      expect(lastSchedule(fetch)).toEqual({
        date: "2026-11-23",
        room_id: "r1",
      });
    });

    it("draws a room that was chosen with a faculty, with that faculty's unit", async () => {
      const { fetch } = await setup();
      chooseTab("room");
      pick($("tt-faculty"), "f1");
      await flush();
      pick($("tt-entity"), "Sala 107", "input");
      await flush();
      expect(lastSchedule(fetch)).toEqual({
        date: "2026-11-23",
        faculty_id: "f1",
        room_id: "r1",
      });
    });

    it("drops the Campus choice when the view changes to a group", async () => {
      await setup();
      chooseTab("room");
      pick($("tt-faculty"), "campus");
      chooseTab("group");
      expect($("tt-faculty").value).toBe("");
      expect([...$("tt-faculty").options].map((o) => o.value)).toEqual([
        "",
        "f1",
        "f2",
      ]);
    });

    it("keeps the Campus choice when the room view is chosen again", async () => {
      await setup({ url: "/timetable?mode=room&faculty_id=campus" });
      expect($("tt-faculty").value).toBe("campus");
      chooseTab("room");
      expect($("tt-faculty").value).toBe("campus");
    });

    it("opens the room view on Campus from the address", async () => {
      const { fetch } = await setup({
        url: "/timetable?mode=room&faculty_id=campus&id=r1",
      });
      expect(calls(fetch, "/api/classrooms")).toHaveLength(1);
      expect($("tt-faculty").value).toBe("campus");
    });
  });

  describe("choosing from the address", () => {
    it("opens the room named in the address, with the week of the date", async () => {
      const { fetch } = await setup({
        url: "/timetable?mode=room&faculty_id=campus&id=r1&date=2026-11-16",
      });
      expect($("tt-entity").value).toBe("Sala 107");
      expect(lastSchedule(fetch)).toEqual({
        date: "2026-11-16",
        room_id: "r1",
      });
    });

    it("opens the professor named in the address", async () => {
      const { fetch } = await setup({
        url: "/timetable?mode=professor&faculty_id=f1&id=Ion%20Ionescu",
      });
      expect($("tt-entity").value).toBe("Ion Ionescu");
      expect(lastSchedule(fetch)).toEqual({
        date: "2026-11-23",
        faculty_id: "f1",
        professor: "Ion Ionescu",
      });
    });

    it("says so when the entity in the address is not in the list", async () => {
      const { fetch } = await setup({
        url: "/timetable?mode=group&faculty_id=f1&id=nope",
      });
      expect(status()).toBe(
        "That entry was not found. Choose one from the list.",
      );
      expect(calls(fetch, "/api/schedule")).toHaveLength(0);
    });

    it("only writes the address when there is no faculty to look up", async () => {
      const { fetch } = await setup({ url: "/timetable?mode=group&id=g1" });
      expect(calls(fetch, "/api/groups")).toHaveLength(0);
      expect(window.location.search).toBe("?mode=group&date=2026-11-23");
    });

    it("only writes the address when no entity is named", async () => {
      await setup({ url: "/timetable?mode=group&faculty_id=f1" });
      expect(window.location.search).toBe(
        "?mode=group&faculty_id=f1&date=2026-11-23",
      );
    });

    it("says nothing about an address entity when the faculty has no entities", async () => {
      const { fetch } = await setup({
        url: "/timetable?mode=group&faculty_id=f1&id=g1",
        routes: { "/api/groups": () => response([]) },
      });
      expect(status()).toBe("");
      expect(calls(fetch, "/api/schedule")).toHaveLength(0);
    });

    it("shows an error when the faculty list fails after an address was given", async () => {
      await setup({
        url: "/timetable?mode=group&faculty_id=f1&id=g1",
        routes: { "/api/groups": () => response({}, 500) },
      });
      expect(status()).toBe("Could not load the timetable. Try again.");
    });
  });

  describe("loading the timetable", () => {
    it("says so when the week has no activities, and draws an empty grid", async () => {
      await setup({
        routes: { "/api/schedule": () => response({ ...SCHEDULE, items: [] }) },
      });
      await chooseGroup();
      expect(status()).toBe("No activities this week.");
      expect(blocks()).toHaveLength(0);
      expect($("tt-body").hidden).toBe(false);
    });

    it("says the timetable is not found when the server does not know the entity", async () => {
      await setup({
        routes: { "/api/schedule": () => response({ detail: "gone" }, 404) },
      });
      await chooseGroup();
      expect(status()).toBe(
        "That entry was not found. Choose one from the list.",
      );
      expect($("tt-body").hidden).toBe(true);
      expect(text("tt-week-label")).toBe("23 Nov – 29 Nov");
    });

    it("says the timetable cannot be loaded for any other failure", async () => {
      await setup({ routes: { "/api/schedule": () => response({}, 500) } });
      await chooseGroup();
      expect(status()).toBe("Could not load the timetable. Try again.");
      expect($("tt-status").className).toBe("notice notice--error");
    });

    it("ignores a timetable that arrives after a newer request", async () => {
      const pending = [];
      await setup({
        routes: {
          "/api/schedule": () => {
            const d = deferred();
            pending.push(d);
            return d.promise;
          },
        },
      });
      await chooseGroup(); // request 1
      $("tt-next").click(); // request 2, for the next week
      await flush();
      pending[1].resolve(response(SCHEDULE));
      await flush();
      expect(blocks()).toHaveLength(2);
      // The older answer arrives last: it is not drawn.
      pending[0].resolve(response({ ...SCHEDULE, items: [] }));
      await flush();
      expect(status()).toBe("");
      expect(blocks()).toHaveLength(2);
    });

    it("ignores a failure that arrives after a newer request", async () => {
      const pending = [];
      await setup({
        routes: {
          "/api/schedule": () => {
            const d = deferred();
            pending.push(d);
            return d.promise;
          },
        },
      });
      await chooseGroup();
      $("tt-next").click();
      await flush();
      pending[1].resolve(response(SCHEDULE));
      await flush();
      pending[0].resolve(response({}, 500));
      await flush();
      expect(status()).toBe("");
      expect(blocks()).toHaveLength(2);
    });

    it("shows the week's number and parity, or only its dates when the number is unknown", async () => {
      await setup({
        routes: {
          "/api/schedule": () =>
            response({ ...SCHEDULE, week_number: null, parity: null }),
        },
      });
      await chooseGroup();
      expect(text("tt-week-label")).toBe("23 Nov – 29 Nov");
    });

    it("says every week when the parity is not known, but the number is", async () => {
      await setup({
        routes: {
          "/api/schedule": () => response({ ...SCHEDULE, parity: null }),
        },
      });
      await chooseGroup();
      expect(text("tt-week-label")).toBe(
        "23 Nov – 29 Nov · Week 9 · Every week",
      );
    });

    it("shows an even week as Even", async () => {
      await setup({
        routes: {
          "/api/schedule": () =>
            response({ ...SCHEDULE, week_number: 8, parity: "EVEN" }),
        },
      });
      await chooseGroup();
      expect(text("tt-week-label")).toBe("23 Nov – 29 Nov · Week 8 · Even");
    });
  });

  describe("moving between weeks", () => {
    it("moves a week forward and back, keeping the selection", async () => {
      const { fetch } = await setup();
      await chooseGroup();
      $("tt-next").click();
      await flush();
      expect(lastSchedule(fetch).date).toBe("2026-11-30");
      expect(window.location.search).toContain("date=2026-11-30");
      $("tt-prev").click();
      $("tt-prev").click();
      await flush();
      expect(lastSchedule(fetch).date).toBe("2026-11-16");
    });

    it("returns to the current week with Today", async () => {
      const { fetch } = await setup({
        url: "/timetable?mode=group&faculty_id=f1&id=g1&date=2026-12-14",
      });
      expect(lastSchedule(fetch).date).toBe("2026-12-14");
      $("tt-today").click();
      await flush();
      expect(lastSchedule(fetch).date).toBe("2026-11-23");
    });

    it("moves the week even before an entity is chosen, without asking", async () => {
      const { fetch } = await setup();
      $("tt-next").click();
      expect(text("tt-week-label")).toBe("30 Nov – 6 Dec");
      expect(calls(fetch, "/api/schedule")).toHaveLength(0);
    });
  });

  describe("details of an activity", () => {
    it("opens the dialog with the activity's details", async () => {
      await setup();
      await chooseGroup();
      $("tt-dialog").showModal = vi.fn();
      blocks()[0].click();
      expect($("tt-dialog").showModal).toHaveBeenCalled();
      expect(text("tt-d-title")).toBe("Algebra");
      expect(text("tt-d-kind")).toBe("Course");
      expect(text("tt-d-date")).toBe("Monday 23 November");
      expect(text("tt-d-time")).toBe("09:40–11:10");
      expect(text("tt-d-room")).toBe("Sala 107");
      expect(text("tt-d-professor")).toBe("Ana Pop / Ion Ionescu");
      expect(text("tt-d-groups")).toBe("EFS_AN1");
      expect(text("tt-d-priority")).toBe("5");
      expect(text("tt-d-parity")).toBe("Odd");
      expect(text("tt-d-recurring")).toBe("Repeats every week of this parity");
    });

    it("shows the fallbacks for an activity with no professor, groups or recurrence", async () => {
      await setup();
      await chooseGroup();
      blocks()[1].click();
      expect(text("tt-d-kind")).toBe("Seminar");
      expect(text("tt-d-professor")).toBe("Not specified");
      expect(text("tt-d-groups")).toBe("Not specified");
      expect(text("tt-d-parity")).toBe("Every week");
      expect(text("tt-d-recurring")).toBe("One-off event");
      expect(text("tt-d-date")).toBe("Tuesday 24 November");
    });

    it("shows the type itself for a kind it does not know, and every week for an unknown parity", async () => {
      const odd = {
        ...ITEMS[0],
        activity_type: "WORKSHOP",
        parity: null,
        groups: ["A", "B"],
      };
      await setup({
        routes: {
          "/api/schedule": () => response({ ...SCHEDULE, items: [odd] }),
        },
      });
      await chooseGroup();
      blocks()[0].click();
      expect(text("tt-d-kind")).toBe("WORKSHOP");
      expect(text("tt-d-parity")).toBe("Every week");
      expect(text("tt-d-groups")).toBe("A, B");
    });

    it("opens the dialog with the open attribute where showModal is not supported", async () => {
      await setup();
      await chooseGroup();
      expect($("tt-dialog").showModal).toBeUndefined();
      blocks()[0].click();
      expect($("tt-dialog").hasAttribute("open")).toBe(true);
    });

    it("closes the dialog with its close button", async () => {
      await setup();
      await chooseGroup();
      $("tt-dialog").close = vi.fn();
      $("tt-d-close").click();
      expect($("tt-dialog").close).toHaveBeenCalled();
    });

    it("shows the details in the new language when the language changes", async () => {
      await setup();
      await chooseGroup();
      blocks()[0].click();
      $("tt-dialog").close = vi.fn();
      window.UniSpaceI18n.setLanguage("ro");
      await flush();
      // The language change closes the dialog; the next opening shows the new language.
      expect($("tt-dialog").close).toHaveBeenCalled();
      blocks()[0].click();
      expect(text("tt-d-kind")).toBe("Curs");
      expect(text("tt-d-recurring")).toBe(
        "Se repetă în fiecare săptămână de acest tip",
      );
    });

    it("closes an open dialog when the language changes, and draws the grid again", async () => {
      await setup();
      await chooseGroup();
      $("tt-dialog").setAttribute("open", "");
      $("tt-dialog").close = vi.fn();
      window.UniSpaceI18n.setLanguage("ro");
      await flush();
      expect($("tt-dialog").close).toHaveBeenCalled();
      expect(blocks()).toHaveLength(2);
      expect(blocks()[0].textContent).toContain("Curs");
    });

    it("does not close a dialog that is not open when the language changes", async () => {
      await setup();
      await chooseGroup();
      $("tt-dialog").close = vi.fn();
      window.UniSpaceI18n.setLanguage("ro");
      await flush();
      expect($("tt-dialog").close).not.toHaveBeenCalled();
    });
  });

  describe("language", () => {
    it("writes the lists, labels and status again in the new language", async () => {
      await setup();
      chooseTab("room");
      window.UniSpaceI18n.setLanguage("ro");
      await flush();
      expect(text("tt-entity-label")).toBe("Sală");
      expect($("tt-faculty").options[0].textContent).toBe("Alege o facultate");
      expect($("tt-faculty").options[1].textContent).toBe("Campus");
      expect(text("tt-week-label")).toBe("23 nov. – 29 nov.");
    });

    it("keeps the status message, translated again", async () => {
      await setup({ url: "/timetable?mode=group&faculty_id=f1&id=nope" });
      expect(status()).toBe(
        "That entry was not found. Choose one from the list.",
      );
      window.UniSpaceI18n.setLanguage("ro");
      await flush();
      expect(status()).toBe(
        "Nu am găsit această intrare. Alege una din listă.",
      );
    });

    it("does not draw a grid after a language change when no timetable is shown", async () => {
      await setup();
      window.UniSpaceI18n.setLanguage("ro");
      await flush();
      expect(blocks()).toHaveLength(0);
      expect($("tt-body").hidden).toBe(true);
    });
  });
});
