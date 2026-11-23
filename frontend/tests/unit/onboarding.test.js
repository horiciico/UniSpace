import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { deferred, flush, loadI18n, loadScript, queryOf, response, stubFetch } from "../helpers.js";

const realLocation = window.location;
const $ = (id) => document.getElementById(id);
const panel = () => document.getElementById("onboarding");

const FACULTIES = [
  { id: "f1", code: "ing", name: "Inginerie" },
  { id: "f2", code: "dre", name: "Drept" }
];
const FORMATIONS = [
  { id: "g1", name: "332CA", faculty_id: "f1" },
  { id: "g2", name: "331AB", faculty_id: "f1" }
];
const NEW_STUDENT = { id: "u1", email: "ana@ulbsibiu.ro", name: "Ana", role: "STUDENT", needs_onboarding: true };

// The default answers of the backend: all faculties; formations only for f1.
function defaultRoutes(overrides = {}) {
  return {
    "/api/faculties": () => response(FACULTIES),
    "/api/groups": (url) => response(queryOf(url).faculty_id === "f1" ? FORMATIONS : []),
    "/api/me/study-profile": () => response({ ...NEW_STUDENT, needs_onboarding: false }),
    ...overrides
  };
}

// Loads the real api.js and the component for a visitor, the way head.html does.
async function start({ user = NEW_STUDENT, path = "/", routes = defaultRoutes() } = {}) {
  vi.resetModules();
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { pathname: path, search: "", replace: vi.fn(), assign: vi.fn() }
  });
  document.body.innerHTML = "<main><p>The home page</p></main>";
  await loadI18n("en");
  window.UniSpaceAuth = { ready: Promise.resolve(user) };
  await loadScript("js/api.js");
  const fetch = stubFetch(routes);
  await loadScript("components/onboarding.js");
  await flush();
  return { fetch };
}

function choose(id, value) {
  const select = $(id);
  select.value = value;
  select.dispatchEvent(new Event("change"));
}

function submitForm() {
  $("onboarding-form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
}

function press(key, options = {}, target = document) {
  target.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true, ...options }));
}

const optionValues = (id) => Array.from($(id).options).map((option) => option.value);

