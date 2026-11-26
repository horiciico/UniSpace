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

// The Move Activity dialog (js/move.js) on the timetable page: four steps, live modules, the move.
const NOW = new Date(2026, 10, 20, 10, 0); // Friday 20 Nov 2026

const RECURRING = {
  id: "a1",
  title: "Algebra",
  activity_type: "COURSE",
  day_of_week: 1,
  start_time: "08:00",
  end_time: "09:30",
  room_name: "A1",
  is_recurring: true,
  specific_date: null,
  group_ids: ["g1"],
  groups: ["332CA"],
};
const ONE_OFF = {
  id: "a2",
  title: "Colocviu",
  activity_type: "EXAM",
  day_of_week: 2,
  start_time: "09:40",
  end_time: "11:10",
  room_name: "B2",
  is_recurring: false,
  specific_date: "2026-11-24",
  group_ids: [],
  groups: [],
};
const FREE_MODULE = {
  start_time: "09:40",
  end_time: "11:10",
  available: true,
  conflict_reason: null,
  free_classrooms: [
    {
      id: "r1",
      name: "Sala 1",
      capacity: 30,
      has_projector: true,
      is_field_verified: true,
    },
    {
      id: "r2",
      name: "Lab",
      capacity: null,
      has_projector: null,
      is_field_verified: false,
    },
  ],
};
const BUSY_MODULE = {
  start_time: "08:00",
  end_time: "09:30",
  available: false,
  conflict_reason: "Professor busy: Seminar 08:00-09:30.",
  free_classrooms: [],
};

const $ = (id) => document.getElementById(id);

async function setup(routes = {}) {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  mountPage("pages/student/timetable.html");
  await loadI18n("en");
  await loadScript("components/toast.js");
  // jsdom has no dialog.close(): a stand-in that clears the open attribute, as the browser does.
  const dialog = $("mv-dialog");
  dialog.close = () => dialog.removeAttribute("open");
  await loadScript("js/api.js");
  await loadScript("js/move.js");
  const fetch = stubFetch({
    "/api/professors/me/movable-activities": () =>
      response({ linked: true, activities: [RECURRING, ONE_OFF] }),
    "/api/professors/me/availability": () =>
      response({
        date: "2026-11-23",
        professor_id: "p1",
        modules: [BUSY_MODULE, FREE_MODULE],
      }),
    "/api/professors/me/activities/a1/move": () =>
      response({ id: "n1", original_date: "2026-11-23", date: "2026-11-24" }),
    ...routes,
  });
  return fetch;
}

async function openDialog(onMoved) {
  window.UniSpaceMove.open(onMoved);
  await flush();
}

// Walks the dialog to step 3 with the recurring activity, its Monday, and the Tuesday.
async function toStep3(onMoved) {
  await openDialog(onMoved);
  $("mv-next-1").click();
  $("mv-new").value = "2026-11-24";
  $("mv-next-2").click();
  await flush();
}

const visibleStep = () => [1, 2, 3, 4].filter((n) => !$(`mv-step-${n}`).hidden);

