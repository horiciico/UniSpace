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

// "Orarul meu" on the timetable page: the professor's own week, the move button, and who sees the tab.
const NOW = new Date(2026, 10, 25, 10, 0); // Wednesday 25 Nov 2026, week of 23 Nov

const PROFESSOR = {
  id: "u1",
  email: "p@ulbsibiu.ro",
  name: "P",
  role: "PROFESSOR",
};
const STUDENT = {
  id: "u2",
  email: "s@ulbsibiu.ro",
  name: "S",
  role: "STUDENT",
};
const FACULTIES = [{ id: "f1", code: "dre", name: "Facultatea de Drept" }];
const GROUPS = [{ id: "g1", name: "Grupa 1", faculty_id: "f1" }];
const ITEM = {
  id: "i1",
  title: "Algebra",
  activity_type: "COURSE",
  priority: 5,
  day_of_week: 3,
  date: "2026-11-25",
  start_time: "08:00",
  end_time: "09:30",
  parity: "ALL",
  room_id: "r1",
  room_name: "A1",
  professor: "Prof",
  groups: ["332CA"],
  is_recurring: true,
};
const LINKED = {
  linked: true,
  professor_id: "p1",
  week_start: "2026-11-23",
  week_end: "2026-11-29",
  activities: [ITEM],
};
const UNLINKED = {
  linked: false,
  professor_id: null,
  week_start: "2026-11-23",
  week_end: "2026-11-29",
  activities: [],
};

const $ = (id) => document.getElementById(id);

async function setup({
  search = "",
  user = PROFESSOR,
  auth = true,
  routes = {},
} = {}) {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  window.history.replaceState(
    null,
    "",
    `/timetable${search ? "?" + search : ""}`,
  );
  mountPage("pages/student/timetable.html");
  await loadI18n("en");
  await loadScript("js/modules.js");
  await loadScript("js/api.js");
  await loadScript("js/grid.js");
  await loadScript("js/bookings.js");
  if (auth) window.UniSpaceAuth = { ready: Promise.resolve(user) };
  window.UniSpaceMove = { open: vi.fn() };
  const fetch = stubFetch({
    "/api/faculties": () => response(FACULTIES),
    "/api/groups": () => response(GROUPS),
    "/api/professors/me/timetable": () => response(LINKED),
    ...routes,
  });
  await loadScript("js/pages/timetable.js");
  await flush();
  await flush();
  await flush();
  return fetch;
}

const mineCalls = (fetch) =>
  fetch.mock.calls.filter(([url]) => url.includes("/professors/me/timetable"));

describe("timetable.js: the Orarul meu tab shows for a professor only", () => {
  beforeEach(() => {
    vi.resetModules();
    delete window.UniSpaceMove;
  });

  it("shows the tab to a professor", async () => {
    await setup();

    expect($("tt-tab-mine").hidden).toBe(false);
  });

  it("keeps the tab hidden from a student", async () => {
    await setup({ user: STUDENT });

    expect($("tt-tab-mine").hidden).toBe(true);
  });

  it("keeps the tab hidden from a visitor who is not signed in", async () => {
    await setup({ user: null });

    expect($("tt-tab-mine").hidden).toBe(true);
  });

  it("keeps the tab hidden when there is no session script on the page", async () => {
    await setup({ auth: false });

    expect($("tt-tab-mine").hidden).toBe(true);
  });

  it("does not open the view for a student who asks for it in the link", async () => {
    const fetch = await setup({ search: "mode=mine", user: STUDENT });

    expect(mineCalls(fetch)).toHaveLength(0);
    expect($("tt-tab-mine").hidden).toBe(true);
    expect(new URLSearchParams(window.location.search).get("mode")).toBe(
      "group",
    );
  });
});

