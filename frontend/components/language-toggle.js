/*
 * Component: the RO | EN language switch (a two-segment pill in the header).
 * Clicking a segment calls UniSpaceI18n.setLanguage; the app rebuilds the chrome.
 */
(() => {
  window.UniSpaceUI = window.UniSpaceUI || {};
  var UI = window.UniSpaceUI;

  UI.languageToggle = () => {
    var t = window.UniSpaceI18n.t;
    var group = document.createElement("div");
    group.className = "lang-toggle";
    group.setAttribute("role", "group");
    group.setAttribute("aria-label", t("header.language"));
    var current = window.UniSpaceI18n.current();
    window.UniSpaceI18n.languages.forEach((code) => {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "lang-toggle__btn";
      button.dataset.lang = code;
      button.textContent = code.toUpperCase();
      button.setAttribute("aria-pressed", String(code === current));
      group.appendChild(button);
    });
    group.addEventListener("click", (event) => {
      var button = event.target.closest("[data-lang]");
      if (button) window.UniSpaceI18n.setLanguage(button.dataset.lang);
    });
    return group;
  };
})();
