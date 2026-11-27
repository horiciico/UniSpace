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

// The Bookings page follows the academic calendar (D-027, C-010): modules on a teaching day, whole
// hours in an exam session, no booking on a holiday. Today is Tuesday 24 November 2026, 10:00.
const NOW = new Date(2026, 10, 24, 10, 0);
const FACULTY = "0b1a6f7e-2c3d-4e5f-8a9b-0c1d2e3f4a5b";
const ROOM = "7c8d9e0f-1a2b-4c3d-9e8f-7a6b5c4d3e2f";
const PERIODS = [
  {
    id: "p1",
    name: "Sesiune",
    type: "EXAM_SESSION",
    start_date: "2026-12-10",
    end_date: "2026-12-18",
  },
  {
    id: "p2",
    name: "Vacanta",
    type: "HOLIDAY",
    start_date: "2026-12-20",
    end_date: "2027-01-03",
  },
];

async function setup({
  url = "/bookings/",
  periods = () => response(PERIODS),
  language = "en",
} = {}) {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  window.history.replaceState(null, "", url);
  mountPage("pages/shared/bookings.html");
  await loadI18n(language);
  window.UniSpaceI18n.setLanguage(language);
  window.UniSpaceI18n.apply(document.body);
  await loadScript("js/modules.js");
  await loadScript("js/api.js");
  await loadScript("js/bookings.js");
  const fetch = stubFetch({
    "/auth/me": () =>
      response({
        id: "u1",
        email: "s@ulbsibiu.ro",
        name: "S",
        role: "STUDENT",
      }),
    "/api/faculties": () =>
      response([{ id: FACULTY, code: "dre", name: "Drept" }]),
    "/api/classrooms": () =>
      response([
        { id: ROOM, name: "Sala 101", faculty_id: FACULTY, is_bookable: true },
      ]),
    "/api/bookings/my": () => response([]),
    "/api/bookings": () => response({ id: "b1", status: "pending" }, 201),
    "/api/academic-periods": periods,
  });
  await loadScript("js/auth.js");
  await loadScript("js/pages/bookings.js");
  await flush();
  await flush();
  return { fetch };
}

const $ = (id) => document.getElementById(id);
const options = (id) => [...$(id).options].map((o) => o.textContent);
const labelOf = (id) => document.querySelector(`label[for="${id}"]`);

function pickDate(value) {
  $("bk-date").value = value;
  $("bk-date").dispatchEvent(new Event("change", { bubbles: true }));
}

function submit() {
  $("bk-form").dispatchEvent(
    new Event("submit", { cancelable: true, bubbles: true }),
  );
}

async function fill(date) {
  $("bk-faculty").value = FACULTY;
  $("bk-faculty").dispatchEvent(new Event("change", { bubbles: true }));
  await flush();
  $("bk-room").value = ROOM;
  pickDate(date);
  $("bk-title").value = "Study";
}

const posted = (fetch) =>
  fetch.mock.calls.filter((c) => c[1] && c[1].method === "POST");

