import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { deferred, flush, loadI18n, loadScript, mountPage, response, stubFetch } from "../helpers.js";

// Tuesday 24 November 2026, 10:00 local: every request for a day from the 25th on is in the future.
const NOW = new Date(2026, 10, 24, 10, 0);
const STUDENT = { id: "u1", email: "s@ulbsibiu.ro", name: "Student", role: "STUDENT" };
const ADMIN = { id: "u2", email: "a@ulbsibiu.ro", name: "Admin", role: "ADMIN" };

const FACULTIES = [{ id: "0b1a6f7e-2c3d-4e5f-8a9b-0c1d2e3f4a5b", code: "dre", name: "Facultatea de Drept" }, { id: "1c2b7f8e-3d4e-4f60-9b0a-1d2e3f4a5b6c", code: "ing", name: "Inginerie" }];
const ROOMS = [
  { id: "7c8d9e0f-1a2b-4c3d-9e8f-7a6b5c4d3e2f", name: "Sala 101", faculty_id: "0b1a6f7e-2c3d-4e5f-8a9b-0c1d2e3f4a5b", is_bookable: true },
  { id: "8d9e0f1a-2b3c-4d5e-8f70-8b7c6d5e4f3a", name: "Sala 102", faculty_id: "0b1a6f7e-2c3d-4e5f-8a9b-0c1d2e3f4a5b", is_bookable: false }
];
const MINE = [
  { id: "b1", title: "Club", room_name: "Sala 101", faculty_name: "Facultatea de Drept", specific_date: "2026-12-14",
    start_time: "08:00", end_time: "09:30", status: "pending" },
  { id: "b2", title: "Gala", room_name: "Aula", faculty_name: null, specific_date: "2026-12-15",
    start_time: "09:40", end_time: "11:10", status: "approved" },
  { id: "b3", title: "Old", room_name: "Sala 101", faculty_name: "Facultatea de Drept", specific_date: "2026-12-01",
    start_time: "13:00", end_time: "14:30", status: "cancelled" },
  { id: "b4", title: "Odd", room_name: "Sala 101", faculty_name: "Facultatea de Drept", specific_date: "2026-12-16",
    start_time: "13:00", end_time: "14:30", status: "mystery" }
];

// Mounts the real Bookings page, loads its scripts as the browser does, and waits for the lists.
async function setup({ url = "/bookings/", routes = {}, me = () => response(STUDENT), language = "en" } = {}) {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  window.history.replaceState(null, "", url);
  mountPage("pages/shared/bookings.html");
  await loadI18n(language);
  await loadScript("js/modules.js");
  await loadScript("js/api.js");
  await loadScript("js/bookings.js");
  const fetch = stubFetch({
    "/auth/me": me,
    "/api/faculties": () => response(FACULTIES),
    "/api/classrooms": () => response(ROOMS),
    "/api/bookings/my": () => response(MINE),
    ...routes
  });
  await loadScript("js/auth.js");
  await loadScript("js/pages/bookings.js");
  await flush();
  await flush();
  return { fetch };
}

const $ = (id) => document.getElementById(id);
const text = (id) => $(id).textContent;
const rows = () => [...document.querySelectorAll("#bk-list > li")];
const methodOf = (call) => (call[1] && call[1].method) || "GET";
const callsWith = (fetch, method) => fetch.mock.calls.filter((c) => methodOf(c) === method);

// Sets a control's value and fires its change event, as a user would.
function pick(element, value) {
  element.value = value;
  element.dispatchEvent(new Event("change", { bubbles: true }));
}

function submitForm() {
  $("bk-form").dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
}

// A room chosen (the faculty is chosen with it), a date, the modules and a title.
async function fillForm({ title = "Club", date = "2026-12-14", from = "0", to = "0" } = {}) {
  pick($("bk-faculty"), "0b1a6f7e-2c3d-4e5f-8a9b-0c1d2e3f4a5b");
  await flush();
  pick($("bk-room"), "7c8d9e0f-1a2b-4c3d-9e8f-7a6b5c4d3e2f");
  $("bk-date").value = date;
  pick($("bk-from"), from);
  pick($("bk-to"), to);
  $("bk-title").value = title;
}

