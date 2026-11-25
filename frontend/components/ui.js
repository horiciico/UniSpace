/*
 * Shared helpers for the components. Loaded first; every component adds itself to
 * window.UniSpaceUI. The structure is described in docs/agents/ARCHITECTURE.md.
 */
(() => {
  window.UniSpaceUI = window.UniSpaceUI || {};
  var UI = window.UniSpaceUI;

  UI.escapeHtml = (text) =>
    String(text).replace(
      /[&<>"']/g,
      (ch) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[ch],
    );

  UI.normalisePath = (path) =>
    path.length > 1 ? path.replace(/\/+$/, "") : path;
})();