describe("bookings page: the academic calendar", () => {
  beforeEach(() => vi.resetModules());

  it("offers the 90-minute modules on a teaching day", async () => {
    await setup();

    expect($("bk-from").options).toHaveLength(8);
    expect(options("bk-from")[0]).toBe("1 · 08:00–09:30");
    expect(labelOf("bk-from").textContent).toBe("From module");
    expect($("bk-period-note").hidden).toBe(true);
    expect($("bk-send").disabled).toBe(false);
  });

  it("offers half hours with its own labels and note on an exam-session day", async () => {
    await setup();

    pickDate("2026-12-14");

    expect($("bk-from").options).toHaveLength(28);
    expect(options("bk-from")[0]).toBe("08:00–08:30");
    expect(options("bk-to")[27]).toBe("21:30–22:00");
    expect(labelOf("bk-from").textContent).toBe("From hour");
    expect(labelOf("bk-to").textContent).toBe("To hour");
    expect($("bk-period-note").hidden).toBe(false);
    expect($("bk-period-note").textContent).toContain("half-hour steps");
    expect($("bk-send").disabled).toBe(false);
  });

  it("closes the form on a holiday and says why", async () => {
    await setup();

    pickDate("2026-12-21");

    expect($("bk-send").disabled).toBe(true);
    expect($("bk-period-note").hidden).toBe(false);
    expect($("bk-period-note").textContent).toContain("closed");
    expect($("bk-from").options).toHaveLength(8);
  });

  it("opens the form again, with modules, when the date moves back to a teaching day", async () => {
    await setup();
    pickDate("2026-12-14");

    pickDate("2026-12-08");

    expect($("bk-from").options).toHaveLength(8);
    expect(labelOf("bk-from").textContent).toBe("From module");
    expect($("bk-period-note").hidden).toBe(true);
    expect($("bk-send").disabled).toBe(false);
  });

  it("keeps the chosen hours when the date moves inside the same kind of day", async () => {
    await setup();
    pickDate("2026-12-14");
    $("bk-from").value = "3";

    pickDate("2026-12-15");

    expect($("bk-from").value).toBe("3");
  });

  it("sends the hour range chosen in an exam session", async () => {
    const { fetch } = await setup();
    await fill("2026-12-14");
    $("bk-from").value = "4";
    $("bk-to").value = "9";

    submit();
    await flush();

    const body = JSON.parse(posted(fetch)[0][1].body);
    expect(body).toMatchObject({
      specific_date: "2026-12-14",
      start_time: "10:00",
      end_time: "13:00",
    });
    expect($("bk-send").disabled).toBe(false);
  });

  it("sends modules on a teaching day as before", async () => {
    const { fetch } = await setup();
    await fill("2026-12-08");
    $("bk-from").value = "1";
    $("bk-to").value = "1";

    submit();
    await flush();

    expect(JSON.parse(posted(fetch)[0][1].body)).toMatchObject({
      start_time: "09:40",
      end_time: "11:10",
    });
  });

  it("does not send a booking for a holiday, even when the form is submitted", async () => {
    const { fetch } = await setup();
    await fill("2026-12-21");

    submit();
    await flush();

    expect(posted(fetch)).toHaveLength(0);
    expect($("bk-form-status").textContent).toContain("closed on holidays");
  });

  it("opens an exam-session link with the hours from the link", async () => {
    await setup({
      url:
        "/bookings/?faculty_id=" +
        FACULTY +
        "&room=" +
        ROOM +
        "&date=2026-12-14&start=10:00&end=11:00",
    });

    expect($("bk-from").options).toHaveLength(28);
    expect($("bk-from").value).toBe("4");
    expect($("bk-to").value).toBe("5");
  });

  const link = (date, start, end) =>
    "/bookings/?faculty_id=" +
    FACULTY +
    "&room=" +
    ROOM +
    `&date=${date}&start=${start}&end=${end}`;

  it("does not replace an hour from a link that a teaching day cannot take", async () => {
    const { fetch } = await setup({
      url: link("2026-12-08", "10:00", "11:00"),
    });
    $("bk-title").value = "Study";

    expect($("bk-from").value).toBe("");
    expect($("bk-to").value).toBe("");
    expect($("bk-time-note").hidden).toBe(false);
    expect($("bk-time-note").textContent).toContain("does not fit");

    submit();
    await flush();

    expect(posted(fetch)).toHaveLength(0);
    expect($("bk-form-status").textContent).toBe(
      "Choose the start and the end.",
    );
  });

  it("does not replace module times from a link on an exam-session day", async () => {
    await setup({ url: link("2026-12-14", "14:40", "16:10") });

    expect($("bk-from").value).toBe("");
    expect($("bk-to").value).toBe("");
    expect($("bk-time-note").hidden).toBe(false);
  });

  it("hides the note once both times are chosen, and sends them", async () => {
    const { fetch } = await setup({
      url: link("2026-12-08", "10:00", "11:00"),
    });
    $("bk-title").value = "Study";

    for (const id of ["bk-from", "bk-to"]) {
      $(id).value = "1";
      $(id).dispatchEvent(new Event("change", { bubbles: true }));
    }
    expect($("bk-time-note").hidden).toBe(true);

    submit();
    await flush();

    expect(JSON.parse(posted(fetch)[0][1].body)).toMatchObject({
      start_time: "09:40",
      end_time: "11:10",
    });
  });

  it("keeps the times unchosen when the language changes", async () => {
    await setup({ url: link("2026-12-08", "10:00", "11:00") });

    window.UniSpaceI18n.setLanguage("ro");
    await flush();

    expect($("bk-from").value).toBe("");
    expect($("bk-to").value).toBe("");
    expect($("bk-time-note").textContent).toContain("nu se potrivește");
  });

  it("shows no time note while the periods are still loading", async () => {
    const periods = deferred();
    await setup({
      url: link("2026-12-14", "10:00", "11:00"),
      periods: () => periods.promise,
    });
    expect($("bk-time-note").hidden).toBe(true);

    periods.resolve(response(PERIODS));
    await flush();
    await flush();

    expect($("bk-from").value).toBe("4");
    expect($("bk-time-note").hidden).toBe(true);
  });

  it("shows the time note when the periods cannot be loaded and the link does not fit", async () => {
    await setup({
      url: link("2026-12-14", "10:00", "11:00"),
      periods: () => response({ detail: "boom" }, 500),
    });

    expect($("bk-time-note").hidden).toBe(false);
  });

  it("keeps working with modules when the periods cannot be loaded", async () => {
    await setup({ periods: () => response({ detail: "boom" }, 500) });

    pickDate("2026-12-14");

    expect($("bk-from").options).toHaveLength(8);
    expect($("bk-send").disabled).toBe(false);
  });

  it("changes the pickers when the periods arrive after the form is shown", async () => {
    const periods = deferred();
    await setup({
      url: "/bookings/?date=2026-12-14",
      periods: () => periods.promise,
    });
    expect($("bk-from").options).toHaveLength(8);

    periods.resolve(response(PERIODS));
    await flush();
    await flush();

    expect($("bk-from").options).toHaveLength(28);
  });

  it("translates the labels and the note when the language changes", async () => {
    await setup();
    pickDate("2026-12-14");

    window.UniSpaceI18n.setLanguage("ro");
    await flush();

    expect(labelOf("bk-from").textContent).toBe("De la ora");
    expect($("bk-period-note").textContent).toContain("jumătate de oră");
    expect($("bk-from").options).toHaveLength(28);
  });
});