const httpError = (status) => Object.assign(new Error("HTTP " + status), { status });

function tidy() {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
}

describe("bookings page: the user's requests", () => {
  beforeEach(() => vi.resetModules());
  afterEach(tidy);

  it("lists the requests with their status, and offers cancel only for a pending one", async () => {
    await setup();

    expect(rows()).toHaveLength(4);
    const [pending, approved, cancelled, unknown] = rows();
    expect(pending.querySelector("strong").textContent).toBe("Club");
    expect(pending.querySelector(".pill").textContent).toBe("Pending");
    expect(pending.querySelector(".pill").className).toBe("pill pill--pending");
    expect(pending.querySelector("button").textContent).toBe("Cancel");
    expect(pending.querySelector("button").getAttribute("aria-label")).toBe("Cancel the request Club");
    expect(pending.querySelector(".booking-meta").textContent).toContain("Sala 101 · Facultatea de Drept");
    expect(approved.querySelector(".pill").textContent).toBe("Approved");
    expect(approved.querySelector(".booking-meta").textContent).toContain("Aula · Campus");
    expect(approved.querySelector("button")).toBeNull();
    expect(cancelled.querySelector(".pill").textContent).toBe("Cancelled");
    expect(cancelled.querySelector(".pill").className).toBe("pill");
    expect(unknown.querySelector(".pill").textContent).toBe("mystery");
  });

  it("shows the administrator's message on a decided request, and nothing extra without one", async () => {
    await setup({
      routes: {
        "/api/bookings/my": () => response([
          { ...MINE[0], status: "rejected", decision_message: "Sala e ocupata." },
          { ...MINE[1], status: "approved", decision_message: null }
        ])
      }
    });

    const [rejected, approved] = rows();
    expect(rejected.querySelector(".decision-note").textContent).toBe("Note from the administrator: Sala e ocupata.");
    expect(approved.querySelector(".decision-note")).toBeNull();
  });

  it("labels the submit button by what happens: a request for a student, a booking for an admin", async () => {
    await setup();
    expect($("bk-send").textContent).toBe("Request to book");
  });

  it("labels the submit button 'Book the room' for an admin, whose booking is approved at once", async () => {
    await setup({ me: () => response(ADMIN) });
    expect($("bk-send").textContent).toBe("Book the room");
    expect($("bk-send").getAttribute("data-i18n")).toBe("bookings.book");
  });

  it("keeps the submit label in the new language", async () => {
    await setup({ me: () => response(ADMIN), language: "en" });
    window.UniSpaceI18n.setLanguage("ro");
    await flush();
    expect($("bk-send").textContent).toBe("Rezervă sala");
    window.UniSpaceI18n.setLanguage("en");
  });

  it("says so when there are no requests yet", async () => {
    await setup({ routes: { "/api/bookings/my": () => response([]) } });

    expect(rows()).toHaveLength(0);
    expect(text("bk-mine-status")).toBe("No requests yet. Send your first one with the form.");
  });

  it("shows an error when the requests cannot be loaded", async () => {
    await setup({ routes: { "/api/bookings/my": () => response({ detail: "x" }, 500) } });

    expect(text("bk-mine-status")).toBe("Could not load the data. Try again.");
    expect($("bk-mine-status").className).toBe("notice notice--error");
  });

  it("cancels a pending request and lists the requests again", async () => {
    const { fetch } = await setup({
      routes: { "/api/bookings/b1": () => response({ ...MINE[0], status: "cancelled" }) }
    });
    fetch.mockClear();
    rows()[0].querySelector("button").click();
    await flush();
    await flush();

    expect(callsWith(fetch, "DELETE")).toHaveLength(1);
    expect(fetch.mock.calls.some((c) => c[0] === "/api/bookings/my")).toBe(true);
    expect(text("bk-mine-status")).toBe("");
  });

  it("explains a cancel the backend refuses", async () => {
    await setup({ routes: { "/api/bookings/b1": () => response({ detail: "no" }, 409) } });
    rows()[0].querySelector("button").click();
    await flush();

    expect(text("bk-mine-status")).toBe("Only a pending request can be cancelled.");
    expect($("bk-mine-status").className).toBe("notice notice--error");
  });

  it("explains any other cancel failure in general words", async () => {
    await setup({ routes: { "/api/bookings/b1": () => response({ detail: "x" }, 500) } });
    rows()[0].querySelector("button").click();
    await flush();

    expect(text("bk-mine-status")).toBe("Something went wrong. Try again.");
  });
});

