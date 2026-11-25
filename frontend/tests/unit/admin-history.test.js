import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  flush,
  loadI18n,
  loadScript,
  mountPage,
  queryOf,
  response,
  stubFetch,
} from "../helpers.js";

// Booking history for admins (issue: admin booking history). Shown on a second tab; 15 rows a page.
const NOW = new Date(2026, 10, 24, 12, 0);

const FACULTIES = [{ id: "f1", code: "dre", name: "Facultatea de Drept" }];
const ROOMS_ALL = [
  { id: "r1", name: "B110", faculty_id: "f1", is_bookable: true },
  { id: "r2", name: "L2", faculty_id: null, is_bookable: true },
];

// A list of bookings, `count` long: the first is in the future and approved.
function bookings(count) {
  return Array.from({ length: count }, (_, i) => ({
    id: `b${i}`,
    classroom_id: "r1",
    classroom_name: "B110",
    faculty_id: "f1",
    faculty_name: "Facultatea de Drept",
    specific_date: i === 0 ? "2026-12-18" : "2026-11-01",
    start_time: "18:00",
    end_time: "19:30",
    title: `Event ${i}`,
    status: i === 0 ? "approved" : "rejected",
    created_at: "2026-11-20T10:00:00",
    user_id: "u1",
    user_email: `user${i}@ulbsibiu.ro`,
    user_role: "STUDENT",
  }));
}

// Answers /api/admin/bookings with the slice that the request asks for.
function historyAnswer(all) {
  return (url) => {
    const q = queryOf(url);
    const limit = Number(q.limit || 50);
    const offset = Number(q.offset || 0);
    return response({
      items: all.slice(offset, offset + limit),
      total: all.length,
      limit,
      offset,
    });
  };
}

async function setup({ total = 40, routes = {}, language = "en" } = {}) {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  mountPage("pages/admin/index.html");
  await loadI18n(language);
  window.UniSpaceI18n.setLanguage(language);
  window.UniSpaceI18n.apply(document.body);
  const all = bookings(total);
  const fetch = stubFetch({
    "/api/admin/bookings/pending": () => response([]),
    "/api/faculties": () => response(FACULTIES),
    "/api/classrooms": () => response(ROOMS_ALL),
    "/api/admin/bookings": historyAnswer(all),
    ...routes,
  });
  await loadScript("js/api.js");
  await loadScript("js/bookings.js");
  await loadScript("js/pages/admin-bookings.js");
  await loadScript("js/pages/admin-history.js");
  await flush();
  await flush();
  return { fetch, all };
}

const $ = (id) => document.getElementById(id);
const tab = (name) =>
  document.querySelector(`[role="tab"][data-tab="${name}"]`);
const rows = () => [...document.querySelectorAll("#hist-body > tr.row")];
const confirms = () => [
  ...document.querySelectorAll("#hist-body > tr.confirm"),
];
const historyCalls = (fetch) =>
  fetch.mock.calls
    .map((c) => c[0])
    .filter((u) => u.startsWith("/api/admin/bookings?"));
const lastHistoryQuery = (fetch) => queryOf(historyCalls(fetch).at(-1));

function pick(element, value) {
  element.value = value;
  element.dispatchEvent(new Event("change", { bubbles: true }));
}

async function openHistory() {
  tab("history").click();
  await flush();
  await flush();
}

function tidy() {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
}

describe("admin history: the tabs", () => {
  beforeEach(() => vi.resetModules());
  afterEach(tidy);

  it("opens on the pending requests, and the history tab shows its own panel", async () => {
    const { fetch } = await setup();
    expect(tab("pending").getAttribute("aria-selected")).toBe("true");
    expect($("panel-pending").hidden).toBe(false);
    expect($("panel-history").hidden).toBe(true);
    expect(historyCalls(fetch)).toHaveLength(0);

    await openHistory();

    expect(tab("history").getAttribute("aria-selected")).toBe("true");
    expect($("panel-pending").hidden).toBe(true);
    expect($("panel-history").hidden).toBe(false);
    expect(historyCalls(fetch)).toHaveLength(1);
  });

  it("switches back to the pending requests", async () => {
    await setup();
    await openHistory();
    tab("pending").click();
    expect($("panel-pending").hidden).toBe(false);
    expect($("panel-history").hidden).toBe(true);
    expect(tab("pending").getAttribute("aria-selected")).toBe("true");
  });
});

