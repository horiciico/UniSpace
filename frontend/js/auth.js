/*
 * Dummy auth gate. Loaded synchronously in <head>, before the page renders, so a
 * protected page never flashes. Every page except the public ones needs a session.
 *
 * This is NOT security. The files are still public on the server, and the session is
 * a localStorage value anyone can edit. It only stops casual browsing until the backend
 * issues real sessions; then the check moves to the API and nginx.
 */
(function () {
  "use strict";

  var KEY = "unispace-session";
  var MAX_AGE_MS = 8 * 60 * 60 * 1000; // a dummy session lasts one working day
  var PUBLIC = ["/login", "/404"];

  function normalise(path) {
    var p = path.replace(/\/index\.html$/, "/").replace(/\.html$/, "");
    return p.length > 1 ? p.replace(/\/+$/, "") : p;
  }

  function readSession() {
    try {
      var s = JSON.parse(localStorage.getItem(KEY));
      if (!s || !s.user || Date.now() - s.at > MAX_AGE_MS) return null;
      return s;
    } catch (error) {
      return null;
    }
  }

  // Only same-site paths may be used after login, so ?next= cannot send people off-site.
  function safeNext(value) {
    return typeof value === "string" && value.charAt(0) === "/" && value.charAt(1) !== "/"
      ? value
      : "/";
  }

  var session = readSession();
  var path = normalise(window.location.pathname);
  var isPublic = PUBLIC.indexOf(path) !== -1;

  function redirect(target) {
    document.documentElement.style.display = "none";
    window.location.replace(target);
  }

  if (!session && !isPublic) {
    redirect("/login?next=" + encodeURIComponent(window.location.pathname + window.location.search));
  } else if (session && path === "/login") {
    var next = new URLSearchParams(window.location.search).get("next");
    redirect(safeNext(next));
  } else if (session && path.indexOf("/admin") === 0 && session.user.role !== "admin") {
    redirect("/");
  }

  window.UniSpaceAuth = {
    user: function () {
      var s = readSession();
      return s ? s.user : null;
    },
    login: function (name, role) {
      localStorage.setItem(KEY, JSON.stringify({
        at: Date.now(),
        user: { name: name, role: role }
      }));
    },
    logout: function () {
      localStorage.removeItem(KEY);
    }
  };
})();
