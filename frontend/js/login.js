/*
 * Dummy login: any non-empty email and password sign the user in. The role comes from
 * the picked card. Replace the body of submit with a real API call later.
 */
(function () {
  "use strict";

  var form = document.getElementById("login-form");
  if (!form) return;

  var roleButtons = document.querySelectorAll("[data-role]");
  var error = document.getElementById("login-error");
  var role = "student";

  roleButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      role = button.dataset.role;
      roleButtons.forEach(function (other) {
        other.setAttribute("aria-pressed", String(other === button));
      });
    });
  });

  function nameFromEmail(email) {
    var local = email.split("@")[0].replace(/[._-]+/g, " ").trim();
    return local
      .split(" ")
      .filter(Boolean)
      .map(function (word) {
        return word.charAt(0).toUpperCase() + word.slice(1);
      })
      .join(" ") || "Guest";
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var email = form.elements.email.value.trim();
    var password = form.elements.password.value;

    if (!email || !password) {
      error.hidden = false;
      return;
    }

    window.UniSpaceAuth.login(nameFromEmail(email), role);

    var next = new URLSearchParams(window.location.search).get("next");
    var safe = next && next.charAt(0) === "/" && next.charAt(1) !== "/" ? next : "/";
    window.location.replace(safe);
  });
})();
