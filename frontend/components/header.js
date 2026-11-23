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
    var actions = "";

    if (user) {
      links = NAV.filter(function (item) {
        return !item.adminOnly || user.role === "ADMIN";
      }).map(function (item) {
        var current = UI.normalisePath(item.href) === here ? ' aria-current="page"' : "";
        return '<a href="' + item.href + '"' + current + ">" + esc(t(item.key)) + "</a>";
      }).join("");
      actions +=
        '<span class="pill pill--info user-chip">' + esc(user.name) +
        " · " + esc(window.UniSpaceAuth.roleLabel(user.role)) + "</span>";
    } else {
      actions += '<button class="btn btn-ghost btn-small theme-toggle" type="button"></button>';
    }

    var header = document.createElement("header");
    header.className = "site-header";
    header.innerHTML =
      '<a class="skip-link" href="#main">' + esc(t("header.skip")) + "</a>" +
      '<div class="site-header__inner">' +
      '<a class="brand" href="/"><img class="brand__mark" src="/public/brand-mark.png" alt="" width="28" height="28" />UniSpace</a>' +
      '<div class="header-actions">' + actions + "</div>" +
      (user ? '<nav id="site-nav" class="nav" aria-label="' + esc(t("header.navAria")) + '">' + links + "</nav>" : "") +
    "</div>";

    var actionsEl = header.querySelector(".header-actions");
    actionsEl.appendChild(UI.languageToggle());

    if (user) {
      var avatarHtml = "";
      if (user.picture) {
        avatarHtml = '<img class="user-avatar" src="' + esc(user.picture) + '" alt="" width="32" height="32" referrerpolicy="no-referrer" />';
      } else {
        avatarHtml = '<span class="user-avatar user-avatar--placeholder" aria-hidden="true">' + esc(user.name.charAt(0).toUpperCase()) + "</span>";
      }

      var menu = document.createElement("div");
      menu.className = "profile-menu";
      menu.innerHTML =
        '<button class="profile-menu__trigger" type="button" aria-expanded="false" aria-haspopup="true" aria-label="' + esc(t("header.profileMenu")) + '">' +
        avatarHtml +
        "</button>" +
        '<div class="profile-menu__dropdown" hidden>' +
        '<button class="btn btn-ghost btn-small theme-toggle" type="button"></button>' +
        '<a class="btn btn-ghost btn-small profile-menu__item" href="/settings">' + esc(t("header.settings")) + "</a>" +
        '<button class="btn btn-ghost btn-small logout" type="button">' + esc(t("header.logout")) + "</button>" +
        "</div>";
      actionsEl.appendChild(menu);

      var trigger = menu.querySelector(".profile-menu__trigger");
      var dropdown = menu.querySelector(".profile-menu__dropdown");

      trigger.addEventListener("click", function (event) {
        event.stopPropagation();
        var open = dropdown.hidden;
        dropdown.hidden = !open;
        trigger.setAttribute("aria-expanded", String(open));
      });

      document.addEventListener("click", function (event) {
        if (!menu.contains(event.target)) {
          dropdown.hidden = true;
          trigger.setAttribute("aria-expanded", "false");
        }
      });

      document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && !dropdown.hidden) {
          dropdown.hidden = true;
          trigger.setAttribute("aria-expanded", "false");
          trigger.focus();
        }
      });
    }

    document.body.prepend(header);

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
  }) ();
