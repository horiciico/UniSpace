import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  deferred,
  flush,
  loadI18n,
  loadScript,
  mountPage,
} from "../helpers.js";

const realLocation = window.location;
const $ = (id) => document.getElementById(id);
const dialog = () => $("admin-dialog");

// The login page with the admin modal. `replace` stands in for window.location.replace.
async function loadAdminLogin({ language = "en" } = {}) {
  vi.resetModules();
  const replace = vi.fn();
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { pathname: "/login", search: "", replace },
  });
  mountPage("pages/shared/login.html");
  await loadI18n(language);
  await loadScript("components/admin-login.js");
  return { replace };
}

// A fetch stub that answers with `result`, or waits for a promise the test settles by hand.
function fetchAnswers(result) {
  const fetch = vi.fn(() => result);
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

const ok = () => ({
  ok: true,
  status: 200,
  json: () => Promise.resolve({ role: "ADMIN" }),
});
const status = (code) => ({
  ok: false,
  status: code,
  json: () => Promise.resolve({}),
});

function type(id, value) {
  $(id).value = value;
}

function press(key, options = {}, target = document) {
  target.dispatchEvent(
    new KeyboardEvent("keydown", {
      key,
      bubbles: true,
      cancelable: true,
      ...options,
    }),
  );
}

function submitForm() {
  $("admin-form").dispatchEvent(
    new Event("submit", { bubbles: true, cancelable: true }),
  );
}

describe("admin-login.js: the administrator sign-in modal", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: realLocation,
    });
    vi.unstubAllGlobals();
  });

  it("keeps the dialog hidden until the link is pressed, then focuses the username", async () => {
    await loadAdminLogin();
    expect(dialog().hidden).toBe(true);

    $("admin-open").click();

    expect(dialog().hidden).toBe(false);
    expect(document.activeElement).toBe($("admin-username"));
  });

  it("closes with Cancel, clears the password and gives the focus back to the link", async () => {
    await loadAdminLogin();
    $("admin-open").click();
    type("admin-username", "admin");
    type("admin-password", "secret");

    $("admin-cancel").click();

    expect(dialog().hidden).toBe(true);
    expect($("admin-password").value).toBe("");
    expect(document.activeElement).toBe($("admin-open"));
  });

  it("closes with Escape, and ignores Escape while it is already closed", async () => {
    await loadAdminLogin();
    press("Escape");
    expect(dialog().hidden).toBe(true);

    $("admin-open").click();
    press("Escape");
    expect(dialog().hidden).toBe(true);
  });

  it("ignores other keys while open", async () => {
    await loadAdminLogin();
    $("admin-open").click();
    press("a");
    expect(dialog().hidden).toBe(false);
  });

  it("keeps Tab inside the dialog, going forward from the last control to the first", async () => {
    await loadAdminLogin();
    $("admin-open").click();
    $("admin-submit").focus();

    press("Tab");

    expect(document.activeElement).toBe($("admin-username"));
  });

  it("keeps Shift+Tab inside the dialog, going back from the first control to the last", async () => {
    await loadAdminLogin();
    $("admin-open").click();

    press("Tab", { shiftKey: true });

    expect(document.activeElement).toBe($("admin-submit"));
  });

  it("leaves Tab alone between the first and the last control", async () => {
    await loadAdminLogin();
    $("admin-open").click();
    $("admin-password").focus();

    press("Tab");
    press("Tab", { shiftKey: true });

    expect(document.activeElement).toBe($("admin-password"));
  });

  it("posts the username and password as JSON to /auth/admin-login, and loads the home page on success", async () => {
    const { replace } = await loadAdminLogin();
    const fetch = fetchAnswers(Promise.resolve(ok()));
    $("admin-open").click();
    type("admin-username", "admin");
    type("admin-password", "s3cret");

    submitForm();
    await flush();

    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe("/auth/admin-login");
    expect(options.method).toBe("POST");
    expect(options.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(options.body)).toEqual({
      username: "admin",
      password: "s3cret",
    });
    expect(replace).toHaveBeenCalledWith("/");
  });

  it("shows the wrong-credentials message on 401, keeps the dialog open and clears the password", async () => {
    const { replace } = await loadAdminLogin();
    fetchAnswers(Promise.resolve(status(401)));
    $("admin-open").click();
    type("admin-username", "admin");
    type("admin-password", "wrong");

    submitForm();
    await flush();

    expect(dialog().hidden).toBe(false);
    expect($("admin-error").hidden).toBe(false);
    expect($("admin-error").textContent).toBe(
      window.UniSpaceI18n.t("admin.invalid"),
    );
    expect($("admin-username").getAttribute("aria-invalid")).toBe("true");
    expect($("admin-password").value).toBe("");
    expect(document.activeElement).toBe($("admin-password"));
    expect(replace).not.toHaveBeenCalled();
  });

  it("shows the could-not-reach message for another server error, without marking the fields", async () => {
    await loadAdminLogin();
    fetchAnswers(Promise.resolve(status(500)));
    $("admin-open").click();

    submitForm();
    await flush();

    expect($("admin-error").textContent).toBe(
      window.UniSpaceI18n.t("admin.failed"),
    );
    expect($("admin-password").getAttribute("aria-invalid")).toBe("false");
  });

  it("shows the could-not-reach message when the request fails", async () => {
    await loadAdminLogin();
    fetchAnswers(Promise.reject(new TypeError("network down")));
    $("admin-open").click();

    submitForm();
    await flush();

    expect($("admin-error").textContent).toBe(
      window.UniSpaceI18n.t("admin.failed"),
    );
  });

  it("sends one request at a time and disables Sign in while it waits", async () => {
    await loadAdminLogin();
    const answer = deferred();
    const fetch = fetchAnswers(answer.promise);
    $("admin-open").click();

    submitForm();
    submitForm();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect($("admin-submit").disabled).toBe(true);

    answer.resolve(status(401));
    await flush();
    expect($("admin-submit").disabled).toBe(false);
  });

  it("explains a wrong password again in the new language", async () => {
    await loadAdminLogin();
    fetchAnswers(Promise.resolve(status(401)));
    $("admin-open").click();
    submitForm();
    await flush();
    const english = $("admin-error").textContent;

    window.UniSpaceI18n.setLanguage("ro");
    await flush();

    expect($("admin-error").textContent).toBe(
      window.UniSpaceI18n.t("admin.invalid"),
    );
    expect($("admin-error").textContent).not.toBe(english);
  });

  it("clears the message when the dialog is closed", async () => {
    await loadAdminLogin();
    fetchAnswers(Promise.resolve(status(401)));
    $("admin-open").click();
    submitForm();
    await flush();

    $("admin-cancel").click();

    expect($("admin-error").hidden).toBe(true);
    expect($("admin-error").textContent).toBe("");
    expect($("admin-username").getAttribute("aria-invalid")).toBe("false");
  });

  it("closes safely when Cancel is pressed before the dialog was ever opened", async () => {
    await loadAdminLogin();
    expect(() => $("admin-cancel").click()).not.toThrow();
    expect(dialog().hidden).toBe(true);
  });

  it("does nothing on a page without the admin link", async () => {
    vi.resetModules();
    document.body.innerHTML = "<main><p>No admin link here</p></main>";
    await loadI18n("en");
    await expect(
      loadScript("components/admin-login.js"),
    ).resolves.toBeUndefined();
    expect(document.getElementById("admin-open")).toBeNull();
  });
});
