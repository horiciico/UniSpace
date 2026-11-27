import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  deferred,
  flush,
  loadI18n,
  loadScript,
  mountPage,
  response,
  stubFetch,
} from "../helpers.js";

// Admin: the Data import tab (D-031, C-012).
const URL_IMPORT = "/api/admin/data-import";
const IDLE = {
  status: "idle",
  step: null,
  started_at: null,
  finished_at: null,
  result: null,
};
const RUNNING = { ...IDLE, status: "running", step: "schedules" };
const RESULT = {
  schedule: {
    inserted: 2,
    updated: 1,
    unchanged: 5,
    restored: 1,
    cancelled: 3,
    kept_edited: 4,
    unread_entries: 6,
  },
  professors: { stored: 7 },
  problems: [
    { faculty: "ing", kind: "download" },
    { faculty: null, kind: "professors_save" },
  ],
  clashes: [
    {
      date: "2026-12-07",
      start: "09:00",
      end: "10:00",
      room: "B110",
      what: "booking",
      title: "<b>Club</b>",
      class_start: "08:00",
      class_end: "09:30",
      class_room: "B110",
      reasons: ["room"],
    },
    {
      date: "2026-12-08",
      start: "09:00",
      end: "10:00",
      room: "B111",
      what: "exam",
      title: "Algebra",
      class_start: "09:40",
      class_end: "11:10",
      class_room: "B112",
      reasons: ["professor", "group"],
    },
  ],
};
const DONE = {
  ...IDLE,
  status: "done",
  finished_at: "2026-11-27T10:00:00+00:00",
  result: RESULT,
};

const $ = (id) => document.getElementById(id);
const texts = (id) => [...$(id).children].map((node) => node.textContent);

let net; // the fetch stub of the current test
const isPost = () => net.mock.calls.at(-1)[1]?.method === "POST";

async function setup(routes = {}, language = "en") {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  mountPage("pages/admin/index.html");
  await loadI18n(language);
  window.UniSpaceI18n.setLanguage(language);
  window.UniSpaceI18n.apply(document.body);
  await loadScript("js/api.js");
  net = stubFetch({
    "/api/admin/bookings/pending": () => response([]),
    "/api/admin/bookings": () =>
      response({ items: [], total: 0, limit: 15, offset: 0 }),
    [URL_IMPORT]: () => response(IDLE),
    ...routes,
  });
  await loadScript("js/pages/admin-history.js");
  await loadScript("js/pages/admin-import.js");
  return { fetch: net };
}

// A GET route that answers each state in turn and then repeats the last one.
function inTurn(...answers) {
  let index = 0;
  return () => {
    if (isPost()) return response(RUNNING, 202);
    const answer = answers[Math.min(index, answers.length - 1)];
    index += 1;
    return typeof answer === "function" ? answer() : response(answer);
  };
}

async function open() {
  $("tab-import").click();
  await flush();
}

const posts = (fetch) =>
  fetch.mock.calls.filter((call) => call[1] && call[1].method === "POST");

async function tick() {
  await vi.advanceTimersByTimeAsync(3000);
  await flush();
}

