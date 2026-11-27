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

// The Schedule Exam dialog (js/exam.js) on the timetable page: subject, groups, date, half-hour
// times with a live check, a free room.
const NOW = new Date(2026, 10, 20, 10, 0); // Friday 20 Nov 2026

const SUBJECTS = [
  {
    name: "Retele",
    groups: [{ id: "g3", name: "3C" }],
  },
  {
    name: "Sisteme de Operare",
    groups: [
      { id: "g1", name: "3A" },
      { id: "g2", name: "3B" },
    ],
  },
];

const ROOMS = [
  { id: "r1", name: "Sala 1", capacity: 30 },
  { id: "r2", name: "Lab", capacity: null },
];

const FREE = {
  available: true,
  conflict_reason: null,
  exam_session: true,
  free_classrooms: ROOMS,
};

const CHECK = "/api/professors/me/availability/interval";
const SAVE = "/api/professors/me/exams";

const $ = (id) => document.getElementById(id);
const options = (id) => [...$(id).options].map((o) => o.textContent);
const boxes = () => [...$("ex-groups").querySelectorAll("input")];
const change = (element) =>
  element.dispatchEvent(new Event("change", { bubbles: true }));

async function setup(routes = {}, language = "en") {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  mountPage("pages/student/timetable.html");
  await loadI18n(language);
  window.UniSpaceI18n.setLanguage(language);
  window.UniSpaceI18n.apply(document.body);
  const toast = vi.fn();
  window.UniSpaceUI = { toast };
  const fetch = stubFetch({
    "/api/professors/me/subjects": () =>
      response({ linked: true, subjects: SUBJECTS }),
    [CHECK]: () => response(FREE),
    [SAVE]: () => response({ id: "e1" }, 201),
    ...routes,
  });
  await loadScript("js/api.js");
  await loadScript("js/exam.js");
  return { fetch, toast };
}

async function open(onDone) {
  window.UniSpaceExam.open(onDone);
  await flush();
}

// Chooses the second subject, its groups and a date, then waits for the check.
async function choose({ groups = [0, 1], date = "2026-12-08" } = {}) {
  $("ex-subject").value = "Sisteme de Operare";
  change($("ex-subject"));
  groups.forEach((index) => {
    boxes()[index].checked = true;
    change(boxes()[index]);
  });
  $("ex-date").value = date;
  change($("ex-date"));
  await flush();
}

const checks = (fetch) =>
  fetch.mock.calls.filter((call) => call[0].startsWith(CHECK));
const saves = (fetch) =>
  fetch.mock.calls.filter((call) => call[0].startsWith(SAVE));

function submit() {
  $("ex-form").dispatchEvent(
    new Event("submit", { cancelable: true, bubbles: true }),
  );
}

