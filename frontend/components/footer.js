/*
 * Component: the site footer, appended to the end of every page.
 */
(() => {
  window.UniSpaceUI = window.UniSpaceUI || {};
  var UI = window.UniSpaceUI;

  UI.buildFooter = () => {
    var t = window.UniSpaceI18n.t;
    var footer = document.createElement("footer");
    footer.className = "site-footer";
    footer.innerHTML =
      "<p>" +
      UI.escapeHtml(t("footer.note")) +
      "</p>" +
      '<p><a href="/">' +
      UI.escapeHtml(t("footer.home")) +
      '</a> · <a href="/calendar">' +
      UI.escapeHtml(t("footer.subscribe")) +
      "</a></p>";
    document.body.appendChild(footer);
  };
})();
