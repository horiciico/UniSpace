import { beforeEach, describe, expect, it, vi } from "vitest";
import { loadI18n, loadScript } from "../helpers.js";

const STUDENT = { id: "u1", name: "Ana <Pop>", email: "ana@ulbsibiu.ro", role: "STUDENT" };
const ADMIN = { id: "u2", name: "Ion", email: "ion@ulbsibiu.ro", role: "ADMIN" };

// Loads the components the header uses, with a stand-in for the session script.
async function loadHeader({ path = "/" } = {}) {
  vi.resetModules();
  window.history.replaceState(null, "", path);
  await loadI18n("en");
  window.UniSpaceAuth = {
    roleLabel: vi.fn((role) => role.toLowerCase()),
    logout: vi.fn(),
    ready: Promise.resolve(null)
  };
  await loadScript("components/ui.js");
  await loadScript("components/language-toggle.js");
  await loadScript("components/theme-toggle.js");
  await loadScript("components/header.js");
  return window.UniSpaceUI;
}

const header = () => document.querySelector("header.site-header");
const navLinks = () => [...document.querySelectorAll("nav.nav a")];

describe("header.js: the site header", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  describe("signed out", () => {
    it("shows the brand, the theme and language buttons, and no navigation", async () => {
      const UI = await loadHeader();
      UI.buildHeader(null);
      expect(header()).not.toBeNull();
      expect(header().querySelector(".brand").textContent).toBe("UniSpace");
      expect(header().querySelector(".brand__mark").getAttribute("src")).toBe("/public/brand-mark.png");
      expect(header().querySelector(".skip-link").getAttribute("href")).toBe("#main");
      expect(header().querySelector(".theme-toggle")).not.toBeNull();
      expect(header().querySelector(".lang-toggle")).not.toBeNull();
      expect(document.querySelector("nav.nav")).toBeNull();
      expect(document.querySelector(".nav-toggle")).toBeNull();
      expect(document.querySelector(".logout")).toBeNull();
    });

    it("puts the header first in the page", async () => {
      const UI = await loadHeader();
      document.body.innerHTML = "<main>Page</main>";
      UI.buildHeader(null);
      expect(document.body.firstElementChild).toBe(header());
    });
  });

  describe("signed in", () => {
    it("lists the navigation, without the admin page, for a student", async () => {
      const UI = await loadHeader();
      UI.buildHeader(STUDENT);
      const labels = navLinks().map((a) => a.textContent);
      expect(labels).toEqual(["Timetable", "Rooms", "Free now", "Bookings", "Announcements", "Changes", "Calendar"]);
      expect(navLinks().some((a) => a.getAttribute("href") === "/admin/")).toBe(false);
    });

    it("also lists the admin page for an administrator", async () => {
      const UI = await loadHeader();
      UI.buildHeader(ADMIN);
      const admin = navLinks().find((a) => a.getAttribute("href") === "/admin/");
      expect(admin.textContent).toBe("Admin");
    });

    it("marks the page the visitor is on", async () => {
      const UI = await loadHeader({ path: "/rooms/" });
      UI.buildHeader(STUDENT);
      const current = navLinks().filter((a) => a.getAttribute("aria-current") === "page");
      expect(current.map((a) => a.getAttribute("href"))).toEqual(["/rooms/"]);
    });

    it("marks nothing when the page is not in the navigation", async () => {
      const UI = await loadHeader({ path: "/elsewhere" });
      UI.buildHeader(STUDENT);
      expect(navLinks().some((a) => a.hasAttribute("aria-current"))).toBe(false);
    });

    it("shows the user's name, escaped, and the role label", async () => {
      const UI = await loadHeader();
      UI.buildHeader(STUDENT);
      const chip = document.querySelector(".user-chip");
      expect(chip.textContent).toBe("Ana <Pop> · student");
      expect(chip.innerHTML).toContain("&lt;Pop&gt;");
      expect(window.UniSpaceAuth.roleLabel).toHaveBeenCalledWith("STUDENT");
    });

    it("opens and closes the menu on small screens, and says so", async () => {
      const UI = await loadHeader();
      UI.buildHeader(STUDENT);
      const toggle = document.querySelector(".nav-toggle");
      const nav = document.querySelector("nav.nav");
      toggle.click();
      expect(nav.classList.contains("is-open")).toBe(true);
      expect(toggle.getAttribute("aria-expanded")).toBe("true");
      toggle.click();
      expect(nav.classList.contains("is-open")).toBe(false);
      expect(toggle.getAttribute("aria-expanded")).toBe("false");
    });

    it("signs out from the log out button, and cannot be pressed twice", async () => {
      const UI = await loadHeader();
      UI.buildHeader(STUDENT);
      const button = document.querySelector(".logout");
      button.click();
      expect(button.disabled).toBe(true);
      expect(window.UniSpaceAuth.logout).toHaveBeenCalledTimes(1);
    });

    it("builds a fresh header each time, one after another", async () => {
      const UI = await loadHeader();
      UI.buildHeader(STUDENT);
      UI.buildHeader(ADMIN);
      expect(document.querySelectorAll("header.site-header")).toHaveLength(2);
    });
  });

  describe("the user's name on the page", () => {
    it("fills every [data-user-name] with the user's name", async () => {
      const UI = await loadHeader();
      document.body.innerHTML = '<span data-user-name></span><span data-user-name></span>';
      UI.fillUserName(STUDENT);
      expect([...document.querySelectorAll("[data-user-name]")].map((el) => el.textContent))
        .toEqual(["Ana <Pop>", "Ana <Pop>"]);
    });

    it("writes the guest word when nobody is signed in", async () => {
      const UI = await loadHeader();
      document.body.innerHTML = '<span data-user-name></span>';
      UI.fillUserName(null);
      expect(document.querySelector("[data-user-name]").textContent).toBe(window.UniSpaceI18n.t("common.guest"));
    });
  });
});