describe("admin history: the list and its pages", () => {
  beforeEach(() => vi.resetModules());
  afterEach(tidy);

  it("asks for all bookings with no faculty chosen, 15 at a time, and shows the first page", async () => {
    const { fetch } = await setup({ total: 40 });
    await openHistory();

    expect(lastHistoryQuery(fetch)).toEqual({ limit: "15", offset: "0" });
    expect(rows()).toHaveLength(15);
    expect($("hist-range").textContent).toBe("1–15 of 40");
  });

  it("shows each booking with its date, room and faculty, requester, and status", async () => {
    await setup({ total: 1 });
    await openHistory();

    const [row] = rows();
    expect(row.textContent).toContain("Fri 18 Dec · 18:00–19:30");
    expect(row.textContent).toContain("B110 (Facultatea de Drept)");
    expect(row.textContent).toContain("Event 0");
    expect(row.textContent).toContain("user0@ulbsibiu.ro");
    expect(row.textContent).toContain("Student");
    expect(row.querySelectorAll("td")[4].textContent).toBe("Approved");
  });

  it("shows Campus for a room with no faculty", async () => {
    const all = bookings(1);
    all[0].classroom_name = "L2";
    all[0].faculty_id = null;
    all[0].faculty_name = null;
    await setup({ routes: { "/api/admin/bookings": historyAnswer(all) } });
    await openHistory();

    expect(rows()[0].textContent).toContain("L2 (Campus)");
  });

  it("moves through the pages with Previous and Next, and stops at both ends", async () => {
    const { fetch } = await setup({ total: 40 });
    await openHistory();
    expect($("hist-prev").disabled).toBe(true);
    expect($("hist-next").disabled).toBe(false);

    $("hist-next").click();
    await flush();
    await flush();
    expect(lastHistoryQuery(fetch)).toEqual({ limit: "15", offset: "15" });
    expect($("hist-range").textContent).toBe("16–30 of 40");

    $("hist-next").click();
    await flush();
    await flush();
    expect($("hist-range").textContent).toBe("31–40 of 40");
    expect($("hist-next").disabled).toBe(true);

    $("hist-prev").click();
    await flush();
    await flush();
    expect($("hist-range").textContent).toBe("16–30 of 40");
  });
});

describe("admin history: the filters", () => {
  beforeEach(() => vi.resetModules());
  afterEach(tidy);

  it("filters by faculty and by Campus, and goes back to page 1 when the filter changes", async () => {
    const { fetch } = await setup({ total: 40 });
    await openHistory();
    $("hist-next").click();
    await flush();
    await flush();

    pick($("hist-faculty"), "f1");
    await flush();
    await flush();
    expect(lastHistoryQuery(fetch)).toEqual({
      limit: "15",
      offset: "0",
      faculty_id: "f1",
    });

    pick($("hist-faculty"), "campus");
    await flush();
    await flush();
    expect(lastHistoryQuery(fetch).faculty_id).toBe("campus");

    pick($("hist-faculty"), "");
    await flush();
    await flush();
    expect(lastHistoryQuery(fetch)).toEqual({ limit: "15", offset: "0" });
  });

  it("lists every room when no faculty is chosen, and only the faculty's rooms once one is", async () => {
    const { fetch } = await setup();
    await openHistory();
    expect(fetch.mock.calls.map((c) => c[0])).toContain("/api/classrooms");
    expect([...$("hist-room").options].map((o) => o.textContent)).toEqual([
      "All rooms",
      "B110",
      "L2",
    ]);

    pick($("hist-faculty"), "f1");
    await flush();
    await flush();
    expect(fetch.mock.calls.map((c) => c[0])).toContain(
      "/api/classrooms?faculty_id=f1",
    );
  });

  it("filters by one room, and clears the room when the faculty changes", async () => {
    const { fetch } = await setup();
    await openHistory();

    pick($("hist-room"), "r1");
    await flush();
    await flush();
    expect(lastHistoryQuery(fetch).classroom_id).toBe("r1");

    pick($("hist-faculty"), "f1");
    await flush();
    await flush();
    expect($("hist-room").value).toBe("");
    expect(lastHistoryQuery(fetch).classroom_id).toBeUndefined();
  });

  it("filters by status, and All sends no status", async () => {
    const { fetch } = await setup();
    await openHistory();

    pick($("hist-status"), "approved");
    await flush();
    await flush();
    expect(lastHistoryQuery(fetch).status).toBe("approved");

    pick($("hist-status"), "");
    await flush();
    await flush();
    expect(lastHistoryQuery(fetch).status).toBeUndefined();
  });

  it("says so when no booking matches, and Clear filters brings the list back", async () => {
    const { fetch } = await setup({ total: 0 });
    await openHistory();

    expect(rows()).toHaveLength(0);
    expect($("hist-empty").hidden).toBe(false);
    expect($("hist-empty").querySelector("h2").textContent).toBe(
      "No bookings match these filters",
    );

    pick($("hist-status"), "cancelled");
    await flush();
    await flush();
    $("hist-clear").click();
    await flush();
    await flush();

    expect($("hist-status").value).toBe("");
    expect(lastHistoryQuery(fetch)).toEqual({ limit: "15", offset: "0" });
  });

  it("shows an error when the bookings cannot be loaded", async () => {
    await setup({
      routes: { "/api/admin/bookings": () => response({ detail: "x" }, 500) },
    });
    await openHistory();

    expect($("hist-status-line").textContent).toBe(
      "Could not load the bookings. Try again.",
    );
    expect($("hist-status-line").className).toBe("notice notice--error");
  });
});

