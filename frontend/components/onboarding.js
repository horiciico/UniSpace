/*
 * Component: the first-sign-in step of a student (D-022). The student picks a faculty, then a
 * study formation of that faculty, and saves both. Until the save succeeds the dialog cannot
 * be closed: there is no Close button, and Escape does nothing. The server decides everything
 * that matters (who is a student, which formations a faculty has); this only shows the choice.
 */
(() => {
  var t = window.UniSpaceI18n.t;
  var api = window.UniSpaceApi;
  var state = {
    faculties: [],
    facultiesFailed: false,
    facultyId: "",
    formations: [],
    formationsFailed: false,
    loadingFormations: false,
    formationId: "",
    busy: false,
    saveFailed: false,
  };
  var root = null;

  function $(id) {
    return document.getElementById(id);
  }

  // Only the login page is excluded: a signed-in visitor there is sent home at once.
  function onLoginPage() {
    return /\/login(\.html)?\/?$/.test(window.location.pathname);
  }

  function build() {
    root = document.createElement("div");
    root.className = "onboarding";
    root.id = "onboarding";
    root.innerHTML =
      '<form class="onboarding__panel" id="onboarding-form" role="dialog" aria-modal="true" ' +
      'aria-labelledby="onboarding-title" novalidate>' +
      '<h2 id="onboarding-title"></h2>' +
      '<p class="onboarding__lead" id="onboarding-lead"></p>' +
      '<div class="notice notice--error onboarding__error" id="onboarding-error" role="alert" hidden>' +
      '<span id="onboarding-error-text"></span> ' +
      '<button class="btn btn-ghost" id="onboarding-retry" type="button"></button>' +
      "</div>" +
      '<div class="field"><label for="onboarding-faculty" id="onboarding-faculty-label"></label>' +
      '<select id="onboarding-faculty"></select></div>' +
      '<div class="field"><label for="onboarding-formation" id="onboarding-formation-label"></label>' +
      '<select id="onboarding-formation" disabled></select>' +
      '<p class="muted" id="onboarding-hint" hidden></p></div>' +
      '<div class="onboarding__actions">' +
      '<button class="btn btn-primary" id="onboarding-save" type="submit" disabled></button>' +
      "</div>" +
      "</form>";
    document.body.appendChild(root);
  }

  function option(value, label) {
    var element = document.createElement("option");
    element.value = value;
    element.textContent = label;
    return element;
  }

  function renderFaculties() {
    var select = $("onboarding-faculty");
    select.innerHTML = "";
    select.appendChild(option("", t("onboarding.pickFaculty")));
    state.faculties.forEach((faculty) => {
      select.appendChild(option(faculty.id, faculty.name));
    });
    select.value = state.facultyId;
    select.disabled = state.busy || state.facultiesFailed;
  }

  function renderFormations() {
    var select = $("onboarding-formation");
    var hint = $("onboarding-hint");
    var empty =
      !!state.facultyId &&
      !state.loadingFormations &&
      !state.formationsFailed &&
      state.formations.length === 0;
    var placeholder = t("onboarding.pickFormation");
    if (!state.facultyId) placeholder = t("onboarding.chooseFacultyFirst");
    else if (state.loadingFormations) placeholder = t("onboarding.loading");
    select.innerHTML = "";
    select.appendChild(option("", placeholder));
    state.formations.forEach((formation) => {
      select.appendChild(option(formation.id, formation.name));
    });
    select.value = state.formationId;
    select.disabled =
      !state.facultyId ||
      state.loadingFormations ||
      state.formationsFailed ||
      empty ||
      state.busy;
    hint.hidden = !empty;
    hint.textContent = empty ? t("onboarding.noFormations") : "";
  }

  function renderError() {
    var box = $("onboarding-error");
    var loadFailed = state.facultiesFailed || state.formationsFailed;
    box.hidden = !(loadFailed || state.saveFailed);
    $("onboarding-error-text").textContent = state.saveFailed
      ? t("onboarding.saveFailed")
      : t("onboarding.loadFailed");
    $("onboarding-retry").hidden = !loadFailed;
    $("onboarding-retry").textContent = t("onboarding.retry");
  }

  function render() {
    $("onboarding-title").textContent = t("onboarding.title");
    $("onboarding-lead").textContent = t("onboarding.lead");
    $("onboarding-faculty-label").textContent = t("onboarding.faculty");
    $("onboarding-formation-label").textContent = t("onboarding.formation");
    $("onboarding-save").textContent = state.busy
      ? t("onboarding.saving")
      : t("onboarding.save");
    $("onboarding-save").disabled = state.busy || !state.formationId;
    renderFaculties();
    renderFormations();
    renderError();
  }

  function loadFaculties() {
    state.facultiesFailed = false;
    render();
    api
      .faculties()
      .then((list) => {
        state.faculties = list;
      })
      .catch(() => {
        state.facultiesFailed = true;
      })
      .then(render);
  }

  // Each load is tied to the faculty it was asked for: an answer that arrives after the
  // student has picked another faculty is dropped.
  function loadFormations() {
    var asked = state.facultyId;
    state.formations = [];
    state.formationsFailed = false;
    state.loadingFormations = true;
    state.formationId = "";
    render();
    api
      .groups(asked)
      .then((list) => {
        if (asked === state.facultyId) state.formations = list;
      })
      .catch(() => {
        if (asked === state.facultyId) state.formationsFailed = true;
      })
      .then(() => {
        if (asked !== state.facultyId) return;
        state.loadingFormations = false;
        render();
      });
  }

  function onFacultyChange() {
    state.facultyId = $("onboarding-faculty").value;
    state.saveFailed = false;
    if (state.facultyId) {
      loadFormations();
    } else {
      state.formations = [];
      state.formationsFailed = false;
      state.formationId = "";
      render();
    }
  }

  function onFormationChange() {
    state.formationId = $("onboarding-formation").value;
    state.saveFailed = false;
    render();
  }

  function retry() {
    if (state.facultiesFailed) loadFaculties();
    else loadFormations();
  }

  function close() {
    root.remove();
    root = null;
  }

  function submit(event) {
    event.preventDefault();
    if (state.busy || !state.facultyId || !state.formationId) return;
    state.busy = true;
    state.saveFailed = false;
    render();
    api
      .saveStudyProfile(state.facultyId, state.formationId)
      .then(close, () => {
        state.saveFailed = true;
      })
      .then(() => {
        state.busy = false;
        if (root) render();
      });
  }

  // Tab stays inside the dialog. Escape is not handled: the choice cannot be skipped.
  function onKeydown(event) {
    if (!root || event.key !== "Tab") return;
    var items = Array.prototype.slice
      .call(root.querySelectorAll("select, button"))
      .filter((el) => !el.disabled && !el.hidden);
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

  function start() {
    build();
    render();
    $("onboarding-faculty").addEventListener("change", onFacultyChange);
    $("onboarding-formation").addEventListener("change", onFormationChange);
    $("onboarding-form").addEventListener("submit", submit);
    $("onboarding-retry").addEventListener("click", retry);
    document.addEventListener("keydown", onKeydown);
    document.addEventListener("unispace:langchange", () => {
      if (root) render();
    });
    loadFaculties();
    $("onboarding-faculty").focus();
  }

  window.UniSpaceAuth.ready.then((user) => {
    if (user && user.needs_onboarding && !onLoginPage()) start();
  });
})();