describe("onboarding.js: a student's faculty and study formation", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    Object.defineProperty(window, "location", { configurable: true, value: realLocation });
    vi.unstubAllGlobals();
    delete window.UniSpaceAuth;
  });

  it("does nothing for a student who already has a faculty", async () => {
    await start({ user: { ...NEW_STUDENT, needs_onboarding: false } });
    expect(panel()).toBeNull();
  });

  it("does nothing for a signed-out visitor", async () => {
    await start({ user: null });
    expect(panel()).toBeNull();
  });

  it("does nothing on the login page, with or without the .html ending", async () => {
    await start({ path: "/login" });
    expect(panel()).toBeNull();
    document.body.innerHTML = "";
    await start({ path: "/pages/shared/login.html" });
    expect(panel()).toBeNull();
  });

  it("opens for a new student with the faculties listed and Save disabled", async () => {
    await start();

    expect(panel()).not.toBeNull();
    expect(optionValues("onboarding-faculty")).toEqual(["", "f1", "f2"]);
    expect($("onboarding-faculty").options[1].textContent).toBe("Inginerie");
    expect($("onboarding-formation").disabled).toBe(true);
    expect($("onboarding-formation").options[0].textContent).toBe("Choose a faculty first.");
    expect($("onboarding-save").disabled).toBe(true);
    expect(document.activeElement).toBe($("onboarding-faculty"));
  });

  it("lists the formations of the chosen faculty", async () => {
    const { fetch } = await start();

    choose("onboarding-faculty", "f1");
    await flush();

    const groupCall = fetch.mock.calls.find(([url]) => url.startsWith("/api/groups"));
    expect(queryOf(groupCall[0])).toEqual({ faculty_id: "f1" });
    expect(optionValues("onboarding-formation")).toEqual(["", "g1", "g2"]);
    expect($("onboarding-formation").disabled).toBe(false);
    expect($("onboarding-formation").options[0].textContent).toBe("Choose a study formation");
  });

  it("says so when a faculty has no formations, and keeps that list disabled", async () => {
    await start();

    choose("onboarding-faculty", "f2");
    await flush();

    expect($("onboarding-hint").hidden).toBe(false);
    expect($("onboarding-hint").textContent).toBe("No study formations are listed for this faculty yet.");
    expect($("onboarding-formation").disabled).toBe(true);
  });

  it("clears the formation when the faculty is set back to the placeholder", async () => {
    await start();
    choose("onboarding-faculty", "f1");
    await flush();
    choose("onboarding-formation", "g1");

    choose("onboarding-faculty", "");

    expect(optionValues("onboarding-formation")).toEqual([""]);
    expect($("onboarding-formation").disabled).toBe(true);
    expect($("onboarding-formation").options[0].textContent).toBe("Choose a faculty first.");
    expect($("onboarding-save").disabled).toBe(true);
    expect($("onboarding-hint").hidden).toBe(true);
  });

  it("enables Save only when both a faculty and a formation are chosen", async () => {
    await start();
    choose("onboarding-faculty", "f1");
    await flush();
    expect($("onboarding-save").disabled).toBe(true);

    choose("onboarding-formation", "g2");

    expect($("onboarding-save").disabled).toBe(false);
  });

  it("saves the choice as JSON, then the dialog goes away", async () => {
    const { fetch } = await start();
    choose("onboarding-faculty", "f1");
    await flush();
    choose("onboarding-formation", "g1");

    submitForm();
    await flush();

    const [url, options] = fetch.mock.calls.find(([called]) => called === "/api/me/study-profile");
    expect(url).toBe("/api/me/study-profile");
    expect(options.method).toBe("PUT");
    expect(options.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(options.body)).toEqual({ faculty_id: "f1", study_formation_id: "g1" });
    expect(panel()).toBeNull();
  });

  it("a language change after saving does not fail", async () => {
    await start();
    choose("onboarding-faculty", "f1");
    await flush();
    choose("onboarding-formation", "g1");
    submitForm();
    await flush();

    expect(() => window.UniSpaceI18n.setLanguage("ro")).not.toThrow();
  });

  it("keeps the dialog open with the message when the save is refused", async () => {
    await start({
      routes: defaultRoutes({ "/api/me/study-profile": () => response({ detail: "nope" }, 422) })
    });
    choose("onboarding-faculty", "f1");
    await flush();
    choose("onboarding-formation", "g1");

    submitForm();
    await flush();

    expect(panel()).not.toBeNull();
    expect($("onboarding-error").hidden).toBe(false);
    expect($("onboarding-error-text").textContent).toBe("Nothing was saved. Try again.");
    expect($("onboarding-retry").hidden).toBe(true);
    expect($("onboarding-save").disabled).toBe(false);
  });

  it("sends one save at a time and shows Saving while it waits", async () => {
    const answer = deferred();
    const { fetch } = await start({
      routes: defaultRoutes({ "/api/me/study-profile": () => answer.promise })
    });
    choose("onboarding-faculty", "f1");
    await flush();
    choose("onboarding-formation", "g1");

    submitForm();
    submitForm();

    expect(fetch.mock.calls.filter(([url]) => url === "/api/me/study-profile")).toHaveLength(1);
    expect($("onboarding-save").textContent).toBe("Saving…");
    expect($("onboarding-save").disabled).toBe(true);

    answer.resolve(response({ ...NEW_STUDENT, needs_onboarding: false }));
    await flush();
    expect(panel()).toBeNull();
  });

  it("ignores a submit until both choices are made", async () => {
    const { fetch } = await start();

    submitForm();
    await flush();

    expect(fetch.mock.calls.some(([url]) => url === "/api/me/study-profile")).toBe(false);
  });

  it("shows a load failure with Try again, which loads the faculties again", async () => {
    let calls = 0;
    await start({
      routes: defaultRoutes({
        "/api/faculties": () => {
          calls += 1;
          return calls === 1 ? response({ detail: "down" }, 500) : response(FACULTIES);
        }
      })
    });

    expect($("onboarding-error").hidden).toBe(false);
    expect($("onboarding-error-text").textContent).toBe("The list could not be loaded.");
    expect($("onboarding-retry").hidden).toBe(false);
    expect($("onboarding-faculty").disabled).toBe(true);

    $("onboarding-retry").click();
    await flush();

    expect(optionValues("onboarding-faculty")).toEqual(["", "f1", "f2"]);
    expect($("onboarding-error").hidden).toBe(true);
  });

  it("shows a formation load failure with Try again, which loads that faculty's formations", async () => {
    let calls = 0;
    await start({
      routes: defaultRoutes({
        "/api/groups": () => {
          calls += 1;
          return calls === 1 ? response({ detail: "down" }, 500) : response(FORMATIONS);
        }
      })
    });
    choose("onboarding-faculty", "f1");
    await flush();

    expect($("onboarding-error").hidden).toBe(false);
    expect($("onboarding-formation").disabled).toBe(true);

    $("onboarding-retry").click();
    await flush();

    expect(optionValues("onboarding-formation")).toEqual(["", "g1", "g2"]);
    expect($("onboarding-error").hidden).toBe(true);
  });

  it("drops a formation answer that arrives after another faculty was picked", async () => {
    const slow = deferred();
    await start({
      routes: defaultRoutes({
        "/api/groups": (url) => (queryOf(url).faculty_id === "f1" ? slow.promise : response([]))
      })
    });
    choose("onboarding-faculty", "f1");
    choose("onboarding-faculty", "f2");
    await flush();

    slow.resolve(response(FORMATIONS));
    await flush();

    expect(optionValues("onboarding-formation")).toEqual([""]);
    expect($("onboarding-hint").hidden).toBe(false);
  });

  it("ignores a failed formation answer that arrives after another faculty was picked", async () => {
    const slow = deferred();
    await start({
      routes: defaultRoutes({
        "/api/groups": (url) => (queryOf(url).faculty_id === "f1" ? slow.promise : response([]))
      })
    });
    choose("onboarding-faculty", "f1");
    choose("onboarding-faculty", "f2");
    await flush();

    slow.reject(new TypeError("network down"));
    await flush();

    expect($("onboarding-error").hidden).toBe(true);
    expect($("onboarding-formation").disabled).toBe(true);
  });

  it("does not close on Escape, and ignores other keys", async () => {
    await start();

    press("Escape");
    press("a");

    expect(panel()).not.toBeNull();
  });

  it("keeps Tab inside the dialog, both ways", async () => {
    await start();
    choose("onboarding-faculty", "f1");
    await flush();
    choose("onboarding-formation", "g1");
    $("onboarding-save").focus();

    press("Tab");
    expect(document.activeElement).toBe($("onboarding-faculty"));

    press("Tab", { shiftKey: true });
    expect(document.activeElement).toBe($("onboarding-save"));
  });

  it("leaves Tab alone between the first and the last control", async () => {
    await start();
    choose("onboarding-faculty", "f1");
    await flush();
    $("onboarding-formation").focus();

    press("Tab");
    press("Tab", { shiftKey: true });

    expect(document.activeElement).toBe($("onboarding-formation"));
  });

  it("translates the dialog when the language changes", async () => {
    await start();

    window.UniSpaceI18n.setLanguage("ro");
    await flush();

    expect($("onboarding-title").textContent).toBe("Datele tale de studiu");
    expect($("onboarding-faculty-label").textContent).toBe("Facultatea");
    expect($("onboarding-faculty").options[0].textContent).toBe("Alege facultatea");
  });
});