describe("admin history: cancelling a future approved booking", () => {
  beforeEach(() => vi.resetModules());
  afterEach(tidy);

  it("offers Cancel only on a booking that is approved and has not started", async () => {
    await setup({ total: 2 });
    await openHistory();

    const cancelButtons = rows().map((row) => row.querySelector("button"));
    expect(cancelButtons[0].textContent).toBe("Cancel");
    expect(cancelButtons[1]).toBeNull();
  });

  it("asks first, then cancels, and the list is shown again with the outcome", async () => {
    const { fetch } = await setup({
      total: 2,
      routes: {
        "/api/admin/bookings/b0/cancel": () =>
          response({ id: "b0", status: "cancelled" }),
      },
    });
    await openHistory();

    rows()[0].querySelector("button").click();
    expect(confirms()).toHaveLength(1);
    expect(confirms()[0].textContent).toContain("Event 0");

    confirms()[0].querySelector(".btn-primary").click();
    await flush();
    await flush();

    const post = fetch.mock.calls.find(
      (c) => c[0] === "/api/admin/bookings/b0/cancel",
    );
    expect(post[1].method).toBe("POST");
    expect(JSON.parse(post[1].body)).toEqual({});
    expect($("hist-status-line").textContent).toBe(
      "The booking was cancelled and marked rejected.",
    );
    expect(confirms()).toHaveLength(0);
  });

  it("sends the admin's message with the cancellation, trimmed, and only when one is typed", async () => {
    const { fetch } = await setup({
      total: 2,
      routes: {
        "/api/admin/bookings/b0/cancel": () =>
          response({ id: "b0", status: "rejected" }),
      },
    });
    await openHistory();

    rows()[0].querySelector("button").click();
    const box = confirms()[0].querySelector("textarea");
    expect(box.maxLength).toBe(100);
    box.value = "  Sala e necesară pentru un examen.  ";
    confirms()[0].querySelector(".btn-primary").click();
    await flush();
    await flush();

    const post = fetch.mock.calls.find(
      (c) => c[0] === "/api/admin/bookings/b0/cancel",
    );
    expect(JSON.parse(post[1].body)).toEqual({
      message: "Sala e necesară pentru un examen.",
    });
  });

  it("keeps the booking when the admin chooses to keep it", async () => {
    const { fetch } = await setup({ total: 2 });
    await openHistory();

    rows()[0].querySelector("button").click();
    confirms()[0].querySelector(".btn:not(.btn-primary)").click();

    expect(confirms()).toHaveLength(0);
    expect(
      fetch.mock.calls.some((c) => c[0] === "/api/admin/bookings/b0/cancel"),
    ).toBe(false);
  });

  it("explains when the booking can no longer be cancelled", async () => {
    await setup({
      total: 2,
      routes: {
        "/api/admin/bookings/b0/cancel": () =>
          response({ detail: "started" }, 409),
      },
    });
    await openHistory();

    rows()[0].querySelector("button").click();
    confirms()[0].querySelector(".btn-primary").click();
    await flush();
    await flush();

    expect($("hist-status-line").textContent).toBe(
      "This booking can no longer be cancelled.",
    );
    expect($("hist-status-line").className).toBe("notice notice--error");
  });

  it("explains any other failure in general words", async () => {
    await setup({
      total: 2,
      routes: {
        "/api/admin/bookings/b0/cancel": () => response({ detail: "x" }, 500),
      },
    });
    await openHistory();

    rows()[0].querySelector("button").click();
    confirms()[0].querySelector(".btn-primary").click();
    await flush();
    await flush();

    expect($("hist-status-line").textContent).toBe(
      "Something went wrong. Try again.",
    );
  });
});

describe("admin history: the language and a page without the list", () => {
  beforeEach(() => vi.resetModules());
  afterEach(tidy);

  it("writes the status words again in the new language", async () => {
    await setup({ total: 1 });
    await openHistory();
    expect(rows()[0].querySelectorAll("td")[4].textContent).toBe("Approved");

    window.UniSpaceI18n.setLanguage("ro");
    await flush();
    await flush();

    expect(rows()[0].querySelectorAll("td")[4].textContent).toBe("Aprobată");
    window.UniSpaceI18n.setLanguage("en");
  });

  it("does nothing when the page has no history panel", async () => {
    mountPage("pages/admin/index.html");
    $("panel-history").remove();
    await loadI18n("en");
    await loadScript("js/api.js");
    const fetch = stubFetch({ "/api/admin/bookings": historyAnswer([]) });
    await loadScript("js/pages/admin-history.js");
    await flush();

    expect(fetch).not.toHaveBeenCalled();
  });
});

describe("admin history: a load that works again clears the error", () => {
  beforeEach(() => vi.resetModules());
  afterEach(tidy);

  it("clears the error once the bookings load again", async () => {
    let calls = 0;
    const answer = historyAnswer(bookings(2));
    await setup({
      routes: {
        "/api/admin/bookings": (url) => {
          calls += 1;
          return calls === 1 ? response({ detail: "x" }, 500) : answer(url);
        },
      },
    });
    await openHistory();
    expect($("hist-status-line").className).toBe("notice notice--error");

    $("hist-status").value = "approved";
    $("hist-status").dispatchEvent(new Event("change"));
    await flush();
    await flush();

    expect($("hist-status-line").textContent).toBe("");
    expect(rows()).toHaveLength(2);
  });
});
