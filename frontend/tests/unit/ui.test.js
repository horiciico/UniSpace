import { beforeEach, describe, expect, it, vi } from "vitest";
import { loadI18n, loadScript } from "../helpers.js";

describe("ui.js and footer.js: shared helpers and the footer", () => {
  beforeEach(async () => {
    vi.resetModules();
    await loadI18n("en");
    await loadScript("components/ui.js");
  });

  describe("escapeHtml", () => {
    it("escapes the characters that are special in HTML", () => {
      expect(
        window.UniSpaceUI.escapeHtml(`<a href="x">Tom & 'Jerry'</a>`),
      ).toBe("&lt;a href=&quot;x&quot;&gt;Tom &amp; &#39;Jerry&#39;&lt;/a&gt;");
    });

    it("leaves plain text alone, and turns numbers into text", () => {
      expect(window.UniSpaceUI.escapeHtml("Sala 101")).toBe("Sala 101");
      expect(window.UniSpaceUI.escapeHtml(42)).toBe("42");
    });
  });

  describe("normalisePath", () => {
    it("drops trailing slashes", () => {
      expect(window.UniSpaceUI.normalisePath("/rooms/")).toBe("/rooms");
      expect(window.UniSpaceUI.normalisePath("/rooms//")).toBe("/rooms");
    });

    it("keeps the root path and paths without a trailing slash", () => {
      expect(window.UniSpaceUI.normalisePath("/")).toBe("/");
      expect(window.UniSpaceUI.normalisePath("/timetable")).toBe("/timetable");
    });
  });

  describe("footer", () => {
    it("appends a footer with the note and the two links, escaped", async () => {
      await loadScript("components/footer.js");
      window.UniSpaceUI.buildFooter();
      const footer = document.querySelector("footer.site-footer");
      expect(footer).not.toBeNull();
      expect(footer.querySelector("p").textContent).toBe(
        window.UniSpaceI18n.t("footer.note"),
      );
      const links = [...footer.querySelectorAll("a")];
      expect(links.map((a) => a.getAttribute("href"))).toEqual([
        "/",
        "/calendar",
      ]);
      expect(links.map((a) => a.textContent)).toEqual([
        window.UniSpaceI18n.t("footer.home"),
        window.UniSpaceI18n.t("footer.subscribe"),
      ]);
    });
  });

  // Each component adds itself to window.UniSpaceUI, creating it when it is loaded first.
  describe("components create the shared namespace when they are loaded first", () => {
    it.each([
      "components/footer.js",
      "components/header.js",
      "components/language-toggle.js",
      "components/theme-toggle.js",
      "components/toast.js",
    ])("%s", async (file) => {
      delete window.UniSpaceUI;
      await loadScript(file);
      expect(window.UniSpaceUI).toBeDefined();
    });
  });
});
