/*
 * Component: toast messages, and the placeholder behaviour of the pages. Forms and
 * actions that do not exist yet show a toast instead of sending anything; copy buttons
 * copy the value of the input named by data-copy.
 */
(() => {
  window.UniSpaceUI = window.UniSpaceUI || {};
  var UI = window.UniSpaceUI;

  UI.toast = (message) => {
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
    el._hide = setTimeout(() => {
      el.classList.remove("is-visible");
    }, 3200);
  };

  // Bound once per page. The listeners look up the text when they run, so they follow
  // the language.
  UI.bindActions = () => {
    var t = window.UniSpaceI18n.t;
    document.addEventListener("submit", (event) => {
      if (event.target.matches("form[data-placeholder]")) {
        event.preventDefault();
        UI.toast(t("placeholder.nothingSaved"));
      }
    });
    document.addEventListener("click", (event) => {
      var action = event.target.closest("[data-placeholder-action]");
      if (action) {
        event.preventDefault();
        UI.toast(t(action.dataset.placeholderAction || "placeholder.generic"));
        return;
      }
      var copy = event.target.closest("[data-copy]");
      if (copy) {
        const input = document.querySelector(copy.dataset.copy);
        if (input && navigator.clipboard) {
          navigator.clipboard.writeText(input.value).then(() => {
            UI.toast(t("toast.copied"));
          });
        } else {
          UI.toast(t("toast.copyUnavailable"));
        }
      }
    });
  };
})();
