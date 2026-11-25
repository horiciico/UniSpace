import { beforeEach, describe, expect, it, vi } from "vitest";
import { flush, loadI18n, loadScript } from "../helpers.js";

const t = (key) => window.UniSpaceI18n.t(key);
const toastEl = () => document.getElementById("toast");

describe("toast.js: messages and the placeholder actions", () => {
  beforeEach(async () => {
    vi.resetModules();
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    await loadI18n("en");
    await loadScript("components/ui.js");
    await loadScript("components/toast.js");
  });

  describe("UniSpaceUI.toast", () => {
    it("creates the toast once, as a status region, and shows the message", () => {
      window.UniSpaceUI.toast("Saved");
      const el = toastEl();
      expect(el.getAttribute("role")).toBe("status");
      expect(el.className).toBe("toast is-visible");
      expect(el.textContent).toBe("Saved");
      expect(document.querySelectorAll("#toast")).toHaveLength(1);
    });

    it("reuses the toast for the next message", () => {
      window.UniSpaceUI.toast("One");
      window.UniSpaceUI.toast("Two");
      expect(document.querySelectorAll("#toast")).toHaveLength(1);
      expect(toastEl().textContent).toBe("Two");
    });

    it("hides itself after 3.2 seconds", () => {
      window.UniSpaceUI.toast("Bye");
      vi.advanceTimersByTime(3199);
      expect(toastEl().classList.contains("is-visible")).toBe(true);
      vi.advanceTimersByTime(1);
      expect(toastEl().classList.contains("is-visible")).toBe(false);
    });

    it("restarts the timer when a new message comes before the old one hides", () => {
      window.UniSpaceUI.toast("First");
      vi.advanceTimersByTime(3000);
      window.UniSpaceUI.toast("Second");
      vi.advanceTimersByTime(3000);
      expect(toastEl().classList.contains("is-visible")).toBe(true);
      vi.advanceTimersByTime(200);
      expect(toastEl().classList.contains("is-visible")).toBe(false);
    });
  });

  describe("bindActions", () => {
    beforeEach(() => {
      window.UniSpaceUI.bindActions();
    });

    it("stops a placeholder form from sending and says nothing was saved", () => {
      document.body.innerHTML =
        "<form data-placeholder><button>Save</button></form>";
      const submit = new Event("submit", { bubbles: true, cancelable: true });
      document.querySelector("form").dispatchEvent(submit);
      expect(submit.defaultPrevented).toBe(true);
      expect(toastEl().textContent).toBe(t("placeholder.nothingSaved"));
    });

    it("leaves other forms alone", () => {
      document.body.innerHTML = '<form id="real"></form>';
      const submit = new Event("submit", { bubbles: true, cancelable: true });
      document.getElementById("real").dispatchEvent(submit);
      expect(submit.defaultPrevented).toBe(false);
      expect(toastEl()).toBeNull();
    });

    it("ignores submit events that do not come from a form", () => {
      document.body.innerHTML = '<div id="odd"></div>';
      const submit = new Event("submit", { bubbles: true, cancelable: true });
      document.getElementById("odd").dispatchEvent(submit);
      expect(submit.defaultPrevented).toBe(false);
    });

    it("runs a placeholder action with its own message, without following the link", () => {
      document.body.innerHTML =
        '<a id="go" href="#x" data-placeholder-action="placeholder.icsDownload"><span id="inner">Go</span></a>';
      const click = new MouseEvent("click", {
        bubbles: true,
        cancelable: true,
      });
      document.getElementById("inner").dispatchEvent(click);
      expect(click.defaultPrevented).toBe(true);
      expect(toastEl().textContent).toBe(t("placeholder.icsDownload"));
    });

    it("uses the generic message for a placeholder action with no message key", () => {
      document.body.innerHTML =
        '<button id="b" data-placeholder-action=""></button>';
      document.getElementById("b").click();
      expect(toastEl().textContent).toBe(t("placeholder.generic"));
    });

    it("copies the value of the named input and confirms it", async () => {
      const writeText = vi.fn(() => Promise.resolve());
      Object.defineProperty(navigator, "clipboard", {
        configurable: true,
        value: { writeText },
      });
      document.body.innerHTML =
        '<input id="src" value="abc"><button id="c" data-copy="#src"></button>';
      document.getElementById("c").click();
      expect(writeText).toHaveBeenCalledWith("abc");
      await flush();
      expect(toastEl().textContent).toBe(t("toast.copied"));
      delete navigator.clipboard;
    });

    it("says copying is unavailable when the input is not on the page", () => {
      Object.defineProperty(navigator, "clipboard", {
        configurable: true,
        value: { writeText: vi.fn() },
      });
      document.body.innerHTML = '<button id="c" data-copy="#missing"></button>';
      document.getElementById("c").click();
      expect(toastEl().textContent).toBe(t("toast.copyUnavailable"));
      delete navigator.clipboard;
    });

    it("says copying is unavailable when the browser has no clipboard", () => {
      document.body.innerHTML =
        '<input id="src" value="abc"><button id="c" data-copy="#src"></button>';
      document.getElementById("c").click();
      expect(toastEl().textContent).toBe(t("toast.copyUnavailable"));
    });

    it("ignores clicks on anything else", () => {
      document.body.innerHTML = '<p id="plain">Text</p>';
      const click = new MouseEvent("click", {
        bubbles: true,
        cancelable: true,
      });
      document.getElementById("plain").dispatchEvent(click);
      expect(click.defaultPrevented).toBe(false);
      expect(toastEl()).toBeNull();
    });
  });
});
