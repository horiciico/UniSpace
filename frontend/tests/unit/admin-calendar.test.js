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

// Admin: the Academic calendar tab (D-027, C-010). Lazy: the periods load when the tab opens.
const PERIODS = [
  {
    id: "p1",
    name: "Semestrul 1",
    type: "TEACHING",
    start_date: "2026-10-05",
    end_date: "2026-12-06",
  },
  {
    id: "p2",
    name: "Sesiune iarnă",
    type: "EXAM_SESSION",
    start_date: "2026-12-10",
    end_date: "2026-12-18",
  },
  {
    id: "p3",
    name: "Vacanță",
    type: "HOLIDAY",
    start_date: "2026-12-20",
    end_date: "2027-01-03",
  },
];

async function setup({ periods = PERIODS, routes = {}, language = "en" } = {}) {
  mountPage("pages/admin/index.html");
  await loadI18n(language);
  window.UniSpaceI18n.setLanguage(language);
  window.UniSpaceI18n.apply(document.body);
  const toast = vi.fn();
  window.UniSpaceUI = { toast };
  await loadScript("js/api.js");
  const fetch = stubFetch({
    "/api/admin/bookings/pending": () => response([]),
    "/api/admin/bookings": () =>
      response({ items: [], total: 0, limit: 15, offset: 0 }),
    "/api/faculties": () => response([]),
    "/api/admin/academic-periods": (url) =>
      response(Array.isArray(periods) ? periods : periods(url)),
    ...routes,
  });
  await loadScript("js/pages/admin-history.js");
  await loadScript("js/pages/admin-calendar.js");
  return { fetch, toast };
}

const $ = (id) => document.getElementById(id);
const tab = () => document.getElementById("tab-calendar");
const rows = () => [...$("acal-body").querySelectorAll("tr")];
const cells = (row) =>
  [...row.querySelectorAll("td")].map((c) => c.textContent);
const methodOf = (call) => (call[1] && call[1].method) || "GET";
const calls = (fetch, method) =>
  fetch.mock.calls.filter((c) => methodOf(c) === method);

async function openTab(options) {
  const world = await setup(options);
  tab().click();
  await flush();
  return world;
}

function fillForm({
  name = "Sesiune vară",
  type = "EXAM_SESSION",
  start = "2027-06-01",
  end = "2027-06-30",
} = {}) {
  $("acal-name").value = name;
  $("acal-type").value = type;
  $("acal-start").value = start;
  $("acal-end").value = end;
}

function submit() {
  $("acal-form").dispatchEvent(
    new Event("submit", { cancelable: true, bubbles: true }),
  );
}

const httpError = (status) => response({ detail: "x" }, status);

