/*
 * Entry point for the shared chrome. Loaded last among the components (see
 * components/head.html). It waits for the session, builds the header and footer, and
 * rebuilds them when the language changes. Access control is nginx's; this script
 * only decides how the chrome looks.
 */
(function () {
  "use strict";

  var UI = window.UniSpaceUI;
  var currentUser = null;
  var built = false;

  function rebuildChrome() {
    if (!built) return;
    document.querySelectorAll(".site-header, .site-footer").forEach(function (el) {
      el.remove();
    });
    UI.buildHeader(currentUser);
    UI.fillUserName(currentUser);
    UI.buildFooter();
    UI.bindTheme();
  }

  document.addEventListener("unispace:langchange", rebuildChrome);

  // Apply the saved theme at once; the header (and its toggle) waits for the session
  // so the navigation does not flash in and out.
  UI.applyTheme(UI.currentTheme());
  window.UniSpaceAuth.ready.then(function (user) {
    currentUser = user;
    UI.buildHeader(user);
    UI.fillUserName(user);
    UI.buildFooter();
    UI.bindTheme();
    UI.bindActions();
    built = true;
  });
})();