describe("bookings page: the form", () => {
  beforeEach(() => vi.resetModules());
  afterEach(tidy);

  it("opens on today, with the first module in both pickers and no link note", async () => {
    await setup();

    expect($("bk-date").value).toBe("2026-11-24");
    expect($("bk-date").min).toBe("2026-11-24");
    expect($("bk-from").value).toBe("0");
    expect($("bk-to").value).toBe("0");
    expect($("bk-from").options).toHaveLength(8);
    expect($("bk-from").options[0].textContent).toBe("1 · 08:00–09:30");
    expect($("bk-prefill-note").hidden).toBe(true);
    expect($("bk-room").disabled).toBe(true);
  });

  it("fills in the faculty, the room, the date and the modules from the link", async () => {
    await setup({ url: "/bookings/?faculty_id=0b1a6f7e-2c3d-4e5f-8a9b-0c1d2e3f4a5b&room=7c8d9e0f-1a2b-4c3d-9e8f-7a6b5c4d3e2f&date=2026-12-14&start=09:40&end=11:10" });

    expect($("bk-prefill-note").hidden).toBe(false);
    expect($("bk-faculty").value).toBe("0b1a6f7e-2c3d-4e5f-8a9b-0c1d2e3f4a5b");
    expect($("bk-room").value).toBe("7c8d9e0f-1a2b-4c3d-9e8f-7a6b5c4d3e2f");
    expect($("bk-room").disabled).toBe(false);
    expect($("bk-date").value).toBe("2026-12-14");
    expect($("bk-from").value).toBe("1");
    expect($("bk-to").value).toBe("1");
  });

  it("falls back to the first module when a link time is not a module boundary", async () => {
    await setup({ url: "/bookings/?faculty_id=campus&start=12:00&end=12:00" });

    expect($("bk-faculty").value).toBe("campus");
    expect($("bk-prefill-note").hidden).toBe(false);
    expect($("bk-from").value).toBe("0");
    expect($("bk-to").value).toBe("0");
    expect($("bk-date").value).toBe("2026-11-24");
  });

  it("lists the faculties, then Campus, and only the rooms that can be booked", async () => {
    await setup();
    pick($("bk-faculty"), "0b1a6f7e-2c3d-4e5f-8a9b-0c1d2e3f4a5b");
    await flush();

    expect([...$("bk-faculty").options].map((o) => o.textContent)).toEqual([
      "Choose a faculty", "Campus", "Facultatea de Drept", "Inginerie"
    ]);
    expect([...$("bk-room").options].map((o) => o.textContent)).toEqual(["Choose a room", "Sala 101"]);
    expect($("bk-room-note").textContent).toBe("Only rooms that can be booked are listed.");
  });

  it("says so when no room of the faculty can be booked", async () => {
    await setup({ routes: { "/api/classrooms": () => response([ROOMS[1]]) } });
    pick($("bk-faculty"), "0b1a6f7e-2c3d-4e5f-8a9b-0c1d2e3f4a5b");
    await flush();

    expect($("bk-room-note").textContent).toBe("No room in this faculty can be booked.");
  });

  it("asks the server for the campus rooms when Campus is chosen", async () => {
    const { fetch } = await setup();
    pick($("bk-faculty"), "campus");
    await flush();

    expect(fetch.mock.calls.map((c) => c[0])).toContain("/api/classrooms?faculty_id=campus");
  });

  it("shows an error when the faculties cannot be loaded", async () => {
    await setup({ routes: { "/api/faculties": () => response({ detail: "x" }, 500) } });

    expect(text("bk-form-status")).toBe("Could not load the data. Try again.");
    expect($("bk-form-status").hidden).toBe(false);
  });

  it("shows an error when the rooms cannot be loaded", async () => {
    await setup({ routes: { "/api/classrooms": () => response({ detail: "x" }, 500) } });
    pick($("bk-faculty"), "0b1a6f7e-2c3d-4e5f-8a9b-0c1d2e3f4a5b");
    await flush();

    expect(text("bk-form-status")).toBe("Could not load the data. Try again.");
  });

  it("drops an old room answer that arrives after a newer one", async () => {
    const late = deferred();
    await setup({
      routes: {
        "/api/classrooms": (url) => (url.includes("faculty_id=0b1a6f7e-2c3d-4e5f-8a9b-0c1d2e3f4a5b")
          ? late.promise.then(() => response(ROOMS))
          : response([{ id: "r9", name: "Sala 9", is_bookable: true }]))
      }
    });
    pick($("bk-faculty"), "0b1a6f7e-2c3d-4e5f-8a9b-0c1d2e3f4a5b");
    pick($("bk-faculty"), "campus");
    await flush();
    late.resolve();
    await flush();

    expect([...$("bk-room").options].map((o) => o.textContent)).toEqual(["Choose a room", "Sala 9"]);
  });

  it("ignores a late failure of an old room request", async () => {
    const late = deferred();
    await setup({
      routes: { "/api/classrooms": (url) => (url.includes("faculty_id=0b1a6f7e-2c3d-4e5f-8a9b-0c1d2e3f4a5b") ? late.promise : response([])) }
    });
    pick($("bk-faculty"), "0b1a6f7e-2c3d-4e5f-8a9b-0c1d2e3f4a5b");
    pick($("bk-faculty"), "campus");
    await flush();
    late.reject(httpError(500));
    await flush();

    expect($("bk-form-status").hidden).toBe(true);
  });

  it("clears the room that the link named when the faculty changes", async () => {
    await setup({ url: "/bookings/?faculty_id=0b1a6f7e-2c3d-4e5f-8a9b-0c1d2e3f4a5b&room=7c8d9e0f-1a2b-4c3d-9e8f-7a6b5c4d3e2f" });
    pick($("bk-faculty"), "campus");
    await flush();

    expect($("bk-room").value).toBe("");
  });

  it("refuses a request with no room before it is sent", async () => {
    const { fetch } = await setup();
    submitForm();
    await flush();

    expect(text("bk-form-status")).toBe("Choose a room.");
    expect(callsWith(fetch, "POST")).toHaveLength(0);
  });

  it("refuses a request with no date, a blank title, or the last module before the first", async () => {
    const { fetch } = await setup();
    await fillForm({ date: "" });
    submitForm();
    expect(text("bk-form-status")).toBe("Choose a date.");

    await fillForm({ title: "   " });
    submitForm();
    expect(text("bk-form-status")).toBe("Write a title or a reason.");

    await fillForm({ from: "2", to: "1" });
    submitForm();
    expect(text("bk-form-status")).toBe("The last module must be after the first one.");
    expect(callsWith(fetch, "POST")).toHaveLength(0);
  });

  it("sends the request with the module range and a trimmed title, then clears the title", async () => {
    const { fetch } = await setup({
      url: "/bookings/?faculty_id=0b1a6f7e-2c3d-4e5f-8a9b-0c1d2e3f4a5b&room=7c8d9e0f-1a2b-4c3d-9e8f-7a6b5c4d3e2f",
      routes: { "/api/bookings": () => response({ id: "b9", status: "pending" }, 201) }
    });
    await fillForm({ title: "  Club  ", from: "1", to: "2" });
    submitForm();
    await flush();
    await flush();

    const post = callsWith(fetch, "POST")[0];
    expect(post[0]).toBe("/api/bookings");
    expect(JSON.parse(post[1].body)).toEqual({
      classroom_id: "7c8d9e0f-1a2b-4c3d-9e8f-7a6b5c4d3e2f", specific_date: "2026-12-14", start_time: "09:40", end_time: "12:50", title: "Club"
    });
    expect(text("bk-form-status")).toBe("The request was sent. It waits for an admin to approve it.");
    expect($("bk-form-status").className).toBe("notice");
    expect($("bk-title").value).toBe("");
    expect($("bk-send").disabled).toBe(false);
  });

  it("tells an admin that the booking is approved at once", async () => {
    await setup({
      url: "/bookings/?faculty_id=0b1a6f7e-2c3d-4e5f-8a9b-0c1d2e3f4a5b&room=7c8d9e0f-1a2b-4c3d-9e8f-7a6b5c4d3e2f",
      me: () => response(ADMIN),
      routes: { "/api/bookings": () => response({ id: "b9", status: "approved" }, 201) }
    });
    expect($("bk-admin-note").hidden).toBe(false);
    await fillForm();
    submitForm();
    await flush();
    await flush();

    expect(text("bk-form-status")).toBe("The booking was approved.");
  });

  it("hides the admin note from a student", async () => {
    await setup();
    expect($("bk-admin-note").hidden).toBe(true);
  });

  it("hides the admin note when the session is not known", async () => {
    await setup({ me: () => response({ detail: "x" }, 500) });
    expect($("bk-admin-note").hidden).toBe(true);
  });

  it.each([
    [409, "The room is taken at that time. Choose another time or another room."],
    [400, "Check the date and modules: a booking cannot start in the past and must use whole modules."],
    [404, "The room was not found. Choose the room again."],
    [500, "Something went wrong. Try again."]
  ])("explains a refused request (status %i) in words", async (status, message) => {
    await setup({
      url: "/bookings/?faculty_id=0b1a6f7e-2c3d-4e5f-8a9b-0c1d2e3f4a5b&room=7c8d9e0f-1a2b-4c3d-9e8f-7a6b5c4d3e2f",
      routes: { "/api/bookings": () => response({ detail: "x" }, status) }
    });
    await fillForm();
    submitForm();
    await flush();
    await flush();

    expect(text("bk-form-status")).toBe(message);
    expect($("bk-form-status").className).toBe("notice notice--error");
    expect($("bk-send").disabled).toBe(false);
  });

  it("writes the current messages and the lists again in the new language", async () => {
    const { fetch } = await setup({ language: "en" });
    submitForm();
    await flush();
    expect(text("bk-form-status")).toBe("Choose a room.");
    fetch.mockClear();

    window.UniSpaceI18n.setLanguage("ro");
    await flush();
    await flush();

    expect(text("bk-form-status")).toBe("Alege o sală.");
    expect(fetch.mock.calls.some((c) => c[0] === "/api/bookings/my")).toBe(true);
    expect($("bk-from").options[0].textContent).toBe("1 · 08:00–09:30");
    window.UniSpaceI18n.setLanguage("en");
  });

  it("keeps the requests message, and leaves the form message clear, on a language change", async () => {
    await setup({ routes: { "/api/bookings/my": () => response([]) } });
    expect(text("bk-mine-status")).toBe("No requests yet. Send your first one with the form.");

    document.dispatchEvent(new CustomEvent("unispace:langchange"));
    await flush();
    await flush();

    expect(text("bk-mine-status")).toBe("No requests yet. Send your first one with the form.");
    expect($("bk-form-status").hidden).toBe(true);
  });
});