describe("move.js: opening and step 1", () => {
  beforeEach(() => {
    vi.resetModules();
    delete window.UniSpaceMove;
  });

  it("lists the movable activities and defaults the date to the next day of the weekday", async () => {
    await setup();

    await openDialog();

    const options = [...$("mv-activity").options].map((o) => o.textContent);
    expect(options[0]).toBe("Algebra · 332CA · Mon 08:00–09:30 · A1");
    expect($("mv-activity").value).toBe("a1");
    expect($("mv-original").value).toBe("2026-11-23");
    expect($("mv-original").min).toBe("2026-11-20");
    expect(visibleStep()).toEqual([1]);
    expect($("mv-empty").hidden).toBe(true);
    expect($("mv-dialog").getAttribute("open")).toBe("");
  });

  it("shows a dash for an activity with no group", async () => {
    await setup();

    await openDialog();
    $("mv-activity").value = "a2";
    $("mv-activity").dispatchEvent(new Event("change"));

    const second = [...$("mv-activity").options][1];
    expect(second.textContent).toBe("Colocviu · – · Tue 09:40–11:10 · B2");
  });

  it("defaults a one-off to its own date", async () => {
    await setup();

    await openDialog();
    $("mv-activity").value = "a2";
    $("mv-activity").dispatchEvent(new Event("change"));

    expect($("mv-original").value).toBe("2026-11-24");
  });

  it("ignores a change when there is nothing to choose", async () => {
    await setup({
      "/api/professors/me/movable-activities": () =>
        response({ linked: true, activities: [] }),
    });

    await openDialog();
    $("mv-activity").dispatchEvent(new Event("change"));

    expect($("mv-original").value).toBe("");
  });

  it("says there is nothing to move when the account has no activities", async () => {
    await setup({
      "/api/professors/me/movable-activities": () =>
        response({ linked: false, activities: [] }),
    });

    await openDialog();

    expect($("mv-empty").hidden).toBe(false);
    expect($("mv-next-1").disabled).toBe(true);
  });

  it("shows the timetable error when the list cannot be loaded", async () => {
    await setup({
      "/api/professors/me/movable-activities": () =>
        response({ detail: "x" }, 500),
    });

    await openDialog();

    expect($("mv-error").hidden).toBe(false);
    expect($("mv-error-text").textContent).toBe(
      "Could not load the timetable. Try again.",
    );
    expect($("mv-next-1").disabled).toBe(true);
  });

  it("opens with the open attribute where showModal is not supported", async () => {
    await setup();

    await openDialog();

    expect($("mv-dialog").showModal).toBeUndefined();
    expect($("mv-dialog").open).toBe(true);
  });

  it("uses showModal where the browser has it", async () => {
    await setup();
    $("mv-dialog").showModal = vi.fn();

    await openDialog();

    expect($("mv-dialog").showModal).toHaveBeenCalled();
  });

  it("refuses to go on without an activity", async () => {
    await setup({
      "/api/professors/me/movable-activities": () =>
        response({ linked: true, activities: [] }),
    });
    await openDialog();
    $("mv-next-1").disabled = false;

    $("mv-next-1").click();

    expect($("mv-error-text").textContent).toBe("Choose an activity.");
  });

  it("refuses to go on without an original date", async () => {
    await setup();
    await openDialog();
    $("mv-original").value = "";

    $("mv-next-1").click();

    expect($("mv-error-text").textContent).toBe("Choose a date.");
  });

  it("refuses a date on another weekday than the activity", async () => {
    await setup();
    await openDialog();
    $("mv-original").value = "2026-11-24";

    $("mv-next-1").click();

    expect($("mv-error-text").textContent).toBe(
      "The activity does not take place on that day.",
    );
    expect(visibleStep()).toEqual([1]);
  });

  it("goes to step 2 with the original date as the new date", async () => {
    await setup();
    await openDialog();

    $("mv-next-1").click();

    expect(visibleStep()).toEqual([2]);
    expect($("mv-new").value).toBe("2026-11-23");
    expect($("mv-new").min).toBe("2026-11-20");
    expect($("mv-pill-2").className).toBe("pill pill--info");
    expect($("mv-pill-1").className).toBe("pill");
  });
});

