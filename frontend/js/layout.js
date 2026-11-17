/*
 * Shared chrome for every page: header, footer, theme toggle, language toggle, mobile
 * menu, copy buttons, placeholder forms and actions (they show a toast instead of
 * sending anything until the backend endpoints exist). The header depends on the
 * session: logged-out visitors only get the brand and the toggles, logged-in users get
 * the navigation. Who is signed in comes from auth.js; the access check is nginx's.
 * Every label is looked up with UniSpaceI18n.t(); a language change rebuilds the chrome.
 */
(function () {
  "use strict";

  var t = window.UniSpaceI18n.t;

  var NAV = [
    { href: "/timetable", key: "nav.timetable" },
    { href: "/rooms/", key: "nav.rooms" },
    { href: "/rooms/free", key: "nav.freeNow" },
    { href: "/bookings/", key: "nav.bookings" },
    { href: "/announcements", key: "nav.announcements" },
    { href: "/changes", key: "nav.changes" },
    { href: "/calendar", key: "nav.calendar" },
    { href: "/admin/", key: "nav.admin", adminOnly: true }
  ];

  var THEMES = ["auto", "light", "dark"];

  var currentUser = null;
  var built = false;

  function normalise(path) {
    return path.length > 1 ? path.replace(/\/+$/, "") : path;
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function buildLanguageToggle() {
    var group = document.createElement("div");
    group.className = "lang-toggle";
    group.setAttribute("role", "group");
    group.setAttribute("aria-label", t("header.language"));
    var current = window.UniSpaceI18n.current();
    window.UniSpaceI18n.languages.forEach(function (code) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "lang-toggle__btn";
      button.dataset.lang = code;
      button.textContent = code.toUpperCase();
      button.setAttribute("aria-pressed", String(code === current));
      group.appendChild(button);
    });
    group.addEventListener("click", function (event) {
      var button = event.target.closest("[data-lang]");
      if (button) window.UniSpaceI18n.setLanguage(button.dataset.lang);
    });
    return group;
  }

  function buildHeader(user) {
    var here = normalise(window.location.pathname);
    var links = "";
    var actions = '<button class="btn btn-ghost btn-small theme-toggle" type="button"></button>';

    if (user) {
      links = NAV.filter(function (item) {
        return !item.adminOnly || user.role === "ADMIN";
      }).map(function (item) {
        var current = normalise(item.href) === here ? ' aria-current="page"' : "";
        return '<a href="' + item.href + '"' + current + ">" + escapeHtml(t(item.key)) + "</a>";
      }).join("");
      actions +=
        '<span class="pill pill--info user-chip">' + escapeHtml(user.name) +
        " · " + escapeHtml(window.UniSpaceAuth.roleLabel(user.role)) + "</span>" +
        '<button class="btn btn-ghost btn-small logout" type="button">' + escapeHtml(t("header.logout")) + "</button>";
    }

    var header = document.createElement("header");
    header.className = "site-header";
    header.innerHTML =
      '<a class="skip-link" href="#main">' + escapeHtml(t("header.skip")) + "</a>" +
      '<div class="site-header__inner">' +
      '<a class="brand" href="/"><span class="brand__mark" aria-hidden="true"></span>UniSpace</a>' +
      (user
        ? '<button class="btn btn-ghost btn-small nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav">' +
          escapeHtml(t("header.menu")) + "</button>" +
          '<nav id="site-nav" class="nav" aria-label="' + escapeHtml(t("header.navAria")) + '">' + links + "</nav>"
        : "") +
      '<div class="header-actions">' + actions + "</div></div>";
    // The language toggle is last, so it sits in the top right corner.
    header.querySelector(".header-actions").appendChild(buildLanguageToggle());
    document.body.prepend(header);

    var nav = header.querySelector(".nav");
    var toggle = header.querySelector(".nav-toggle");
    if (toggle && nav) {
      toggle.addEventListener("click", function (event) {
        var open = nav.classList.toggle("is-open");
        event.currentTarget.setAttribute("aria-expanded", String(open));
      });
    }

    var logout = header.querySelector(".logout");
    if (logout) {
      logout.addEventListener("click", function () {
        logout.disabled = true;
        window.UniSpaceAuth.logout();
      });
    }
  }

  function fillUserName(user) {
    document.querySelectorAll("[data-user-name]").forEach(function (el) {
      el.textContent = user ? user.name : t("common.guest");
    });
  }

  function buildFooter() {
    var footer = document.createElement("footer");
    footer.className = "site-footer";
    footer.innerHTML =
      "<p>" + escapeHtml(t("footer.note")) + "</p>" +
      '<p><a href="/">' + escapeHtml(t("footer.home")) + '</a> · <a href="/calendar">' +
      escapeHtml(t("footer.subscribe")) + "</a></p>";
    document.body.appendChild(footer);
  }

  function currentTheme() {
    return localStorage.getItem("unispace-theme") || "auto";
  }

  function applyTheme(mode) {
    var root = document.documentElement;
    if (mode === "auto") {
      root.removeAttribute("data-theme");
    } else {
      root.setAttribute("data-theme", mode);
    }
    var button = document.querySelector(".theme-toggle");
    if (button) {
      button.textContent = t("theme." + mode);
    }
  }

  function bindTheme() {
    applyTheme(currentTheme());
    var button = document.querySelector(".theme-toggle");
    if (!button) return;
    button.addEventListener("click", function () {
      var next = THEMES[(THEMES.indexOf(currentTheme()) + 1) % THEMES.length];
      localStorage.setItem("unispace-theme", next);
      applyTheme(next);
    });
  }

  function toast(message) {
    var el = document.getElementById("toast");
    if (!el) {
      el = document.createElement("div");
      el.id = "toast";
      el.className = "toast";
      el.setAttribute("role", "status");
      document.body.appendChild(el);
    }
    el.textContent = message;
    el.classList.add("is-visible");
    clearTimeout(el._hide);
    el._hide = setTimeout(function () {
      el.classList.remove("is-visible");
    }, 3200);
  }

  function bindPlaceholders() {
    document.addEventListener("submit", function (event) {
      if (event.target.matches("form[data-placeholder]")) {
        event.preventDefault();
        toast(t("placeholder.nothingSaved"));
      }
    });
    document.addEventListener("click", function (event) {
      var action = event.target.closest("[data-placeholder-action]");
      if (action) {
        event.preventDefault();
        toast(t(action.dataset.placeholderAction || "placeholder.generic"));
        return;
      }
      var copy = event.target.closest("[data-copy]");
      if (copy) {
        var input = document.querySelector(copy.dataset.copy);
        if (input && navigator.clipboard) {
          navigator.clipboard.writeText(input.value).then(function () {
            toast(t("toast.copied"));
          });
        } else {
          toast(t("toast.copyUnavailable"));
        }
      }
    });
  }

  // Rebuilds the header and footer so their labels follow the new language.
  function rebuildChrome() {
    if (!built) return;
    document.querySelectorAll(".site-header, .site-footer").forEach(function (el) {
      el.remove();
    });
    buildHeader(currentUser);
    fillUserName(currentUser);
    buildFooter();
    bindTheme();
  }

  document.addEventListener("unispace:langchange", rebuildChrome);

  // Apply the saved theme at once; the header (and its toggle) waits for the session
  // so the navigation does not flash in and out.
  applyTheme(currentTheme());
  window.UniSpaceAuth.ready.then(function (user) {
    currentUser = user;
    buildHeader(user);
    fillUserName(user);
    buildFooter();
    bindTheme();
    bindPlaceholders();
    built = true;
  });
})();
