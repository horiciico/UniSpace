/*
 * UniSpace i18n runtime. Loaded in <head> before every other page script.
 *
 * Languages: ro (Romanian) and en (English). The first visit follows the browser: the
 * first language in navigator.languages that is ro or en; otherwise Romanian. A choice
 * made with the header toggle is remembered in localStorage and wins over the browser.
 *
 * Text in the pages:
 *   <h1 data-i18n="home.title">…</h1>                       textContent
 *   <input data-i18n-attr="placeholder:home.search">         attributes, "name:key;name:key"
 *   <span data-i18n="home.count" data-i18n-vars="n:5">      {n} in the text is replaced
 * Scripts call UniSpaceI18n.t(key, vars).
 *
 * Only text the frontend itself defines goes here. Records from the backend (room
 * names, course titles, times of real classes) are shown as they arrive.
 *
 * A key missing in the chosen language falls back to English, then to the key itself,
 * with a console warning, so a gap is visible rather than silent.
 */
(() => {
  var LANGUAGES = ["ro", "en"];
  var DEFAULT_LANGUAGE = "ro";
  var STORAGE_KEY = "unispace-lang";
  var dictionaries = {};

  function fromStorage() {
    try {
      const value = localStorage.getItem(STORAGE_KEY);
      return LANGUAGES.indexOf(value) !== -1 ? value : null;
    } catch (error) {
      return null;
    }
  }

  function fromBrowser() {
    var list =
      navigator.languages && navigator.languages.length
        ? navigator.languages
        : [navigator.language || ""];
    for (let i = 0; i < list.length; i++) {
      const code = String(list[i]).toLowerCase().split("-")[0];
      if (LANGUAGES.indexOf(code) !== -1) return code;
    }
    return DEFAULT_LANGUAGE;
  }

  var current = fromStorage() || fromBrowser();
  document.documentElement.lang = current;

  function lookup(language, key) {
    var dictionary = dictionaries[language];
    return dictionary && Object.hasOwn(dictionary, key)
      ? dictionary[key]
      : undefined;
  }

  function t(key, vars) {
    var text = lookup(current, key);
    if (text === undefined) text = lookup("en", key);
    if (text === undefined) {
      console.warn('i18n: no text for key "' + key + '"');
      return key;
    }
    if (vars) {
      text = text.replace(/\{(\w+)\}/g, (match, name) =>
        vars[name] !== undefined ? vars[name] : match,
      );
    }
    return text;
  }

  // "time:14:30;n:5" -> { time: "14:30", n: "5" }. The first colon separates name and value.
  function parseVars(spec) {
    var vars = {};
    spec.split(";").forEach((pair) => {
      var index = pair.indexOf(":");
      if (index > 0)
        vars[pair.slice(0, index).trim()] = pair.slice(index + 1).trim();
    });
    return vars;
  }

  function applyTo(root) {
    root.querySelectorAll("[data-i18n]").forEach((el) => {
      var vars = el.hasAttribute("data-i18n-vars")
        ? parseVars(el.getAttribute("data-i18n-vars"))
        : null;
      el.textContent = t(el.getAttribute("data-i18n"), vars);
    });
    root.querySelectorAll("[data-i18n-attr]").forEach((el) => {
      el.getAttribute("data-i18n-attr")
        .split(";")
        .forEach((pair) => {
          var index = pair.indexOf(":");
          if (index > 0) {
            el.setAttribute(
              pair.slice(0, index).trim(),
              t(pair.slice(index + 1).trim()),
            );
          }
        });
    });
  }

  function setLanguage(language) {
    if (LANGUAGES.indexOf(language) === -1 || language === current) return;
    current = language;
    try {
      localStorage.setItem(STORAGE_KEY, language);
    } catch (error) {
      // Private mode can refuse storage; the choice then lasts for this page only.
    }
    document.documentElement.lang = language;
    applyTo(document);
    document.dispatchEvent(
      new CustomEvent("unispace:langchange", { detail: { lang: language } }),
    );
  }

  window.UniSpaceI18n = {
    languages: LANGUAGES.slice(),
    register: (language, dictionary) => {
      dictionaries[language] = dictionary;
    },
    t: t,
    current: () => current,
    setLanguage: setLanguage,
    apply: applyTo,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      applyTo(document);
    });
  } else {
    applyTo(document);
  }
})();
