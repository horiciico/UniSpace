import { beforeEach, describe, expect, it, vi } from "vitest";
import { loadI18n, loadScript } from "../helpers.js";

describe("language-toggle.js: the RO | EN switch", () => {
  beforeEach(async () => {
    vi.resetModules();
    await loadI18n("en");
    await loadScript("components/ui.js");
    await loadScript("components/language-toggle.js");
  });

  it("builds one button per language, and marks the current one", () => {
    const group = window.UniSpaceUI.languageToggle();
    expect(group.getAttribute("role")).toBe("group");
    expect(group.getAttribute("aria-label")).toBe(window.UniSpaceI18n.t("header.language"));
    const buttons = [...group.querySelectorAll("button")];
    expect(buttons.map((b) => b.textContent)).toEqual(["RO", "EN"]);
    expect(buttons.map((b) => b.getAttribute("aria-pressed"))).toEqual(["false", "true"]);
    expect(buttons[0].dataset.lang).toBe("ro");
  });

  it("switches the language when a button is clicked", () => {
    const group = window.UniSpaceUI.languageToggle();
    document.body.appendChild(group);
    group.querySelector('[data-lang="ro"]').click();
    expect(window.UniSpaceI18n.current()).toBe("ro");
    expect(localStorage.getItem("unispace-lang")).toBe("ro");
  });

  it("does nothing when the group itself is clicked", () => {
    const group = window.UniSpaceUI.languageToggle();
    document.body.appendChild(group);
    group.click();
    expect(window.UniSpaceI18n.current()).toBe("en");
  });
});

describe("theme-toggle.js: the auto, light and dark button", () => {
  beforeEach(async () => {
    vi.resetModules();
    document.documentElement.removeAttribute("data-theme");
    await loadI18n("en");
    await loadScript("components/ui.js");
    await loadScript("components/theme-toggle.js");
  });

  it("reads the saved theme, and follows the system when none is saved", () => {
    expect(window.UniSpaceUI.currentTheme()).toBe("auto");
    localStorage.setItem("unispace-theme", "dark");
    expect(window.UniSpaceUI.currentTheme()).toBe("dark");
  });

  it("sets the theme on the page, and names it on the button", () => {
    document.body.innerHTML = '<button class="theme-toggle"></button>';
    window.UniSpaceUI.applyTheme("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(document.querySelector(".theme-toggle").textContent).toBe(window.UniSpaceI18n.t("theme.dark"));
  });

  it("removes the override for auto, so the system setting applies", () => {
    document.documentElement.setAttribute("data-theme", "light");
    window.UniSpaceUI.applyTheme("auto");
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
  });

  it("applies the theme even when there is no button", () => {
    expect(() => window.UniSpaceUI.applyTheme("light")).not.toThrow();
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("does nothing on bind when the page has no button", () => {
    expect(() => window.UniSpaceUI.bindTheme()).not.toThrow();
  });

  it("cycles auto, light, dark and back, and keeps each choice", () => {
    document.body.innerHTML = '<button class="theme-toggle"></button>';
    window.UniSpaceUI.bindTheme();
    const button = document.querySelector(".theme-toggle");
    button.click();
    expect(localStorage.getItem("unispace-theme")).toBe("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    button.click();
    expect(localStorage.getItem("unispace-theme")).toBe("dark");
    button.click();
    expect(localStorage.getItem("unispace-theme")).toBe("auto");
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
  });

  it("applies the saved theme when the button is bound", () => {
    localStorage.setItem("unispace-theme", "light");
    document.body.innerHTML = '<button class="theme-toggle"></button>';
    window.UniSpaceUI.bindTheme();
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(document.querySelector(".theme-toggle").textContent).toBe(window.UniSpaceI18n.t("theme.light"));
  });

  it("saves each click's choice in storage", () => {
    document.body.innerHTML = '<button class="theme-toggle"></button>';
    window.UniSpaceUI.bindTheme();
    const spy = vi.spyOn(Storage.prototype, "setItem");
    document.querySelector(".theme-toggle").click();
    expect(spy).toHaveBeenCalledWith("unispace-theme", "light");
  });
});
