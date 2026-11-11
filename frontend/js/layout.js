/*
 * Shared chrome for every page: header, footer, theme toggle, mobile menu, copy
 * buttons, placeholder forms and actions (they show a toast instead of sending
 * anything until the backend endpoints exist). The header depends on the session:
 * logged-out visitors only get the brand, logged-in users get the navigation.
 * Access control itself lives in auth.js.
 */
(function () {
  "use strict";

  var NAV = [
    { href: "/timetable", label: "Timetable" },
    { href: "/rooms/", label: "Rooms" },
    { href: "/rooms/free", label: "Free now" },
    { href: "/bookings/", label: "Bookings" },
    { href: "/announcements", label: "Announcements" },
    { href: "/changes", label: "Changes" },
    { href: "/calendar", label: "Calendar" },
    { href: "/admin/", label: "Admin", adminOnly: true }
  ];

  var THEMES = ["auto", "light", "dark"];
  var THEME_LABEL = { auto: "Theme: auto", light: "Theme: light", dark: "Theme: dark" };

  function normalise(path) {
    return path.length > 1 ? path.replace(/\/+$/, "") : path;
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function buildHeader(user) {
    var here = normalise(window.location.pathname);
    var links = "";
    var actions = '<button class="btn btn-ghost btn-small theme-toggle" type="button"></button>';

    if (user) {
      links = NAV.filter(function (item) {
        return !item.adminOnly || user.role === "admin";
      }).map(function (item) {
        var current = normalise(item.href) === here ? ' aria-current="page"' : "";
        return '<a href="' + item.href + '"' + current + ">" + item.label + "</a>";
      }).join("");
      actions +=
        '<span class="pill pill--info user-chip">' + escapeHtml(user.name) +
        " · " + escapeHtml(user.role) + "</span>" +
        '<button class="btn btn-ghost btn-small logout" type="button">Log out</button>';
    }

    var header = document.createElement("header");
    header.className = "site-header";
    header.innerHTML =
      '<a class="skip-link" href="#main">Skip to content</a>' +
      '<div class="site-header__inner">' +
      '<a class="brand" href="/"><span class="brand__mark" aria-hidden="true"></span>UniSpace</a>' +
      (user
        ? '<button class="btn btn-ghost btn-small nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav">Menu</button>' +
          '<nav id="site-nav" class="nav" aria-label="Main">' + links + "</nav>"
        : "") +
      '<div class="header-actions">' + actions + "</div></div>";
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
        window.UniSpaceAuth.logout();
        window.location.replace("/login");
      });
    }
  }

  function fillUserName(user) {
    document.querySelectorAll("[data-user-name]").forEach(function (el) {
      el.textContent = user ? user.name : "there";
    });
  }

  function buildFooter() {
    var footer = document.createElement("footer");
    footer.className = "site-footer";
    footer.innerHTML =
      "<p>UniSpace · placeholder build · all data on screen is sample data</p>" +
      '<p><a href="/">Home</a> · <a href="/calendar">Subscribe to your timetable</a></p>';
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
      button.textContent = THEME_LABEL[mode];
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

  var PLACEHOLDER_MESSAGE =
    "Placeholder: nothing was saved. The backend endpoint for this comes later.";

  function bindPlaceholders() {
    document.addEventListener("submit", function (event) {
      if (event.target.matches("form[data-placeholder]")) {
        event.preventDefault();
        toast(PLACEHOLDER_MESSAGE);
      }
    });
    document.addEventListener("click", function (event) {
      var action = event.target.closest("[data-placeholder-action]");
      if (action) {
        event.preventDefault();
        toast(action.dataset.placeholderAction || PLACEHOLDER_MESSAGE);
        return;
      }
      var copy = event.target.closest("[data-copy]");
      if (copy) {
        var input = document.querySelector(copy.dataset.copy);
        if (input && navigator.clipboard) {
          navigator.clipboard.writeText(input.value).then(function () {
            toast("Subscription link copied");
          });
        } else {
          toast("Copy is not available in this browser");
        }
      }
    });
  }

  var user = window.UniSpaceAuth ? window.UniSpaceAuth.user() : null;
  buildHeader(user);
  fillUserName(user);
  buildFooter();
  bindTheme();
  bindPlaceholders();
})();
