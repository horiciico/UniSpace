import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { deferred, flush, loadI18n, loadScript, mountPage, response, stubFetch } from "../helpers.js";

// Issue #23: the admin page lists the pending booking requests and accepts or rejects them.
const REQUESTS = [
  {
    id: "b1", title: "Robotics workshop", room_name: "003 DPPD", faculty_name: null, specific_date: "2026-12-14",
    start_time: "13:00", end_time: "14:30", created_at: "2026-11-24T17:40:00",
    requester: { name: "Clubul de robotica", email: "robotics@ulbsibiu.ro", role: "STUDENT_ORG" }
  },
  {
    id: "b2", title: "Board game evening", room_name: "B110", faculty_name: "Drept", specific_date: "2026-12-18",
    start_time: "18:00", end_time: "19:30", created_at: "2026-11-24T09:12:00",
    requester: { name: "Ioana Pop", email: "ioana.pop@ulbsibiu.ro", role: "STUDENT" }
  }
];

async function setup({ routes = {}, language = "en" } = {}) {
  mountPage("pages/admin/index.html");
  await loadI18n(language);
  window.UniSpaceI18n.setLanguage(language);
  window.UniSpaceI18n.apply(document.body);
  await loadScript("js/api.js");
  const fetch = stubFetch({
    "/api/admin/bookings/pending": () => response(REQUESTS),
    ...routes
  });
  await loadScript("js/pages/admin-bookings.js");
  await flush();
  await flush();
  return { fetch };
}

const $ = (id) => document.getElementById(id);
const rows = () => [...document.querySelectorAll("#bk-admin-queue > tr.request")];
const panels = () => [...document.querySelectorAll("#bk-admin-queue > tr.decide")];
const postsTo = (fetch, id) => fetch.mock.calls.filter((c) => c[0] === `/api/admin/bookings/${id}/decision`);
const actionsOf = (row) => [...row.querySelectorAll("button")];
const actionNamed = (row, name) => actionsOf(row).find((b) => b.textContent === name);

function tidy() {
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
}