describe("schedule exam dialog", () => {
  beforeEach(() => vi.resetModules());
  afterEach(() => vi.useRealTimers());

  it("lists the professor's subjects and the chosen subject's groups", async () => {
    await setup();

    await open();

    expect(options("ex-subject")).toEqual(["Retele", "Sisteme de Operare"]);
    expect(boxes()).toHaveLength(1);
    $("ex-subject").value = "Sisteme de Operare";
    change($("ex-subject"));
    expect($("ex-groups").textContent).toContain("3A");
    expect($("ex-groups").textContent).toContain("3B");
    expect($("ex-submit").disabled).toBe(true);
    expect($("ex-status").textContent).toBe(
      "Choose at least one group and a date.",
    );
  });

  it("offers half-hour times from 08:00 to 22:00, at least one hour apart", async () => {
    await setup();
    await open();

    expect(options("ex-start")[0]).toBe("08:00");
    expect(options("ex-start")).toHaveLength(27); // 08:00 ... 21:00
    expect($("ex-end").value).toBe("09:00");
    expect(options("ex-end")[0]).toBe("09:00");
    expect(options("ex-end").at(-1)).toBe("22:00");

    $("ex-start").value = "20:30";
    change($("ex-start"));

    expect(options("ex-end")).toEqual(["21:30", "22:00"]);
    expect($("ex-end").value).toBe("21:30");
  });

  it("keeps the chosen end when the start still leaves an hour before it", async () => {
    await setup();
    await open();
    $("ex-end").value = "12:00";

    $("ex-start").value = "10:00";
    change($("ex-start"));

    expect($("ex-end").value).toBe("12:00");
  });

  it("checks the chosen groups, date and times, and lists the free rooms", async () => {
    const { fetch } = await setup();
    await open();

    await choose();

    const url = checks(fetch).at(-1)[0];
    expect(queryOf(url)).toMatchObject({
      date: "2026-12-08",
      start_time: "08:00",
      end_time: "09:00",
    });
    expect(url).toContain("group_ids=g1&group_ids=g2");
    expect($("ex-status").textContent).toBe(
      "The professor and the groups are free.",
    );
    expect(options("ex-room")).toEqual(["Sala 1 · 30 seats", "Lab"]);
    expect($("ex-submit").disabled).toBe(false);
  });

  it.each([
    [
      { ...FREE, exam_session: false },
      "That date is not in an exam session for these groups.",
    ],
    [
      { ...FREE, available: false, conflict_reason: "Group 3A busy: X." },
      "Not free: Group 3A busy: X.",
    ],
    [{ ...FREE, free_classrooms: [] }, "No room is free for these times."],
  ])("says why the exam cannot be scheduled", async (answer, message) => {
    await setup({ [CHECK]: () => response(answer) });
    await open();

    await choose();

    expect($("ex-status").textContent).toBe(message);
    expect($("ex-submit").disabled).toBe(true);
  });

  it("refuses a past date without asking the server", async () => {
    const { fetch } = await setup();
    await open();

    await choose({ date: "2026-11-19" });

    expect(checks(fetch)).toHaveLength(0);
    expect($("ex-status").textContent).toBe(
      "The exam date cannot be in the past.",
    );
  });

  it("says when the check fails", async () => {
    await setup({ [CHECK]: () => response({ detail: "x" }, 500) });
    await open();

    await choose();

    expect($("ex-error-text").textContent).toBe(
      "Could not check what is free. Try again.",
    );
    expect($("ex-submit").disabled).toBe(true);
  });

  it("keeps only the answer to the latest choice", async () => {
    const first = deferred();
    const second = deferred();
    let asked = 0;
    await setup({
      [CHECK]: () => (++asked === 1 ? first.promise : second.promise),
    });
    await open();
    await choose({ groups: [0] });
    $("ex-end").value = "11:00";
    change($("ex-end"));

    second.resolve(response(FREE));
    await flush();
    first.resolve(response({ ...FREE, exam_session: false }));
    await flush();

    expect($("ex-status").textContent).toBe(
      "The professor and the groups are free.",
    );
  });

  it("ignores the failure of an older check", async () => {
    const first = deferred();
    let asked = 0;
    await setup({
      [CHECK]: () => (++asked === 1 ? first.promise : response(FREE)),
    });
    await open();
    await choose({ groups: [0] });
    $("ex-end").value = "11:00";
    change($("ex-end"));
    await flush();

    first.resolve(response({ detail: "x" }, 500));
    await flush();

    expect($("ex-error").hidden).toBe(true);
  });

  it("schedules the exam, says so, closes and reloads the timetable", async () => {
    const { fetch, toast } = await setup();
    const done = vi.fn();
    await open(done);
    await choose();
    $("ex-room").value = "r2";

    submit();
    await flush();

    expect(JSON.parse(saves(fetch)[0][1].body)).toEqual({
      subject_name: "Sisteme de Operare",
      group_ids: ["g1", "g2"],
      exam_date: "2026-12-08",
      start_time: "08:00",
      end_time: "09:00",
      classroom_id: "r2",
    });
    expect(toast).toHaveBeenCalledWith("Exam scheduled.");
    expect(done).toHaveBeenCalled();
    expect($("ex-dialog").hasAttribute("open")).toBe(false);
  });

  it("does not send before a free room is known", async () => {
    const { fetch } = await setup();
    await open();

    submit();
    await flush();

    expect(saves(fetch)).toHaveLength(0);
  });

  it.each([
    [{ detail: "Room busy: X." }, "The exam was not scheduled. Room busy: X."],
    [{ detail: [{ msg: "bad" }] }, "The exam was not scheduled."],
  ])("keeps the form and says why a save failed", async (answer, message) => {
    await setup({ [SAVE]: () => response(answer, 409) });
    await open();
    await choose();

    submit();
    await flush();

    expect($("ex-error-text").textContent).toBe(message);
    expect($("ex-dialog").hasAttribute("open")).toBe(true);
    expect($("ex-submit").disabled).toBe(false);
  });

  it("says when there is no subject to schedule", async () => {
    await setup({
      "/api/professors/me/subjects": () =>
        response({ linked: true, subjects: [] }),
    });

    await open();

    expect($("ex-empty").hidden).toBe(false);
    expect($("ex-submit").disabled).toBe(true);
  });

  it("says when the subjects cannot be loaded", async () => {
    await setup({
      "/api/professors/me/subjects": () => response({ detail: "x" }, 500),
    });

    await open();

    expect($("ex-error-text").textContent).toBe(
      "Could not load your subjects. Try again.",
    );
  });

  it("closes on Cancel and on a language change", async () => {
    await setup();
    await open();
    $("ex-cancel").click();
    expect($("ex-dialog").hasAttribute("open")).toBe(false);

    await open();
    window.UniSpaceI18n.setLanguage("ro");
    await flush();

    expect($("ex-dialog").hasAttribute("open")).toBe(false);
    window.UniSpaceI18n.setLanguage("en"); // closed already: nothing happens
  });

  it("uses showModal and close where the browser has them", async () => {
    await setup();
    const dialog = $("ex-dialog");
    dialog.showModal = vi.fn(() => dialog.setAttribute("open", ""));
    dialog.close = vi.fn(() => dialog.removeAttribute("open"));

    await open();
    $("ex-cancel").click();

    expect(dialog.showModal).toHaveBeenCalled();
    expect(dialog.close).toHaveBeenCalled();
  });

  it("does nothing on a page without the dialog", async () => {
    document.body.innerHTML = "<main></main>";
    await loadI18n("en");
    await loadScript("js/api.js");
    delete window.UniSpaceExam;

    await loadScript("js/exam.js");

    expect(window.UniSpaceExam).toBeUndefined();
  });
});