describe("admin data import", () => {
  beforeEach(() => vi.resetModules());
  afterEach(() => vi.useRealTimers());

  it("asks nothing until the tab is opened, then shows the idle panel", async () => {
    const { fetch } = await setup();
    const asked = () =>
      fetch.mock.calls.filter((call) => call[0] === URL_IMPORT).length;
    expect(asked()).toBe(0);

    await open();

    expect(asked()).toBe(1);
    expect($("panel-import").hidden).toBe(false);
    expect($("panel-pending").hidden).toBe(true);
    expect($("imp-start").disabled).toBe(false);
    expect($("imp-status").hidden).toBe(true);
    expect($("imp-result").hidden).toBe(true);
  });

  it("starts a run, follows its steps and shows the result", async () => {
    const { fetch } = await setup({
      [URL_IMPORT]: inTurn(
        IDLE,
        RUNNING,
        { ...RUNNING, step: "professors" },
        DONE,
      ),
    });
    await open();

    $("imp-start").click();
    await flush();

    expect(posts(fetch)).toHaveLength(1);
    expect($("imp-start").disabled).toBe(true);
    expect($("imp-status").textContent).toBe(
      "Import running: downloading the schedules.",
    );
    await tick();
    expect($("imp-status").textContent).toBe(
      "Import running: importing the professors.",
    );
    await tick();
    expect($("imp-status").textContent).toContain("Import finished");
    expect($("imp-start").disabled).toBe(false);
    expect($("imp-result").hidden).toBe(false);
  });

  it("lists the counts, the problems and the clashes as text", async () => {
    await setup({ [URL_IMPORT]: () => response(DONE) });

    await open();

    expect(texts("imp-counts")).toEqual([
      "Classes added: 2",
      "Classes updated: 1",
      "Classes unchanged: 5",
      "Classes restored: 1",
      "Classes cancelled because they left the feed: 3",
      "Classes kept as edited here: 4",
      "Feed entries that could not be read: 6",
      "Professors saved: 7",
    ]);
    expect(texts("imp-problems")).toEqual([
      "ing: the schedule was not downloaded; its classes were left as they were.",
      "Some professors could not be saved.",
    ]);
    const rows = [...$("imp-clashes").querySelectorAll("tr")].map((row) =>
      [...row.children].map((cell) => cell.textContent),
    );
    expect(rows).toEqual([
      [
        "2026-12-07 09:00–10:00",
        "B110",
        "Booking: <b>Club</b>",
        "B110, 08:00–09:30",
        "room",
      ],
      [
        "2026-12-08 09:00–10:00",
        "B111",
        "Exam: Algebra",
        "B112, 09:40–11:10",
        "professor, group",
      ],
    ]);
    expect($("imp-clashes").querySelector("b")).toBeNull();
    expect($("imp-no-clashes").hidden).toBe(true);
  });

  it("says when there is no problem and no clash", async () => {
    await setup({
      [URL_IMPORT]: () =>
        response({
          ...DONE,
          result: { ...RESULT, problems: [], clashes: [] },
        }),
    });

    await open();

    expect($("imp-problems-block").hidden).toBe(true);
    expect($("imp-clashes-wrap").hidden).toBe(true);
    expect($("imp-no-clashes").hidden).toBe(false);
  });

  it("shows a run that has not reached its first step", async () => {
    await setup({
      [URL_IMPORT]: () => response({ ...RUNNING, step: null }),
    });

    await open();

    expect($("imp-status").textContent).toBe(
      "Import running: connecting to the source.",
    );
  });

  it("says where a run failed", async () => {
    await setup({
      [URL_IMPORT]: () =>
        response({ ...IDLE, status: "failed", step: "timetable" }),
    });

    await open();

    expect($("imp-status").textContent).toBe(
      "The import failed while saving the timetable. Nothing was deleted. Try again.",
    );
    expect($("imp-status").className).toContain("notice--error");
    expect($("imp-start").disabled).toBe(false);
  });

  it("says when a run failed before its first step", async () => {
    await setup({
      [URL_IMPORT]: () => response({ ...IDLE, status: "failed" }),
    });

    await open();

    expect($("imp-status").textContent).toContain("connecting to the source");
  });

  it("follows a run that is already going when the start is refused", async () => {
    let started = false;
    await setup({
      [URL_IMPORT]: () => {
        if (isPost()) {
          started = true;
          return response({ detail: "An import is already running." }, 409);
        }
        return response(started ? RUNNING : IDLE);
      },
    });
    await open();

    $("imp-start").click();
    await flush();

    expect($("imp-status").textContent).toContain("Import running");
    expect($("imp-start").disabled).toBe(true);
  });

  it("says when the run could not be started", async () => {
    await setup({
      [URL_IMPORT]: () =>
        isPost() ? response({ detail: "x" }, 500) : response(IDLE),
    });
    await open();

    $("imp-start").click();
    await flush();

    expect($("imp-status").textContent).toBe(
      "The import could not be started. Try again.",
    );
    expect($("imp-start").disabled).toBe(false);
  });

  it("keeps asking after a failed check of a running import", async () => {
    await setup({
      [URL_IMPORT]: inTurn(RUNNING, () => response({ detail: "x" }, 500), DONE),
    });
    await open();

    await tick();
    expect($("imp-status").textContent).toBe(
      "Could not read the import's state. Trying again.",
    );
    await tick();

    expect($("imp-result").hidden).toBe(false);
  });

  it("says when the state cannot be read at all", async () => {
    await setup({ [URL_IMPORT]: () => response({ detail: "x" }, 500) });

    await open();

    expect($("imp-status").textContent).toBe(
      "Could not read the import's state. Trying again.",
    );
  });

  it("ignores the answers of an older check", async () => {
    const first = deferred();
    const second = deferred();
    let asked = 0;
    await setup({
      [URL_IMPORT]: () => {
        asked += 1;
        if (asked === 1) return first.promise;
        if (asked === 2) return second.promise;
        return response(DONE);
      },
    });
    await open();
    await open();
    await open();

    first.resolve(response(RUNNING));
    second.resolve(response({ detail: "x" }, 500));
    await flush();

    expect($("imp-status").textContent).toContain("Import finished");
  });

  it("writes the result again in the other language", async () => {
    await setup({ [URL_IMPORT]: () => response(DONE) });
    window.UniSpaceI18n.setLanguage("ro");
    await flush();
    expect($("imp-status").hidden).toBe(true); // nothing loaded yet

    await open();

    expect(texts("imp-counts")[0]).toBe("Ore adăugate: 2");
    window.UniSpaceI18n.setLanguage("en");
    await flush();
    expect(texts("imp-counts")[0]).toBe("Classes added: 2");
  });
});