describe("admin page: the booking requests", () => {
  beforeEach(() => vi.resetModules());
  afterEach(tidy);

  it("lists each request with the requester, their role, the request and the room and time", async () => {
    await setup();

    expect(rows()).toHaveLength(2);
    const [first] = rows();
    expect(first.querySelector("strong").textContent).toBe("Clubul de robotica");
    expect(first.textContent).toContain("robotics@ulbsibiu.ro");
    expect(first.textContent).toContain("Student organization");
    expect(first.textContent).toContain("Robotics workshop");
    expect(first.textContent).toContain("003 DPPD");
    expect(first.textContent).toContain("Mon 14 Dec · 13:00–14:30");
    expect(rows()[1].textContent).toContain("Drept");
  });

  it("says so when no request is waiting", async () => {
    await setup({ routes: { "/api/admin/bookings/pending": () => response([]) } });

    expect(rows()).toHaveLength(0);
    expect($("bk-admin-empty").hidden).toBe(false);
    expect($("bk-admin-empty").querySelector("h2").textContent).toBe("No requests are waiting");
  });

  it("shows an error when the requests cannot be loaded", async () => {
    await setup({ routes: { "/api/admin/bookings/pending": () => response({ detail: "x" }, 500) } });

    expect(rows()).toHaveLength(0);
    expect($("bk-admin-status").textContent).toBe("Could not load the requests. Try again.");
    expect($("bk-admin-status").hidden).toBe(false);
  });

  it("accepts a request: it is approved, and it leaves the list", async () => {
    const { fetch } = await setup({
      routes: { "/api/admin/bookings/b1/decision": () => response({ id: "b1", status: "approved" }) }
    });

    actionNamed(rows()[0], "Accept").click();
    await flush();
    await flush();

    const [call] = postsTo(fetch, "b1");
    expect(call[1].method).toBe("POST");
    expect(JSON.parse(call[1].body)).toEqual({ decision: "approve" });
    expect(rows()).toHaveLength(1);
    expect($("bk-admin-status").textContent).toBe("The booking is approved.");
    expect($("bk-admin-status").className).toBe("notice");
  });

  it("explains that the room is taken when an accept is refused as a clash", async () => {
    await setup({
      routes: { "/api/admin/bookings/b1/decision": () => response({ detail: "clash" }, 409) }
    });

    actionNamed(rows()[0], "Accept").click();
    await flush();

    expect(rows()).toHaveLength(2);
    expect($("bk-admin-status").textContent).toBe(
      "The room is taken at that time. Reject this request, or ask the requester to choose another time."
    );
    expect($("bk-admin-status").className).toBe("notice notice--error");
  });

  it("explains any other failure in general words and keeps the request", async () => {
    await setup({
      routes: { "/api/admin/bookings/b1/decision": () => response({ detail: "x" }, 500) }
    });

    actionNamed(rows()[0], "Accept").click();
    await flush();

    expect($("bk-admin-status").textContent).toBe("Something went wrong. Try again.");
    expect(rows()).toHaveLength(2);
  });

  it("opens the reject panel under the request, and cancel closes it without a request", async () => {
    const { fetch } = await setup();

    actionNamed(rows()[0], "Reject").click();
    expect(panels()).toHaveLength(1);
    expect(panels()[0].querySelector("textarea").maxLength).toBe(1000);
    expect(panels()[0].querySelector("label").textContent).toBe("Message to Clubul de robotica (optional)");

    actionNamed(panels()[0], "Cancel").click();
    expect(panels()).toHaveLength(0);
    expect(postsTo(fetch, "b1")).toHaveLength(0);
  });

  it("rejects a request with the message typed, trimmed, and it leaves the list", async () => {
    const { fetch } = await setup({
      routes: { "/api/admin/bookings/b1/decision": () => response({ id: "b1", status: "rejected" }) }
    });

    actionNamed(rows()[0], "Reject").click();
    panels()[0].querySelector("textarea").value = "  Sala e ocupata.  ";
    actionNamed(panels()[0], "Reject request").click();
    await flush();
    await flush();

    expect(JSON.parse(postsTo(fetch, "b1")[0][1].body)).toEqual({ decision: "reject", message: "Sala e ocupata." });
    expect(rows()).toHaveLength(1);
    expect(panels()).toHaveLength(0);
    expect($("bk-admin-status").textContent).toBe("The request was rejected.");
  });

  it("rejects without a message when the box is left blank", async () => {
    const { fetch } = await setup({
      routes: { "/api/admin/bookings/b1/decision": () => response({ id: "b1", status: "rejected" }) }
    });

    actionNamed(rows()[0], "Reject").click();
    actionNamed(panels()[0], "Reject request").click();
    await flush();
    await flush();

    expect(JSON.parse(postsTo(fetch, "b1")[0][1].body)).toEqual({ decision: "reject" });
  });

  it("keeps the panel open with an error when the rejection fails", async () => {
    await setup({
      routes: { "/api/admin/bookings/b1/decision": () => response({ detail: "x" }, 500) }
    });

    actionNamed(rows()[0], "Reject").click();
    actionNamed(panels()[0], "Reject request").click();
    await flush();

    expect(panels()).toHaveLength(1);
    expect($("bk-admin-status").textContent).toBe("Something went wrong. Try again.");
  });

  it("shows the empty card once the last request has been decided", async () => {
    await setup({
      routes: {
        "/api/admin/bookings/pending": () => response([REQUESTS[0]]),
        "/api/admin/bookings/b1/decision": () => response({ id: "b1", status: "approved" })
      }
    });

    actionNamed(rows()[0], "Accept").click();
    await flush();
    await flush();

    expect(rows()).toHaveLength(0);
    expect($("bk-admin-empty").hidden).toBe(false);
  });

  it("sends one decision at a time: a second click while one is waiting is ignored", async () => {
    const late = deferred();
    const { fetch } = await setup({
      routes: { "/api/admin/bookings/b1/decision": () => late.promise.then(() => response({ id: "b1" })) }
    });

    actionNamed(rows()[0], "Accept").click();
    actionNamed(rows()[0], "Accept").click();
    late.resolve();
    await flush();
    await flush();

    expect(postsTo(fetch, "b1")).toHaveLength(1);
  });

  it("keeps the status line empty on a language change when nothing has happened", async () => {
    await setup();

    document.dispatchEvent(new CustomEvent("unispace:langchange"));

    expect($("bk-admin-status").hidden).toBe(true);
  });

  it("writes the words, the list and the status line again in the new language", async () => {
    await setup({
      routes: { "/api/admin/bookings/b1/decision": () => response({ detail: "clash" }, 409) }
    });
    actionNamed(rows()[0], "Accept").click();
    await flush();

    window.UniSpaceI18n.setLanguage("ro");
    await flush();

    expect($("bk-admin-status").textContent).toBe(
      "Sala este ocupată la acest interval. Respinge cererea sau cere solicitantului alt interval."
    );
    expect(rows()[0].textContent).toContain("Organizație studențească");
    expect(rows()[0].textContent).toContain("Acceptă");
    window.UniSpaceI18n.setLanguage("en");
  });
});

describe("admin page without its queue", () => {
  beforeEach(() => vi.resetModules());
  afterEach(tidy);

  it("stops without calling the API", async () => {
    mountPage("pages/admin/index.html");
    $("bk-admin-queue").remove();
    await loadI18n("en");
    window.UniSpaceI18n.setLanguage("en");
    await loadScript("js/api.js");
    const fetch = stubFetch({ "/api/admin/bookings/pending": () => response([]) });
    await loadScript("js/pages/admin-bookings.js");
    await flush();

    expect(fetch).not.toHaveBeenCalled();
  });
});
