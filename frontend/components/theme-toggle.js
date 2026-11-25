/*
 * Component: the theme button (auto, light, dark). The choice is kept in localStorage
 * under unispace-theme; "auto" follows the operating system.
 */
(() => {
  window.UniSpaceUI = window.UniSpaceUI || {};
  var UI = window.UniSpaceUI;
  var THEMES = ["auto", "light", "dark"];

  UI.currentTheme = () => localStorage.getItem("unispace-theme") || "auto";

  UI.applyTheme = (mode) => {
    var root = document.documentElement;
    if (mode === "auto") {
      root.removeAttribute("data-theme");
    } else {
      root.setAttribute("data-theme", mode);
    }
    var button = document.querySelector(".theme-toggle");
    if (button) {
      button.textContent = window.UniSpaceI18n.t("theme." + mode);
    }
  };

  UI.bindTheme = () => {
    UI.applyTheme(UI.currentTheme());
    var button = document.querySelector(".theme-toggle");
    if (!button) return;
    button.addEventListener("click", () => {
      var next =
        THEMES[(THEMES.indexOf(UI.currentTheme()) + 1) % THEMES.length];
      localStorage.setItem("unispace-theme", next);
      UI.applyTheme(next);
    });
  };
})();