describe("bookings page: a calendar per faculty", () => {
  beforeEach(() => vi.resetModules());

  const own = () => response([{ ...PERIODS[0], faculty_id: FACULTY }]);

  async function choose(value) {
    $("bk-faculty").value = value;
    $("bk-faculty").dispatchEvent(new Event("change", { bubbles: true }));
    await flush();
  }

  it("follows the calendar of the chosen faculty's rooms", async () => {
    await setup({ periods: own });
    pickDate("2026-12-14");
    expect($("bk-from").options).toHaveLength(8);

    await choose(FACULTY);
    expect($("bk-from").options).toHaveLength(28);

    await choose("campus");
    expect($("bk-from").options).toHaveLength(8);
  });

  it("opens a faculty's exam-session link with the hours from the link", async () => {
    await setup({
      periods: own,
      url: `/bookings/?faculty_id=${FACULTY}&room=${ROOM}&date=2026-12-14&start=10:00&end=11:00`,
    });

    expect($("bk-from").options).toHaveLength(28);
    expect($("bk-from").value).toBe("4");
    expect($("bk-time-note").hidden).toBe(true);
  });
});

describe("bookings page: half hours in an exam session", () => {
  beforeEach(() => vi.resetModules());

  it("starts on the first hour and refuses a half-hour booking", async () => {
    const { fetch } = await setup();
    await fill("2026-12-14");
    expect([$("bk-from").value, $("bk-to").value]).toEqual(["0", "1"]);
    $("bk-to").value = "0";

    submit();
    await flush();

    expect(posted(fetch)).toHaveLength(0);
    expect($("bk-form-status").textContent).toBe(
      "In an exam session a booking lasts at least one hour.",
    );
  });
});