describe("move.js: step 2 and step 3 (the modules)", () => {
  beforeEach(() => {
    vi.resetModules();
    delete window.UniSpaceMove;
  });

  it("goes back from step 2 to step 1", async () => {
    await setup();
    await openDialog();
    $("mv-next-1").click();

    $("mv-back-2").click();

    expect(visibleStep()).toEqual([1]);
  });

  it("refuses an empty new date and a date in the past", async () => {
    await setup();
    await openDialog();
    $("mv-next-1").click();

    $("mv-new").value = "";
    $("mv-next-2").click();
    expect($("mv-error-text").textContent).toBe("Choose a date.");

    $("mv-new").value = "2026-11-19";
    $("mv-next-2").click();
    expect($("mv-error-text").textContent).toBe(
      "The new date cannot be in the past.",
    );
    expect(visibleStep()).toEqual([2]);
  });

  it("asks the availability of the new date, with the groups and the activity itself excluded", async () => {
    const fetch = await setup();
    await toStep3();

    const url = fetch.mock.calls.find(([u]) => u.includes("availability"))[0];
    expect(url).toContain("date=2026-11-24");
    expect(url).toContain("group_ids=g1");
    expect(url).toContain("exclude_activity_id=a1");
    expect(visibleStep()).toEqual([3]);
  });

  it("shows each module: a free one can be chosen, a busy one is disabled with the reason", async () => {
    await setup();
    await toStep3();

    const [busy, free] = [...$("mv-modules").querySelectorAll("button")];
    expect(busy.disabled).toBe(true);
    expect(busy.textContent).toContain(
      "Busy: Professor busy: Seminar 08:00-09:30.",
    );
    expect(free.disabled).toBe(false);
    expect(free.textContent).toBe("09:40–11:10Free");
    expect($("mv-next-3").disabled).toBe(true);
  });

  it("marks the chosen module and enables the next step", async () => {
    await setup();
    await toStep3();

    const free = $("mv-modules").querySelectorAll("button")[1];
    free.click();

    expect(free.getAttribute("aria-pressed")).toBe("true");
    expect(
      $("mv-modules")
        .querySelectorAll("button")[0]
        .getAttribute("aria-pressed"),
    ).toBe("false");
    expect($("mv-next-3").disabled).toBe(false);
  });

  it("refuses to go on without a module", async () => {
    await setup();
    await toStep3();

    $("mv-next-3").disabled = false;
    $("mv-next-3").click();

    expect($("mv-error-text").textContent).toBe("Choose a free module.");
    expect(visibleStep()).toEqual([3]);
  });

  it("goes back from step 3 to step 2", async () => {
    await setup();
    await toStep3();

    $("mv-back-3").click();

    expect(visibleStep()).toEqual([2]);
  });

  it("shows an error when the modules cannot be loaded", async () => {
    await setup({
      "/api/professors/me/availability": () => response({ detail: "x" }, 500),
    });
    await toStep3();

    expect($("mv-error-text").textContent).toBe(
      "Could not load the modules. Try again.",
    );
    expect($("mv-module-status").textContent).toBe("");
  });

  it("ignores a late answer for an earlier date", async () => {
    const first = deferred();
    const second = deferred();
    let calls = 0;
    await setup({
      "/api/professors/me/availability": () => {
        calls += 1;
        return calls === 1 ? first.promise : second.promise;
      },
    });
    await toStep3();
    $("mv-back-3").click();
    $("mv-next-2").click();
    await flush();

    second.resolve(response({ date: "2026-11-24", modules: [FREE_MODULE] }));
    await flush();
    first.resolve(response({ date: "2026-11-23", modules: [BUSY_MODULE] }));
    await flush();

    expect($("mv-modules").querySelectorAll("button")).toHaveLength(1);
    expect($("mv-modules").textContent).toContain("09:40–11:10");
  });

  it("ignores a late failure for an earlier date", async () => {
    const first = deferred();
    const second = deferred();
    let calls = 0;
    await setup({
      "/api/professors/me/availability": () => {
        calls += 1;
        return calls === 1 ? first.promise : second.promise;
      },
    });
    await toStep3();
    $("mv-back-3").click();
    $("mv-next-2").click();
    await flush();

    second.resolve(response({ date: "2026-11-24", modules: [FREE_MODULE] }));
    await flush();
    first.resolve(response({ detail: "x" }, 500));
    await flush();

    expect($("mv-error").hidden).toBe(true);
    expect($("mv-modules").querySelectorAll("button")).toHaveLength(1);
  });
});