describe("timetable.js: the Orarul meu view", () => {
  beforeEach(() => {
    vi.resetModules();
    delete window.UniSpaceMove;
  });

  it("opens from the tab: the week of the day, the grid, and no filters", async () => {
    const fetch = await setup();

    $("tt-tab-mine").click();
    await flush();

    const [url] = mineCalls(fetch).at(-1);
    expect(new URL(url, "http://x").searchParams.get("week_start")).toBe(
      "2026-11-23",
    );
    expect($("tt-tab-mine").getAttribute("aria-selected")).toBe("true");
    expect($("tt-filter-faculty").hidden).toBe(true);
    expect($("tt-filter-entity").hidden).toBe(true);
    expect($("tt-move-bar").hidden).toBe(false);
    expect($("tt-move").disabled).toBe(false);
    expect($("tt-body").hidden).toBe(false);
    expect($("tt-unlinked").hidden).toBe(true);
    expect($("tt-grid").textContent).toContain("Algebra");
    expect($("tt-room").hidden).toBe(true);
    expect($("tt-hint").hidden).toBe(true);
    expect(new URLSearchParams(window.location.search).get("mode")).toBe(
      "mine",
    );
  });

  it("does not fetch the faculty's groups, professors or rooms in this view", async () => {
    const fetch = await setup({ search: "mode=mine&faculty_id=f1" });

    expect(fetch.mock.calls.some(([url]) => url.includes("/api/groups"))).toBe(
      false,
    );
    expect(mineCalls(fetch).length).toBeGreaterThan(0);
  });

  it("opens straight away when the link asks for it and the account is a professor", async () => {
    const fetch = await setup({ search: "mode=mine" });

    expect(mineCalls(fetch).length).toBeGreaterThan(0);
    expect($("tt-tab-mine").getAttribute("aria-selected")).toBe("true");
    expect($("tt-body").hidden).toBe(false);
  });

  it("shows the unlinked notice, no grid, and a disabled move button", async () => {
    await setup({
      search: "mode=mine",
      routes: { "/api/professors/me/timetable": () => response(UNLINKED) },
    });

    expect($("tt-unlinked").hidden).toBe(false);
    expect($("tt-body").hidden).toBe(true);
    expect($("tt-empty").hidden).toBe(true);
    expect($("tt-move").disabled).toBe(true);
    expect($("tt-status").textContent).toBe("");
  });

  it("says so when the week has no activity", async () => {
    await setup({
      search: "mode=mine",
      routes: {
        "/api/professors/me/timetable": () =>
          response({ ...LINKED, activities: [] }),
      },
    });

    expect($("tt-status").textContent).toBe("No activities this week.");
    expect($("tt-body").hidden).toBe(false);
  });

  it("shows the timetable error and no grid when the week cannot be loaded", async () => {
    await setup({
      search: "mode=mine",
      routes: {
        "/api/professors/me/timetable": () => response({ detail: "x" }, 500),
      },
    });

    expect($("tt-status").textContent).toBe(
      "Could not load the timetable. Try again.",
    );
    expect($("tt-body").hidden).toBe(true);
    expect($("tt-empty").hidden).toBe(true);
  });

  it("moves between weeks", async () => {
    const fetch = await setup({ search: "mode=mine" });

    $("tt-next").click();
    await flush();
    $("tt-prev").click();
    $("tt-prev").click();
    await flush();

    const starts = mineCalls(fetch).map(([url]) =>
      new URL(url, "http://x").searchParams.get("week_start"),
    );
    expect(starts).toContain("2026-11-30");
    expect(starts.at(-1)).toBe("2026-11-16");
  });

  it("ignores an answer that arrives after the view has moved on", async () => {
    const slow = deferred();
    let calls = 0;
    await setup({
      search: "mode=mine",
      routes: {
        "/api/professors/me/timetable": () => {
          calls += 1;
          return calls === 1 ? slow.promise : response(UNLINKED);
        },
      },
    });
    // The first request (from the link) is still open; the next week's answer comes first.
    $("tt-next").click();
    await flush();
    slow.resolve(response(LINKED));
    await flush();

    expect($("tt-unlinked").hidden).toBe(false);
  });

  it("ignores a late failure from a week the view has left", async () => {
    const slow = deferred();
    let calls = 0;
    await setup({
      search: "mode=mine",
      routes: {
        "/api/professors/me/timetable": () => {
          calls += 1;
          return calls === 1 ? slow.promise : response(LINKED);
        },
      },
    });
    $("tt-next").click();
    await flush();
    slow.resolve(response({ detail: "x" }, 500));
    await flush();

    expect($("tt-status").textContent).toBe("");
    expect($("tt-body").hidden).toBe(false);
  });

  it("opens the move dialog from the button, and reloads the week when a move is made", async () => {
    const fetch = await setup({ search: "mode=mine" });

    $("tt-move").click();
    expect(window.UniSpaceMove.open).toHaveBeenCalledTimes(1);
    const onMoved = window.UniSpaceMove.open.mock.calls[0][0];
    const before = mineCalls(fetch).length;
    onMoved();
    await flush();

    expect(mineCalls(fetch).length).toBe(before + 1);
  });

  it("goes back to a group view: the filters and the move bar return, and no professor request", async () => {
    const fetch = await setup({ search: "mode=mine" });
    const before = mineCalls(fetch).length;

    document.querySelector("[data-mode='group']").click();
    await flush();

    expect($("tt-filter-faculty").hidden).toBe(false);
    expect($("tt-filter-entity").hidden).toBe(false);
    expect($("tt-move-bar").hidden).toBe(true);
    expect($("tt-unlinked").hidden).toBe(true);
    expect(mineCalls(fetch).length).toBe(before);
  });

  it("keeps the view and redraws it when the language changes", async () => {
    const fetch = await setup({ search: "mode=mine" });
    const before = mineCalls(fetch).length;

    document.dispatchEvent(new Event("unispace:langchange"));
    await flush();

    expect($("tt-move-bar").hidden).toBe(false);
    expect($("tt-grid").textContent).toContain("Algebra");
    expect(mineCalls(fetch).length).toBe(before);
  });
});
