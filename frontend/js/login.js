/*
 * Login page. The button is a plain link to /auth/login, so it works without this
 * script. This only shows why a sign-in was turned back (nginx sends the browser here
 * with ?error=denied or ?error=failed) and skips the page for people already signed in.
 */
(function () {
  "use strict";

  var t = window.UniSpaceI18n.t;
  var box = document.getElementById("login-error");
  var reason = new URLSearchParams(window.location.search).get("error");
  var KNOWN = ["denied", "failed"];

  // Only the two known reasons are shown; anything else in the URL is ignored.
  function showError() {
    if (!box) return;
    if (KNOWN.indexOf(reason) === -1) {
      box.hidden = true;
      return;
    }
    document.getElementById("login-error-title").textContent = t("login." + reason + "Title");
    document.getElementById("login-error-text").textContent = t("login." + reason + "Text");
    box.hidden = false;
  }

  showError();
  document.addEventListener("unispace:langchange", showError);

  window.UniSpaceAuth.ready.then(function (user) {
    if (user) window.location.replace("/");
  });
})();
