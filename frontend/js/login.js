/*
 * Login page. The button is a plain link to /auth/login, so it works without this
 * script. This only shows why a sign-in was turned back (nginx sends the browser here
 * with ?error=denied or ?error=failed) and skips the page for people already signed in.
 */
(function () {
  "use strict";

  var MESSAGES = {
    denied: {
      title: "You could not be signed in.",
      text: "Access denied. Please use your institutional @ulbsibiu.ro account or request an invitation."
    },
    failed: {
      title: "Google sign-in did not finish.",
      text: "Nothing was saved. Try again."
    }
  };

  var box = document.getElementById("login-error");
  var reason = new URLSearchParams(window.location.search).get("error");
  var message = Object.prototype.hasOwnProperty.call(MESSAGES, reason) ? MESSAGES[reason] : null;

  if (box && message) {
    document.getElementById("login-error-title").textContent = message.title;
    document.getElementById("login-error-text").textContent = message.text;
    box.hidden = false;
  }

  window.UniSpaceAuth.ready.then(function (user) {
    if (user) window.location.replace("/");
  });
})();
