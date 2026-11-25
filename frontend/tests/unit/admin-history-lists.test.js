import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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

// The filter lists of the booking history: the faculties and the rooms, when they fail or answer late.
const NOW = new Date(2026, 10, 24, 12, 0);
const FACULTIES = [{ id: "f1", code: "dre", name: "Facultatea de Drept" }];
const ROOMS_ALL = [
  { id: "r1", name: "B110" },
  { id: "r2", name: "L2" },
];
const ANSWER = { items: [], total: 0, limit: 15, offset: 0 };

async function setup(routes = {}, { open = true } = {}) {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  mountPage("pages/admin/index.html");
  await loadI18n("en");
  window.UniSpaceI18n.setLanguage("en");
  window.UniSpaceI18n.apply(document.body);
  await loadScript("js/api.js");
  const fetch = stubFetch({
    "/api/admin/bookings/pending": () => response([]),
    "/api/faculties": () => response(FACULTIES),
    "/api/classrooms": () => response(ROOMS_ALL),
    "/api/admin/bookings": () => response(ANSWER),
    ...routes,
  });
  await loadScript("js/pages/admin-bookings.js");
  await loadScript("js/bookings.js");
  await loadScript("js/pages/admin-history.js");
  await flush();
  if (open) {
    document.querySelector('[role="tab"][data-tab="history"]').click();
    await flush();
    await flush();
  }
  return { fetch };
}

const roomNames = () =>
  [...document.getElementById("hist-room").options].map((o) => o.textContent);

function tidy() {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
}

describe("admin history: the filter lists", () => {
  beforeEach(() => vi.resetModules());
  afterEach(tidy);

  it("still lists the bookings when the faculties cannot be loaded", async () => {
    const { fetch } = await setup({
      "/api/faculties": () => response({ detail: "x" }, 500),
    });

    expect(
      fetch.mock.calls.some((c) => c[0].startsWith("/api/admin/bookings?")),
    ).toBe(true);
    expect(document.getElementById("hist-faculty").options).toHaveLength(0);
  });

  it("keeps the rooms it had when the rooms cannot be loaded", async () => {
    await setup({ "/api/classrooms": () => response({ detail: "x" }, 500) });

    expect(roomNames()).toEqual([]);
  });

  it("ignores a room list that arrives after a newer one", async () => {
    const late = deferred();
    await setup({
      "/api/classrooms": (url) =>
        queryOf(url).faculty_id === "f1"
          ? late.promise.then(() => response([{ id: "x", name: "Stale room" }]))
          : response(ROOMS_ALL),
    });

    const faculty = document.getElementById("hist-faculty");
    faculty.value = "f1";
    faculty.dispatchEvent(new Event("change"));
    faculty.value = "";
    faculty.dispatchEvent(new Event("change"));
    await flush();
    late.resolve();
    await flush();

    expect(roomNames()).toEqual(["All rooms", "B110", "L2"]);
  });

  it("ignores a failure of a room list that is no longer the latest", async () => {
    const late = deferred();
    await setup({
      "/api/classrooms": (url) =>
        queryOf(url).faculty_id === "f1" ? late.promise : response(ROOMS_ALL),
    });

    const faculty = document.getElementById("hist-faculty");
    faculty.value = "f1";
    faculty.dispatchEvent(new Event("change"));
    faculty.value = "";
    faculty.dispatchEvent(new Event("change"));
    await flush();
    late.reject(Object.assign(new Error("x"), { status: 500 }));
    await flush();

    expect(document.getElementById("hist-status-line").hidden).toBe(true);
  });
});

describe("admin history: an unknown status, a late page, and a language change before opening", () => {
  beforeEach(() => vi.resetModules());
  afterEach(tidy);

  it("shows an unknown status word as it came", async () => {
    await setup({
      "/api/admin/bookings": () =>
        response({
          items: [
            {
              id: "m1",
              classroom_id: "r1",
              classroom_name: "B110",
              faculty_id: null,
              faculty_name: null,
              specific_date: "2026-12-18",
              start_time: "18:00",
              end_time: "19:30",
              title: "Odd",
              status: "mystery",
              created_at: null,
              user_id: "u",
              user_email: "a@ulbsibiu.ro",
              user_role: "STUDENT",
            },
          ],
          total: 1,
          limit: 15,
          offset: 0,
        }),
    });

    expect(
      document.querySelectorAll("#hist-body > tr.row td")[4].textContent,
    ).toBe("mystery");
  });

  it("ignores a page that arrives after a newer filter has been chosen", async () => {
    const late = deferred();
    await setup({
      "/api/admin/bookings": (url) =>
        queryOf(url).status === "approved"
          ? response({ items: [], total: 0, limit: 15, offset: 0 })
          : late.promise.then(() =>
              response({ items: [], total: 99, limit: 15, offset: 0 }),
            ),
    });

    const status = document.getElementById("hist-status");
    status.value = "approved";
    status.dispatchEvent(new Event("change"));
    await flush();
    late.resolve();
    await flush();

    expect(document.getElementById("hist-range").textContent).toBe("");
  });

  it("does nothing on a language change before the history has been opened", async () => {
    const { fetch } = await setup({}, { open: false });
    const before = fetch.mock.calls.length;

    document.dispatchEvent(new CustomEvent("unispace:langchange"));
    await flush();

    expect(fetch.mock.calls.length).toBe(before);
  });
});

describe("admin history: a failed page that is no longer the latest", () => {
  beforeEach(() => vi.resetModules());
  afterEach(tidy);

  it("does not show its failure once a newer filter is in place", async () => {
    const late = deferred();
    await setup({
      "/api/admin/bookings": (url) =>
        queryOf(url).status === "approved"
          ? response({ items: [], total: 0, limit: 15, offset: 0 })
          : late.promise,
    });

    const status = document.getElementById("hist-status");
    status.value = "approved";
    status.dispatchEvent(new Event("change"));
    await flush();
    late.reject(Object.assign(new Error("x"), { status: 500 }));
    await flush();

    expect(document.getElementById("hist-status-line").hidden).toBe(true);
  });
});
