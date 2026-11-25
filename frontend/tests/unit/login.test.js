import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  deferred,
  flush,
  loadI18n,
  loadScript,
  mountPage,
} from "../helpers.js";

const realLocation = window.location;

// The login page, with the URL it was opened with (for example ?error=denied). The session
// stand-in answers with `user` (null when signed out).
async function loadLogin({
  search = "",
  user = null,
  language = "en",
  withoutBox = false,
} = {}) {
  vi.resetModules();
  const replace = vi.fn();
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { pathname: "/login", search, replace },
  });
  mountPage("pages/shared/login.html");
  if (withoutBox) document.getElementById("login-error").remove();
  await loadI18n(language);
  const session = deferred();
  window.UniSpaceAuth = { ready: session.promise };
  await loadScript("js/pages/login.js");
  session.resolve(user);
  await flush();
  return { replace };
}

const box = () => document.getElementById("login-error");

describe("login.js: the sign-in page", () => {
  afterEach(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: realLocation,
    });
  });

  beforeEach(() => {
    vi.resetModules();
  });

  it("stays hidden when the page is opened without a reason", async () => {
    await loadLogin();
    expect(box().hidden).toBe(true);
  });

  it("explains a denied sign-in", async () => {
    await loadLogin({ search: "?error=denied" });
    expect(box().hidden).toBe(false);
    expect(document.getElementById("login-error-title").textContent).toBe(
      window.UniSpaceI18n.t("login.deniedTitle"),
    );
    expect(document.getElementById("login-error-text").textContent).toBe(
      window.UniSpaceI18n.t("login.deniedText"),
    );
  });

  it("explains a failed sign-in", async () => {
    await loadLogin({ search: "?error=failed" });
    expect(box().hidden).toBe(false);
    expect(document.getElementById("login-error-title").textContent).toBe(
      window.UniSpaceI18n.t("login.failedTitle"),
    );
  });

  it("ignores any other reason in the address", async () => {
    await loadLogin({ search: "?error=<script>" });
    expect(box().hidden).toBe(true);
    expect(document.getElementById("login-error-title").textContent).toBe("");
  });

  it("explains the reason again in the new language", async () => {
    await loadLogin({ search: "?error=denied" });
    const english = document.getElementById("login-error-title").textContent;
    window.UniSpaceI18n.setLanguage("ro");
    await flush();
    expect(document.getElementById("login-error-title").textContent).toBe(
      window.UniSpaceI18n.t("login.deniedTitle"),
    );
    expect(document.getElementById("login-error-title").textContent).not.toBe(
      english,
    );
  });

  it("hides the explanation after a language change when there is no reason", async () => {
    await loadLogin();
    window.UniSpaceI18n.setLanguage("ro");
    await flush();
    expect(box().hidden).toBe(true);
  });

  it("sends a visitor who is already signed in to the home page", async () => {
    const { replace } = await loadLogin({
      user: { id: "u1", name: "Ana", role: "STUDENT" },
    });
    expect(replace).toHaveBeenCalledWith("/");
  });

  it("keeps a signed-out visitor on the page", async () => {
    const { replace } = await loadLogin({ user: null });
    expect(replace).not.toHaveBeenCalled();
  });

  it("does nothing with the message box when the page has none", async () => {
    await expect(
      loadLogin({ search: "?error=denied", withoutBox: true }),
    ).resolves.toBeDefined();
    expect(box()).toBeNull();
  });
});