describe("move.js: step 4 (the room) and the move", () => {
  beforeEach(() => {
    vi.resetModules();
    delete window.UniSpaceMove;
  });

  async function toStep4(onMoved) {
    await toStep3(onMoved);
    $("mv-modules").querySelectorAll("button")[1].click();
    $("mv-next-3").click();
    await flush();
  }

  it("lists only the free rooms of the module, with their seats", async () => {
    await setup();
    await toStep4();

    const options = [...$("mv-room").options].map((o) => o.textContent);
    expect(options).toEqual(["Sala 1 · 30 seats", "Lab"]);
    expect($("mv-noroom").hidden).toBe(true);
    expect($("mv-submit").disabled).toBe(false);
    expect(visibleStep()).toEqual([4]);
  });

  it("says so, and blocks the move, when no room is free", async () => {
    await setup({
      "/api/professors/me/availability": () =>
        response({ modules: [{ ...FREE_MODULE, free_classrooms: [] }] }),
    });
    await toStep3();
    $("mv-modules").querySelectorAll("button")[0].click();
    $("mv-next-3").click();

    expect($("mv-noroom").hidden).toBe(false);
    expect($("mv-submit").disabled).toBe(true);
  });

  it("goes back from step 4 to step 3", async () => {
    await setup();
    await toStep4();

    $("mv-back-4").click();

    expect(visibleStep()).toEqual([3]);
  });

  it("refuses to submit without a room", async () => {
    await setup();
    await toStep4();

    $("mv-room").textContent = "";
    $("mv-submit").disabled = false;
    $("mv-submit").click();

    expect($("mv-error-text").textContent).toBe("Choose a room.");
  });

  it("posts the move, closes, shows the toast and calls back", async () => {
    const fetch = await setup();
    const onMoved = vi.fn();
    await toStep4(onMoved);

    $("mv-submit").click();
    await flush();

    const move = fetch.mock.calls.find(([u]) => u.includes("/move"));
    expect(move[1].method).toBe("POST");
    expect(JSON.parse(move[1].body)).toEqual({
      original_date: "2026-11-23",
      new_date: "2026-11-24",
      start_time: "09:40",
      end_time: "11:10",
      new_classroom_id: "r1",
    });
    expect($("mv-dialog").open).toBe(false);
    expect($("toast").textContent).toBe("The activity has been moved.");
    expect(onMoved).toHaveBeenCalledTimes(1);
    expect($("mv-submit").disabled).toBe(false);
  });

  it("moves without a callback when none was given", async () => {
    await setup();
    window.UniSpaceMove.open();
    await flush();
    $("mv-next-1").click();
    $("mv-new").value = "2026-11-24";
    $("mv-next-2").click();
    await flush();
    $("mv-modules").querySelectorAll("button")[1].click();
    $("mv-next-3").click();
    await flush();

    $("mv-submit").click();
    await flush();

    expect($("toast").textContent).toBe("The activity has been moved.");
  });

  it("shows the reason the backend gives when the move is refused", async () => {
    await setup({
      "/api/professors/me/activities/a1/move": () =>
        response(
          { detail: "The room is taken from 09:40 to 11:10 by Exam." },
          409,
        ),
    });
    await toStep4();

    $("mv-submit").click();
    await flush();

    expect($("mv-error-text").textContent).toBe(
      "The activity could not be moved. The room is taken from 09:40 to 11:10 by Exam.",
    );
    expect($("mv-dialog").open).toBe(true);
    expect($("mv-submit").disabled).toBe(false);
  });

  it("shows only the words when the answer has no readable reason", async () => {
    await setup({
      "/api/professors/me/activities/a1/move": () =>
        response({ detail: [{ msg: "x" }] }, 422),
    });
    await toStep4();

    $("mv-submit").click();
    await flush();

    expect($("mv-error-text").textContent).toBe(
      "The activity could not be moved.",
    );
  });

  it("shows the words when the answer has no body", async () => {
    await setup({
      "/api/professors/me/activities/a1/move": () => ({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error("not json")),
      }),
    });
    await toStep4();

    $("mv-submit").click();
    await flush();

    expect($("mv-error-text").textContent).toBe(
      "The activity could not be moved.",
    );
  });
});

describe("move.js: closing and language", () => {
  beforeEach(() => {
    vi.resetModules();
    delete window.UniSpaceMove;
  });

  it("cancel closes the dialog", async () => {
    await setup();
    await openDialog();

    $("mv-cancel").click();

    expect($("mv-dialog").open).toBe(false);
  });

  it("closes an open dialog when the language changes, and leaves a closed one alone", async () => {
    await setup();
    document.dispatchEvent(new Event("unispace:langchange"));
    await openDialog();

    document.dispatchEvent(new Event("unispace:langchange"));

    expect($("mv-dialog").open).toBe(false);
  });

  it("does nothing on a page without the dialog", async () => {
    document.body.innerHTML = "";
    vi.resetModules();
    await loadScript("js/move.js");

    expect(window.UniSpaceMove).toBeUndefined();
  });
});