describe("admin calendar tab", () => {
  beforeEach(() => vi.resetModules());

  it("is its own tab and shows its panel only when chosen", async () => {
    await setup();

    expect($("panel-calendar").hidden).toBe(true);
    tab().click();
    await flush();

    expect($("panel-calendar").hidden).toBe(false);
    expect(tab().getAttribute("aria-selected")).toBe("true");
    expect($("panel-pending").hidden).toBe(true);
  });

  it("lists the periods with a type badge, the dates and the actions", async () => {
    const { fetch } = await openTab();

    expect(
      calls(fetch, "GET").some((c) => c[0] === "/api/admin/academic-periods"),
    ).toBe(true);
    expect(rows()).toHaveLength(3);
    expect(cells(rows()[0]).slice(0, 4)).toEqual([
      "Semestrul 1",
      "Semester",
      "2026-10-05",
      "2026-12-06",
    ]);
    const badges = rows().map((r) => r.querySelector(".pill"));
    expect(badges.map((b) => b.textContent)).toEqual([
      "Semester",
      "Exam session",
      "Holiday",
    ]);
    expect(badges.map((b) => b.className)).toEqual([
      "pill pill--confirmed",
      "pill pill--pending",
      "pill pill--busy",
    ]);
    const buttons = rows()[1].querySelectorAll("button");
    expect(buttons[0].getAttribute("aria-label")).toBe("Edit Sesiune iarnă");
    expect(buttons[1].getAttribute("aria-label")).toBe("Delete Sesiune iarnă");
    expect($("acal-empty").hidden).toBe(true);
    expect($("acal-default-note").hidden).toBe(false);
  });

  it("explains an empty calendar", async () => {
    await openTab({ periods: [] });

    expect(rows()).toHaveLength(0);
    expect($("acal-empty").hidden).toBe(false);
    expect($("acal-default-note").hidden).toBe(true);
  });

  it("says when the periods cannot be loaded", async () => {
    await openTab({
      routes: { "/api/admin/academic-periods": () => httpError(500) },
    });

    expect($("acal-status").hidden).toBe(false);
    expect($("acal-status").className).toBe("notice notice--error");
    expect($("acal-status").textContent).toBe(
      "Could not load the periods. Try again.",
    );
  });

  it("ignores an older answer that arrives after a newer one", async () => {
    const first = deferred();
    let calls = 0;
    await setup({
      routes: {
        "/api/admin/academic-periods": () =>
          ++calls === 1 ? first.promise : response([PERIODS[2]]),
      },
    });
    tab().click();
    tab().click();
    await flush();
    first.resolve(response(PERIODS));
    await flush();

    expect(rows()).toHaveLength(1);
  });

  it("ignores an older failure that arrives after a newer answer", async () => {
    const first = deferred();
    let calls = 0;
    await setup({
      routes: {
        "/api/admin/academic-periods": () =>
          ++calls === 1 ? first.promise : response(PERIODS),
      },
    });
    tab().click();
    tab().click();
    await flush();
    first.reject(new Error("late"));
    await flush();

    expect(rows()).toHaveLength(3);
    expect($("acal-status").hidden).toBe(true);
  });

  it("adds a period, shows a toast and loads the list again", async () => {
    const { fetch, toast } = await openTab();

    $("acal-add").click();
    expect($("acal-edit").hidden).toBe(false);
    expect($("acal-edit-title").textContent).toBe("New period");
    expect($("acal-type").value).toBe("TEACHING");
    expect($("acal-name").value).toBe("");
    fillForm({ name: "  Sesiune vară  " });
    submit();
    await flush();

    const [post] = calls(fetch, "POST");
    expect(post[0]).toBe("/api/admin/academic-periods");
    expect(JSON.parse(post[1].body)).toEqual({
      name: "Sesiune vară",
      type: "EXAM_SESSION",
      start_date: "2027-06-01",
      end_date: "2027-06-30",
    });
    expect(toast).toHaveBeenCalledWith("Period saved.");
    expect($("acal-edit").hidden).toBe(true);
    expect(
      calls(fetch, "GET").filter((c) => c[0] === "/api/admin/academic-periods"),
    ).toHaveLength(2);
  });

  it("edits a period with its own values filled in", async () => {
    const { fetch, toast } = await openTab({
      routes: {
        "/api/admin/academic-periods/p2": () => response(PERIODS[1]),
      },
    });

    rows()[1].querySelectorAll("button")[0].click();
    expect($("acal-edit-title").textContent).toBe("Edit period");
    expect($("acal-name").value).toBe("Sesiune iarnă");
    expect($("acal-type").value).toBe("EXAM_SESSION");
    expect($("acal-start").value).toBe("2026-12-10");
    expect($("acal-end").value).toBe("2026-12-18");
    $("acal-end").value = "2026-12-19";
    submit();
    await flush();

    const [put] = calls(fetch, "PUT");
    expect(put[0]).toBe("/api/admin/academic-periods/p2");
    expect(JSON.parse(put[1].body).end_date).toBe("2026-12-19");
    expect(toast).toHaveBeenCalledWith("Period saved.");
  });

  it("closes the editor on Cancel without sending anything", async () => {
    const { fetch } = await openTab();
    $("acal-add").click();

    $("acal-cancel").click();

    expect($("acal-edit").hidden).toBe(true);
    expect(calls(fetch, "POST")).toHaveLength(0);
  });

  it("checks the form before it sends anything", async () => {
    const { fetch } = await openTab();
    $("acal-add").click();

    fillForm({ name: "   " });
    submit();
    expect($("acal-form-error").textContent).toBe(
      "Write a name for the period.",
    );

    fillForm({ start: "" });
    submit();
    expect($("acal-form-error").textContent).toBe(
      "Choose a start date and an end date.",
    );

    fillForm({ end: "" });
    submit();
    expect($("acal-form-error").textContent).toBe(
      "Choose a start date and an end date.",
    );

    fillForm({ start: "2027-07-01", end: "2027-06-01" });
    submit();
    expect($("acal-form-error").hidden).toBe(false);
    expect($("acal-form-error").textContent).toBe(
      "Check the dates. The end date must be on or after the start date.",
    );
    expect(calls(fetch, "POST")).toHaveLength(0);
  });

  it("allows a one-day period", async () => {
    const { fetch } = await openTab();
    $("acal-add").click();
    fillForm({ start: "2027-06-01", end: "2027-06-01" });

    submit();
    await flush();

    expect(calls(fetch, "POST")).toHaveLength(1);
  });

  it.each([
    [
      409,
      "These dates overlap another period. Change the dates or edit that period.",
    ],
    [400, "Check the dates. The end date must be on or after the start date."],
    [
      422,
      "The period is not valid. Check the name (at most 150 characters), the type and the dates.",
    ],
    [500, "The period could not be saved. Try again."],
  ])(
    "explains a %i answer and keeps the form open",
    async (status, message) => {
      let failing = false;
      const { toast } = await openTab({
        routes: {
          "/api/admin/academic-periods": () =>
            failing ? httpError(status) : response(PERIODS),
        },
      });
      failing = true;
      $("acal-add").click();
      fillForm();

      submit();
      await flush();

      expect($("acal-form-error").hidden).toBe(false);
      expect($("acal-form-error").textContent).toBe(message);
      expect($("acal-edit").hidden).toBe(false);
      expect($("acal-save").disabled).toBe(false);
      expect(toast).not.toHaveBeenCalled();
    },
  );

  it("asks before it deletes, and keeps the period on Keep", async () => {
    const { fetch } = await openTab();

    rows()[1].querySelectorAll("button")[1].click();
    expect($("acal-delete").hidden).toBe(false);
    expect($("acal-delete-title").textContent).toBe("Delete “Sesiune iarnă”?");
    expect($("acal-delete-text").textContent).toBe(
      "After this, 2026-12-10 – 2026-12-18 count as teaching weeks again.",
    );
    $("acal-delete-keep").click();

    expect($("acal-delete").hidden).toBe(true);
    expect(calls(fetch, "DELETE")).toHaveLength(0);
  });

  it("deletes after the confirmation, shows a toast and loads the list again", async () => {
    const { fetch, toast } = await openTab({
      routes: {
        "/api/admin/academic-periods/p2": () => response(null, 204),
      },
    });
    rows()[1].querySelectorAll("button")[1].click();

    $("acal-delete-confirm").click();
    await flush();

    expect(calls(fetch, "DELETE")[0][0]).toBe("/api/admin/academic-periods/p2");
    expect(toast).toHaveBeenCalledWith("Period deleted.");
    expect($("acal-delete").hidden).toBe(true);
    expect($("acal-delete-confirm").disabled).toBe(false);
  });

  it("says when a period cannot be deleted", async () => {
    await openTab({
      routes: { "/api/admin/academic-periods/p2": () => httpError(500) },
    });
    rows()[1].querySelectorAll("button")[1].click();

    $("acal-delete-confirm").click();
    await flush();

    expect($("acal-delete").hidden).toBe(true);
    expect($("acal-status").className).toBe("notice notice--error");
    expect($("acal-status").textContent).toBe(
      "The period could not be deleted. Try again.",
    );
  });

  it("shows one card at a time: the editor or the delete question", async () => {
    await openTab();

    rows()[0].querySelectorAll("button")[1].click();
    expect($("acal-delete").hidden).toBe(false);
    $("acal-add").click();
    expect($("acal-delete").hidden).toBe(true);
    expect($("acal-edit").hidden).toBe(false);
    rows()[0].querySelectorAll("button")[1].click();
    expect($("acal-edit").hidden).toBe(true);
  });

  it("closes the cards when the tab is opened again", async () => {
    await openTab();
    $("acal-add").click();

    tab().click();
    await flush();

    expect($("acal-edit").hidden).toBe(true);
    expect($("acal-delete").hidden).toBe(true);
  });

  it("builds its labels again when the language changes", async () => {
    await openTab();
    $("acal-add").click();
    fillForm({ name: "" });
    submit();

    window.UniSpaceI18n.setLanguage("ro");
    await flush();

    expect(rows()[0].querySelector(".pill").textContent).toBe("Semestru");
    expect(rows()[1].querySelector(".pill").textContent).toBe("Sesiune");
    expect(rows()[2].querySelector(".pill").textContent).toBe("Vacanță");
    expect($("acal-edit-title").textContent).toBe("Perioadă nouă");
    expect($("acal-form-error").textContent).toBe(
      "Scrie un nume pentru perioadă.",
    );
  });

  it("translates the open delete question when the language changes", async () => {
    await openTab();
    rows()[2].querySelectorAll("button")[1].click();

    window.UniSpaceI18n.setLanguage("ro");
    await flush();

    expect($("acal-delete-title").textContent).toBe("Ștergi „Vacanță”?");
  });

  it("has Romanian labels for the badges and the toasts", async () => {
    const { toast } = await openTab({ language: "ro" });
    $("acal-add").click();
    fillForm();
    submit();
    await flush();

    expect(toast).toHaveBeenCalledWith("Perioada a fost salvată.");
  });
});
