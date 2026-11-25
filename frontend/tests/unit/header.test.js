import { beforeEach, describe, expect, it, vi } from "vitest";
import { loadI18n, loadScript } from "../helpers.js";

const STUDENT = {
  id: "u1",
  name: "Ana <Pop>",
  email: "ana@ulbsibiu.ro",
  role: "STUDENT",
};
const ADMIN = {
  id: "u2",
  name: "Ion",
  email: "ion@ulbsibiu.ro",
  role: "ADMIN",
};

// Loads the components the header uses, with a stand-in for the session script.
async function loadHeader({ path = "/" } = {}) {
  vi.resetModules();
  window.history.replaceState(null, "", path);
  await loadI18n("en");
  window.UniSpaceAuth = {
    roleLabel: vi.fn((role) => role.toLowerCase()),
    logout: vi.fn(),
    ready: Promise.resolve(null),
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
      expect(header().querySelector(".brand__mark").getAttribute("src")).toBe(
        "/public/brand-mark.png",
      );
      expect(header().querySelector(".skip-link").getAttribute("href")).toBe(
        "#main",
      );
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
      expect(labels).toEqual([
        "Timetable",
        "Rooms",
        "Free now",
        "Bookings",
        "Announcements",
        "Changes",
        "Calendar",
      ]);
      expect(navLinks().some((a) => a.getAttribute("href") === "/admin/")).toBe(
        false,
      );
    });

    it("also lists the admin page for an administrator", async () => {
      const UI = await loadHeader();
      UI.buildHeader(ADMIN);
      const admin = navLinks().find(
        (a) => a.getAttribute("href") === "/admin/",
      );
      expect(admin.textContent).toBe("Admin");
    });

    it("marks the page the visitor is on", async () => {
      const UI = await loadHeader({ path: "/rooms/" });
      UI.buildHeader(STUDENT);
      const current = navLinks().filter(
        (a) => a.getAttribute("aria-current") === "page",
      );
      expect(current.map((a) => a.getAttribute("href"))).toEqual(["/rooms/"]);
    });

    it("marks nothing when the page is not in the navigation", async () => {
      const UI = await loadHeader({ path: "/elsewhere" });
      UI.buildHeader(STUDENT);
      expect(navLinks().some((a) => a.hasAttribute("aria-current"))).toBe(
        false,
      );
    });

    it("shows the user's name, escaped, and the role label", async () => {
      const UI = await loadHeader();
      UI.buildHeader(STUDENT);
      const chip = document.querySelector(".user-chip");
      expect(chip.textContent).toBe("Ana <Pop> · student");
      expect(chip.innerHTML).toContain("&lt;Pop&gt;");
      expect(window.UniSpaceAuth.roleLabel).toHaveBeenCalledWith("STUDENT");
    });

    it("renders user avatar when profile picture is provided", async () => {
      const UI = await loadHeader();
      UI.buildHeader({ ...STUDENT, picture: "https://example.com/avatar.jpg" });
      const avatar = document.querySelector("img.user-avatar");
      expect(avatar).not.toBeNull();
      expect(avatar.getAttribute("src")).toBe("https://example.com/avatar.jpg");
      expect(avatar.getAttribute("width")).toBe("32");
    });

    it("renders placeholder avatar when profile picture is not provided", async () => {
      const UI = await loadHeader();
      UI.buildHeader(STUDENT);
      const placeholder = document.querySelector(".user-avatar--placeholder");
      expect(placeholder).not.toBeNull();
      expect(placeholder.textContent).toBe("A");
    });

    it("does not render a menu toggle button", async () => {
      const UI = await loadHeader();
      UI.buildHeader(STUDENT);
      expect(document.querySelector(".nav-toggle")).toBeNull();
    });

    it("unfolds options (theme, settings, logout) when clicking the profile picture", async () => {
      const UI = await loadHeader();
      UI.buildHeader(STUDENT);
      const trigger = document.querySelector(".profile-menu__trigger");
      const dropdown = document.querySelector(".profile-menu__dropdown");

      expect(dropdown.hidden).toBe(true);
      expect(trigger.getAttribute("aria-expanded")).toBe("false");

      trigger.click();
      expect(dropdown.hidden).toBe(false);
      expect(trigger.getAttribute("aria-expanded")).toBe("true");
      expect(dropdown.querySelector(".theme-toggle")).not.toBeNull();
      expect(dropdown.querySelector('a[href="/settings"]')).not.toBeNull();
      expect(dropdown.querySelector(".logout")).not.toBeNull();

      trigger.click();
      expect(dropdown.hidden).toBe(true);
      expect(trigger.getAttribute("aria-expanded")).toBe("false");
    });

    it("closes the profile menu when clicking outside", async () => {
      const UI = await loadHeader();
      UI.buildHeader(STUDENT);
      const trigger = document.querySelector(".profile-menu__trigger");
      const dropdown = document.querySelector(".profile-menu__dropdown");

      trigger.click();
      expect(dropdown.hidden).toBe(false);

      dropdown.click();
      expect(dropdown.hidden).toBe(false);

      document.body.click();
      expect(dropdown.hidden).toBe(true);
      expect(trigger.getAttribute("aria-expanded")).toBe("false");
    });

    it("closes the profile menu on Escape key press and restores focus", async () => {
      const UI = await loadHeader();
      UI.buildHeader(STUDENT);
      const trigger = document.querySelector(".profile-menu__trigger");
      const dropdown = document.querySelector(".profile-menu__dropdown");

      trigger.click();
      expect(dropdown.hidden).toBe(false);

      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab" }));
      expect(dropdown.hidden).toBe(false);

      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
      expect(dropdown.hidden).toBe(true);
      expect(trigger.getAttribute("aria-expanded")).toBe("false");

      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
      expect(dropdown.hidden).toBe(true);
    });

    it("signs out from the log out button, and cannot be pressed twice", async () => {
      const UI = await loadHeader();
      UI.buildHeader(STUDENT);
      const button = document.querySelector(".logout");
      button.click();
      expect(button.disabled).toBe(true);
      expect(window.UniSpaceAuth.logout).toHaveBeenCalledTimes(1);
    });

    it("removes document listeners when rebuilding the header", async () => {
      const UI = await loadHeader();
      const removeSpy = vi.spyOn(document, "removeEventListener");
      UI.buildHeader(STUDENT);
      expect(removeSpy).not.toHaveBeenCalled();
      UI.buildHeader(STUDENT);
      expect(removeSpy).toHaveBeenCalledWith("click", expect.any(Function));
      expect(removeSpy).toHaveBeenCalledWith("keydown", expect.any(Function));
      removeSpy.mockClear();
      UI.buildHeader(null);
      expect(removeSpy).toHaveBeenCalledWith("click", expect.any(Function));
      expect(removeSpy).toHaveBeenCalledWith("keydown", expect.any(Function));
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
      document.body.innerHTML =
        "<span data-user-name></span><span data-user-name></span>";
      UI.fillUserName(STUDENT);
      expect(
        [...document.querySelectorAll("[data-user-name]")].map(
          (el) => el.textContent,
        ),
      ).toEqual(["Ana <Pop>", "Ana <Pop>"]);
    });

    it("writes the guest word when nobody is signed in", async () => {
      const UI = await loadHeader();
      document.body.innerHTML = "<span data-user-name></span>";
      UI.fillUserName(null);
      expect(document.querySelector("[data-user-name]").textContent).toBe(
        window.UniSpaceI18n.t("common.guest"),
      );
    });
  });
});
