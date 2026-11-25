import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flush, mountPage } from "../helpers.js";

// Loads only the runtime (not the dictionaries), with the stored choice and the browser
// languages set up as the test needs them.
async function loadRuntime({ stored = null, languages, language } = {}) {
  if (stored !== null) localStorage.setItem("unispace-lang", stored);
  if (languages !== undefined) {
    Object.defineProperty(navigator, "languages", {
      configurable: true,
      get: () => languages,
    });
  }
  // null means: the browser gives no language at all (the property is missing).
  if (language !== undefined) {
    Object.defineProperty(navigator, "language", {
      configurable: true,
      get: () => language ?? undefined,
    });
  }
  await import("../../i18n/i18n.js");
  return window.UniSpaceI18n;
}

describe("i18n.js: the translation runtime", () => {
  beforeEach(() => {
    vi.resetModules();
    document.body.innerHTML = "";
    document.documentElement.lang = "";
  });

  afterEach(() => {
    delete navigator.languages;
    delete navigator.language;
    vi.restoreAllMocks();
    delete document.readyState;
  });

  describe("choosing the language", () => {
    it("uses the choice kept in localStorage", async () => {
      const i18n = await loadRuntime({ stored: "en", languages: ["ro-RO"] });
      expect(i18n.current()).toBe("en");
      expect(document.documentElement.lang).toBe("en");
    });

    it("ignores a stored value it does not support, and follows the browser", async () => {
      const i18n = await loadRuntime({
        stored: "fr",
        languages: ["fr-FR", "en-GB"],
      });
      expect(i18n.current()).toBe("en");
    });

    it("follows the browser when storage cannot be read", async () => {
      vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
        throw new Error("denied");
      });
      const i18n = await loadRuntime({ languages: ["en-US"] });
      expect(i18n.current()).toBe("en");
    });

    it("takes the first supported language in the browser's list", async () => {
      const i18n = await loadRuntime({
        languages: ["de-DE", "en-GB", "ro-RO"],
      });
      expect(i18n.current()).toBe("en");
    });

    it("picks Romanian when the browser lists it first", async () => {
      const i18n = await loadRuntime({ languages: ["ro-RO", "en-US"] });
      expect(i18n.current()).toBe("ro");
    });

    it("uses the single browser language when the list is empty", async () => {
      const i18n = await loadRuntime({ languages: [], language: "en-US" });
      expect(i18n.current()).toBe("en");
    });

    it("uses the single browser language when the list is missing", async () => {
      const i18n = await loadRuntime({
        languages: undefined,
        language: "en-GB",
      });
      expect(i18n.current()).toBe("en");
    });

    it("falls back to Romanian when the browser gives no usable language", async () => {
      const i18n = await loadRuntime({ languages: [], language: null });
      expect(i18n.current()).toBe("ro");
    });

    it("falls back to Romanian when no browser language is supported", async () => {
      const i18n = await loadRuntime({ languages: ["de-DE", "fr-FR"] });
      expect(i18n.current()).toBe("ro");
    });

    it("sets the document language", async () => {
      await loadRuntime({ languages: ["en-US"] });
      expect(document.documentElement.lang).toBe("en");
    });
  });

  describe("t(): the text of a key", () => {
    async function withDictionaries() {
      const i18n = await loadRuntime({ stored: "ro" });
      i18n.register("ro", {
        hello: "Salut {name}",
        "only.ro": "Doar în română",
        two: "{a} și {b}",
      });
      i18n.register("en", { hello: "Hello {name}", "only.en": "English only" });
      return i18n;
    }

    it("returns the text in the current language", async () => {
      const i18n = await withDictionaries();
      expect(i18n.t("hello", { name: "Ana" })).toBe("Salut Ana");
    });

    it("replaces every placeholder it has a value for, and keeps the others", async () => {
      const i18n = await withDictionaries();
      expect(i18n.t("two", { a: "1", b: "2" })).toBe("1 și 2");
      expect(i18n.t("hello")).toBe("Salut {name}");
      expect(i18n.t("hello", { name: undefined })).toBe("Salut {name}");
    });

    it("falls back to English when the current language has no text for the key", async () => {
      const i18n = await withDictionaries();
      expect(i18n.t("only.en")).toBe("English only");
    });

    it("falls back to English when the current language has no dictionary at all", async () => {
      const i18n = await loadRuntime({ stored: "ro" });
      i18n.register("en", { greeting: "Hi" });
      expect(i18n.t("greeting")).toBe("Hi");
    });

    it("returns the key itself, with a warning, when no language has the key", async () => {
      const i18n = await withDictionaries();
      const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
      expect(i18n.t("missing.key")).toBe("missing.key");
      expect(warn).toHaveBeenCalledWith('i18n: no text for key "missing.key"');
    });

    it("does not treat inherited object properties as keys", async () => {
      const i18n = await withDictionaries();
      vi.spyOn(console, "warn").mockImplementation(() => {});
      expect(i18n.t("toString")).toBe("toString");
    });
  });

  describe("applying the text to a page", () => {
    it("sets the text of data-i18n elements, with variables", async () => {
      const i18n = await loadRuntime({ stored: "en" });
      i18n.register("en", { "a.title": "Title", "a.count": "{n} rooms" });
      i18n.register("ro", {});
      document.body.innerHTML =
        '<h1 data-i18n="a.title">x</h1><p data-i18n="a.count" data-i18n-vars="n:5;bad;:x">x</p>';
      i18n.apply(document.body);
      expect(document.querySelector("h1").textContent).toBe("Title");
      expect(document.querySelector("p").textContent).toBe("5 rooms");
    });

    it("sets attributes from data-i18n-attr, and skips a pair without a colon", async () => {
      const i18n = await loadRuntime({ stored: "en" });
      i18n.register("en", { "a.search": "Search", "a.label": "Label" });
      i18n.register("ro", {});
      document.body.innerHTML =
        '<input data-i18n-attr="placeholder:a.search;aria-label:a.label;broken;:x" />';
      i18n.apply(document.body);
      const input = document.querySelector("input");
      expect(input.getAttribute("placeholder")).toBe("Search");
      expect(input.getAttribute("aria-label")).toBe("Label");
      expect(input.hasAttribute("broken")).toBe(false);
    });

    it("applies the text when the page is still loading, at DOMContentLoaded", async () => {
      Object.defineProperty(document, "readyState", {
        configurable: true,
        get: () => "loading",
      });
      document.body.innerHTML = '<h1 data-i18n="a.title">x</h1>';
      const i18n = await loadRuntime({ stored: "en" });
      i18n.register("en", { "a.title": "Ready" });
      i18n.register("ro", {});
      expect(document.querySelector("h1").textContent).toBe("x");
      document.dispatchEvent(new Event("DOMContentLoaded"));
      expect(document.querySelector("h1").textContent).toBe("Ready");
    });
  });

  describe("changing the language", () => {
    async function ready() {
      const i18n = await loadRuntime({ stored: "ro" });
      i18n.register("ro", { "a.title": "Titlu" });
      i18n.register("en", { "a.title": "Title" });
      document.body.innerHTML = '<h1 data-i18n="a.title">Titlu</h1>';
      i18n.apply(document.body);
      return i18n;
    }

    it("ignores a language that is not supported", async () => {
      const i18n = await ready();
      const listener = vi.fn();
      document.addEventListener("unispace:langchange", listener);
      i18n.setLanguage("fr");
      expect(i18n.current()).toBe("ro");
      expect(listener).not.toHaveBeenCalled();
    });

    it("ignores the language that is already chosen", async () => {
      const i18n = await ready();
      const listener = vi.fn();
      document.addEventListener("unispace:langchange", listener);
      i18n.setLanguage("ro");
      expect(listener).not.toHaveBeenCalled();
    });

    it("switches, stores the choice, re-applies the text and announces the change", async () => {
      const i18n = await ready();
      const listener = vi.fn();
      document.addEventListener("unispace:langchange", listener);
      i18n.setLanguage("en");
      expect(i18n.current()).toBe("en");
      expect(localStorage.getItem("unispace-lang")).toBe("en");
      expect(document.documentElement.lang).toBe("en");
      expect(document.querySelector("h1").textContent).toBe("Title");
      expect(listener.mock.calls[0][0].detail).toEqual({ lang: "en" });
    });

    it("still switches when storage refuses the choice", async () => {
      const i18n = await ready();
      vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
        throw new Error("private mode");
      });
      i18n.setLanguage("en");
      await flush();
      expect(i18n.current()).toBe("en");
      expect(document.querySelector("h1").textContent).toBe("Title");
    });

    it("exposes the supported languages and the registration", async () => {
      const i18n = await loadRuntime({ stored: "ro" });
      expect(i18n.languages).toEqual(["ro", "en"]);
      i18n.languages.push("xx");
      expect(window.UniSpaceI18n.languages).toEqual(["ro", "en", "xx"]);
    });
  });
});
