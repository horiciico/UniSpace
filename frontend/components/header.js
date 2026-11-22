/*
 * Component: the site header (brand, navigation, user chip, log out, theme and language
 * toggles) and the greeting that fills [data-user-name]. The navigation depends on the
 * session: logged-out visitors only get the brand and the toggles.
 */
(function () {
  "use strict";

  var UI = (window.UniSpaceUI = window.UniSpaceUI || {});

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

  UI.buildHeader = function (user) {
    var t = window.UniSpaceI18n.t;
    var esc = UI.escapeHtml;
    var here = UI.normalisePath(window.location.pathname);
    var links = "";
    var actions = '<button class="btn btn-ghost btn-small theme-toggle" type="button"></button>';

    if (user) {
      links = NAV.filter(function (item) {
        return !item.adminOnly || user.role === "ADMIN";
      }).map(function (item) {
        var current = UI.normalisePath(item.href) === here ? ' aria-current="page"' : "";
        return '<a href="' + item.href + '"' + current + ">" + esc(t(item.key)) + "</a>";
      }).join("");
      actions +=
        '<span class="pill pill--info user-chip">' + esc(user.name) +
        " · " + esc(window.UniSpaceAuth.roleLabel(user.role)) + "</span>" +
        '<button class="btn btn-ghost btn-small logout" type="button">' + esc(t("header.logout")) + "</button>";
    }

    var header = document.createElement("header");
    header.className = "site-header";
    header.innerHTML =
      '<a class="skip-link" href="#main">' + esc(t("header.skip")) + "</a>" +
      '<div class="site-header__inner">' +
      '<a class="brand" href="/"><img class="brand__mark" src="/public/brand-mark.png" alt="" width="28" height="28" />UniSpace</a>' +
      (user
        ? '<button class="btn btn-ghost btn-small nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav">' +
          esc(t("header.menu")) + "</button>" +
          '<nav id="site-nav" class="nav" aria-label="' + esc(t("header.navAria")) + '">' + links + "</nav>"
        : "") +
      '<div class="header-actions">' + actions + "</div></div>";
    // The language toggle is last, so it sits in the top right corner.
    header.querySelector(".header-actions").appendChild(UI.languageToggle());
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
  };

  UI.fillUserName = function (user) {
    document.querySelectorAll("[data-user-name]").forEach(function (el) {
      el.textContent = user ? user.name : window.UniSpaceI18n.t("common.guest");
    });
  };
})();
