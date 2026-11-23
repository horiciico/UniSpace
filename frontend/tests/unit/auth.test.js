import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flush, loadI18n, loadScript, response, stubFetch } from "../helpers.js";

const STUDENT = { id: "u1", name: "Ana", email: "ana@ulbsibiu.ro", role: "STUDENT" };
const ADMIN = { id: "u2", name: "Ion", email: "ion@ulbsibiu.ro", role: "ADMIN" };

const realLocation = window.location;

// Replaces the page location, so a redirect can be seen without leaving the test page.
function setLocation(pathname) {
  const replace = vi.fn();
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { pathname, search: "", replace }
  });
  return replace;
}

// Loads the session script for a page at `pathname`, with the answer to /auth/me.
async function loadSession({ pathname = "/timetable", me = () => response(STUDENT), logout } = {}) {
  vi.resetModules();
  const replace = setLocation(pathname);
  await loadI18n("en");
  const fetch = stubFetch({
    "/auth/me": me,
    "/auth/logout": logout || (() => response(null, 204))
  });
  await loadScript("js/auth.js");
  return { fetch, replace, auth: window.UniSpaceAuth };
}

describe("auth.js: the session in the browser", () => {
  beforeEach(() => {
    document.documentElement.style.display = "";
  });

  afterEach(() => {
    Object.defineProperty(window, "location", { configurable: true, value: realLocation });
    vi.restoreAllMocks();
  });

  describe("who is signed in", () => {
    it("reads the user from /auth/me, and keeps it", async () => {
      const { fetch, replace, auth } = await loadSession();
      expect(fetch).toHaveBeenCalledWith("/auth/me", { credentials: "same-origin" });
      await expect(auth.ready).resolves.toEqual(STUDENT);
      expect(auth.user()).toEqual(STUDENT);
      expect(replace).not.toHaveBeenCalled();
      expect(document.documentElement.style.display).toBe("");
    });

    it("knows the user is not an administrator, and that the role has a label", async () => {
      const { auth } = await loadSession();
      await auth.ready;
      expect(auth.isAdmin()).toBe(false);
      expect(auth.roleLabel("STUDENT")).toBe("Student");
    });

    it("knows an administrator", async () => {
      const { auth } = await loadSession({ me: () => response(ADMIN) });
      await auth.ready;
      expect(auth.isAdmin()).toBe(true);
    });
  });

  describe("signed out", () => {
    it("hides the page and sends the visitor to /login", async () => {
      const { replace, auth } = await loadSession({ pathname: "/timetable", me: () => response({}, 401) });
      await expect(auth.ready).resolves.toBeNull();
      expect(document.documentElement.style.display).toBe("none");
      expect(replace).toHaveBeenCalledWith("/login");
    });

    it("stays on the login page when signed out there", async () => {
      const { replace, auth } = await loadSession({ pathname: "/login", me: () => response({}, 401) });
      await expect(auth.ready).resolves.toBeNull();
      expect(replace).not.toHaveBeenCalled();
      expect(document.documentElement.style.display).toBe("");
    });

    it("recognises the login page with a trailing slash or the .html name", async () => {
      const slash = await loadSession({ pathname: "/login/", me: () => response({}, 401) });
      await slash.auth.ready;
      expect(slash.replace).not.toHaveBeenCalled();
      const html = await loadSession({ pathname: "/login.html", me: () => response({}, 401) });
      await html.auth.ready;
      expect(html.replace).not.toHaveBeenCalled();
    });

    it("has no user, and admin is false, when signed out", async () => {
      const { auth } = await loadSession({ pathname: "/login", me: () => response({}, 401) });
      await auth.ready;
      expect(auth.user()).toBeNull();
      expect(auth.isAdmin()).toBe(false);
    });
  });

  describe("when the session cannot be read", () => {
    it("logs the problem and treats the visitor as having no user, without redirecting", async () => {
      const error = vi.spyOn(console, "error").mockImplementation(() => {});
      const { replace, auth } = await loadSession({ pathname: "/timetable", me: () => response({}, 500) });
      await expect(auth.ready).resolves.toBeNull();
      expect(error).toHaveBeenCalledWith("Could not read the session:", expect.any(Error));
      expect(replace).not.toHaveBeenCalled();
    });

    it("logs a network failure the same way", async () => {
      const error = vi.spyOn(console, "error").mockImplementation(() => {});
      const { auth } = await loadSession({
        pathname: "/timetable",
        me: () => Promise.reject(new Error("offline"))
      });
      await expect(auth.ready).resolves.toBeNull();
      expect(error).toHaveBeenCalled();
    });
  });

  describe("logging out", () => {
    it("posts to /auth/logout, forgets the user and goes to the login page", async () => {
      const { fetch, replace, auth } = await loadSession();
      await auth.ready;
      await auth.logout();
      expect(fetch).toHaveBeenCalledWith("/auth/logout", { method: "POST", credentials: "same-origin" });
      expect(auth.user()).toBeNull();
      expect(replace).toHaveBeenCalledWith("/login");
    });

    it("still goes to the login page when the request fails, and says why", async () => {
      const error = vi.spyOn(console, "error").mockImplementation(() => {});
      const { replace, auth } = await loadSession({
        logout: () => Promise.reject(new Error("offline"))
      });
      await auth.ready;
      await auth.logout();
      expect(error).toHaveBeenCalledWith("Log out request failed:", expect.any(Error));
      expect(replace).toHaveBeenCalledWith("/login");
    });

    it("waits for the request before it leaves the page", async () => {
      const { replace, auth } = await loadSession();
      await auth.ready;
      const done = auth.logout();
      expect(replace).not.toHaveBeenCalled();
      await done;
      await flush();
      expect(replace).toHaveBeenCalledTimes(1);
    });
  });
});
