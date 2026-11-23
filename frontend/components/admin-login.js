/*
 * Component: the discreet administrator sign-in on the login page. A link opens a modal with a
 * username and a password, and the form posts them to /auth/admin-login (D-021). A 401 shows an
 * inline error and keeps the modal open; success loads the home page, which then shows the
 * signed-in admin. The password is never stored, logged or shown.
 */
(function () {
  "use strict";

  var t = window.UniSpaceI18n.t;
  var state = { opener: null, errorKey: null, busy: false };

  function $(id) {
    return document.getElementById(id);
  }

  function dialog() {
    return $("admin-dialog");
  }

  function focusable() {
    return Array.prototype.slice
      .call(dialog().querySelectorAll("input, button"))
      .filter(function (el) { return !el.disabled; });
  }

  function renderError() {
    var box = $("admin-error");
    box.hidden = !state.errorKey;
    box.textContent = state.errorKey ? t(state.errorKey) : "";
  }

  function setInvalid(invalid) {
    ["admin-username", "admin-password"].forEach(function (id) {
      $(id).setAttribute("aria-invalid", invalid ? "true" : "false");
    });
  }

  function open() {
    state.opener = $("admin-open");
    dialog().hidden = false;
    $("admin-username").focus();
  }

  function close() {
    dialog().hidden = true;
    $("admin-form").reset();
    state.errorKey = null;
    setInvalid(false);
    renderError();
    if (state.opener) state.opener.focus();
  }

  function setBusy(busy) {
    state.busy = busy;
    $("admin-submit").disabled = busy;
  }

  function submit(event) {
    event.preventDefault();
    if (state.busy) return;
    setBusy(true);
    fetch("/auth/admin-login", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ username: $("admin-username").value, password: $("admin-password").value })
    })
      .then(function (response) {
        if (response.ok) {
          window.location.replace("/");
          return;
        }
        state.errorKey = response.status === 401 ? "admin.invalid" : "admin.failed";
        setInvalid(response.status === 401);
        $("admin-password").value = "";
        $("admin-password").focus();
        renderError();
      })
      .catch(function () {
        state.errorKey = "admin.failed";
        renderError();
      })
      .then(function () {
        setBusy(false);
      });
  }

  // Escape closes the modal; Tab stays inside it while it is open.
  function onKeydown(event) {
    if (dialog().hidden) return;
    if (event.key === "Escape") {
      close();
      return;
    }
    if (event.key !== "Tab") return;
    var items = focusable();
    var first = items[0];
    var last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  // Only the login page has the link; on any other page this does nothing.
  if ($("admin-open") && dialog()) {
    $("admin-open").addEventListener("click", open);
    $("admin-cancel").addEventListener("click", close);
    $("admin-form").addEventListener("submit", submit);
    document.addEventListener("keydown", onKeydown);
    document.addEventListener("unispace:langchange", renderError);
  }
})();
