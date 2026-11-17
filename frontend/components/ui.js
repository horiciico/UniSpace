/*
 * Shared helpers for the components. Loaded first; every component adds itself to
 * window.UniSpaceUI. The structure is described in docs/agents/ARCHITECTURE.md.
 */
(function () {
  "use strict";

  var UI = (window.UniSpaceUI = window.UniSpaceUI || {});

  UI.escapeHtml = function (text) {
    return String(text).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  };

  UI.normalisePath = function (path) {
    return path.length > 1 ? path.replace(/\/+$/, "") : path;
  };
})();
