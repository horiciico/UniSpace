import { beforeEach, describe, expect, it, vi } from "vitest";
import { deferred, flush, loadI18n, loadScript } from "../helpers.js";

const STUDENT = { id: "u1", name: "Ana", email: "ana@ulbsibiu.ro", role: "STUDENT" };

// Loads the shared chrome in the order head.html does, with the session as a promise the
// test settles (the real session script waits for /auth/me).
async function loadChrome({ language = "en" } = {}) {
  vi.resetModules();
  document.body.innerHTML = '<main><span data-user-name></span></main>';
  await loadI18n(language);
  const session = deferred();
  window.UniSpaceAuth = {
    ready: session.promise,
    roleLabel: (role) => role,
    logout: vi.fn()
  };
  await loadScript("components/ui.js");
  await loadScript("components/language-toggle.js");
  await loadScript("components/theme-toggle.js");
  await loadScript("components/header.js");
  await loadScript("components/footer.js");
  await loadScript("components/toast.js");
  await loadScript("components/app.js");
  return session;
}

const count = (selector) => document.querySelectorAll(selector).length;

describe("app.js: the shared chrome", () => {
  beforeEach(() => {
    localStorage.removeItem("unispace-theme");
    document.documentElement.removeAttribute("data-theme");
  });

  it("applies the saved theme at once, before the session is known", async () => {
    localStorage.setItem("unispace-theme", "dark");
    await loadChrome();
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(count("header.site-header")).toBe(0);
  });

  it("builds the header, the name and the footer once the session is known", async () => {
    const session = await loadChrome();
    session.resolve(STUDENT);
    await flush();
    expect(count("header.site-header")).toBe(1);
    expect(count("footer.site-footer")).toBe(1);
    expect(document.querySelector("[data-user-name]").textContent).toBe("Ana");
    expect(document.querySelector(".user-chip")).not.toBeNull();
  });

  it("builds the chrome for a visitor who is signed out, with no navigation", async () => {
    const session = await loadChrome();
    session.resolve(null);
    await flush();
    expect(count("header.site-header")).toBe(1);
    expect(count("nav.nav")).toBe(0);
    expect(document.querySelector("[data-user-name]").textContent).toBe(window.UniSpaceI18n.t("common.guest"));
  });

  it("wires the theme button and the placeholder actions", async () => {
    const session = await loadChrome();
    session.resolve(null);
    await flush();
    document.querySelector(".theme-toggle").click();
    expect(localStorage.getItem("unispace-theme")).toBe("light");
    document.body.insertAdjacentHTML("beforeend", '<button id="later" data-placeholder-action="placeholder.approved"></button>');
    document.getElementById("later").click();
    expect(document.getElementById("toast").textContent).toBe(window.UniSpaceI18n.t("placeholder.approved"));
  });

  it("does nothing on a language change before the session is known", async () => {
    await loadChrome();
    window.UniSpaceI18n.setLanguage("ro");
    await flush();
    expect(count("header.site-header")).toBe(0);
  });

  it("rebuilds the chrome in the new language, with one header and one footer", async () => {
    const session = await loadChrome();
    session.resolve(STUDENT);
    await flush();
    window.UniSpaceI18n.setLanguage("ro");
    await flush();
    expect(count("header.site-header")).toBe(1);
    expect(count("footer.site-footer")).toBe(1);
    expect(document.querySelector(".logout").textContent).toBe(window.UniSpaceI18n.t("header.logout"));
    expect(document.querySelector(".user-chip")).not.toBeNull();
    expect(document.querySelector("[data-user-name]").textContent).toBe("Ana");
  });
});
