/*
 * Admin: the Academic calendar tab (D-028, C-010). Lists the periods (semester, exam session,
 * holiday) of all faculties or of one, by start date. A period is added or edited in the card under the table; a delete asks
 * first. The dates are checked here (start on or before end) and again by the backend, which also
 * refuses overlapping periods (409). The periods load when the tab is opened.
 * Period names and dates are shown as they arrive (D-012); the words around them are translated.
 */
(() => {
  var t = window.UniSpaceI18n.t;
  var api = window.UniSpaceApi;

  var tab = document.querySelector('[role="tab"][data-tab="calendar"]');
  var statusLine = document.getElementById("acal-status");
  var body = document.getElementById("acal-body");
  var emptyCard = document.getElementById("acal-empty");
  var defaultNote = document.getElementById("acal-default-note");
  var addButton = document.getElementById("acal-add");
  var editCard = document.getElementById("acal-edit");
  var editTitle = document.getElementById("acal-edit-title");
  var formError = document.getElementById("acal-form-error");
  var form = document.getElementById("acal-form");
  var nameInput = /** @type {HTMLInputElement} */ (
    document.getElementById("acal-name")
  );
  var facultySelect = /** @type {HTMLSelectElement} */ (
    document.getElementById("acal-faculty")
  );
  var typeSelect = /** @type {HTMLSelectElement} */ (
    document.getElementById("acal-type")
  );
  var startInput = /** @type {HTMLInputElement} */ (
    document.getElementById("acal-start")
  );
  var endInput = /** @type {HTMLInputElement} */ (
    document.getElementById("acal-end")
  );
  var saveButton = /** @type {HTMLButtonElement} */ (
    document.getElementById("acal-save")
  );
  var cancelButton = document.getElementById("acal-cancel");
  var deleteCard = document.getElementById("acal-delete");
  var deleteTitle = document.getElementById("acal-delete-title");
  var deleteText = document.getElementById("acal-delete-text");
  var deleteConfirm = /** @type {HTMLButtonElement} */ (
    document.getElementById("acal-delete-confirm")
  );
  var deleteKeep = document.getElementById("acal-delete-keep");

  // The label and the pill of each type: literal keys, so the key check reads them. A badge
  // always has its word, so colour is never the only signal.
  var TYPES = {
    TEACHING: { key: "acal.typeTEACHING", pill: "pill pill--confirmed" },
    EXAM_SESSION: { key: "acal.typeEXAM_SESSION", pill: "pill pill--pending" },
    HOLIDAY: { key: "acal.typeHOLIDAY", pill: "pill pill--busy" },
  };

  var state = {
    periods: [],
    faculties: [],
    facultiesFailed: false,
    editing: null, // the period being edited, or "new"
    deleting: null,
    request: 0,
    formErrorKey: "",
  };

  function setStatus(key, isError) {
    statusLine.hidden = !key;
    statusLine.textContent = key ? t(key) : "";
    statusLine.className = isError ? "notice notice--error" : "notice";
  }

  function setFormError(key) {
    state.formErrorKey = key || "";
    formError.hidden = !key;
    formError.textContent = key ? t(key) : "";
  }

  function load() {
    var request = ++state.request;
    return api
      .adminAcademicPeriods()
      .then((periods) => {
        if (request !== state.request) return;
        state.periods = periods;
        setStatus("");
        render();
      })
      .catch(() => {
        if (request !== state.request) return;
        setStatus("acal.loadError", true);
      });
  }

  // "All faculties" (in the page), then each faculty. The period's own faculty stays in the list
  // when the faculties could not be loaded, so saving never moves it to all faculties.
  function renderFacultyOptions(chosen, chosenName) {
    while (facultySelect.options.length > 1) facultySelect.remove(1);
    var list = state.faculties.slice();
    if (chosen && !list.some((faculty) => faculty.id === chosen))
      list.push({ id: chosen, name: chosenName });
    list.forEach((faculty) => {
      var option = document.createElement("option");
      option.value = faculty.id;
      option.textContent = faculty.name;
      facultySelect.appendChild(option);
    });
    facultySelect.value = chosen;
  }

  function loadFaculties() {
    return api
      .faculties()
      .then((faculties) => {
        state.faculties = faculties;
        state.facultiesFailed = false;
        const chosen = facultySelect.value;
        const option = facultySelect.options[facultySelect.selectedIndex];
        renderFacultyOptions(chosen, option.textContent);
        if (state.formErrorKey === "acal.facultiesError") setFormError("");
      })
      .catch(() => {
        state.facultiesFailed = true;
        if (state.editing) setFormError("acal.facultiesError");
      });
  }

  function cell(text) {
    var td = document.createElement("td");
    td.textContent = text;
    return td;
  }

  function actionButton(key, ariaKey, name, onClick) {
    var button = document.createElement("button");
    button.className = "btn btn-secondary btn-small";
    button.type = "button";
    button.textContent = t(key);
    button.setAttribute("aria-label", t(ariaKey, { name: name }));
    button.addEventListener("click", onClick);
    return button;
  }

  function row(period) {
    var tr = document.createElement("tr");
    var name = document.createElement("td");
    var strong = document.createElement("strong");
    strong.textContent = period.name;
    name.appendChild(strong);
    tr.appendChild(name);
    tr.appendChild(cell(period.faculty_name || t("acal.allFaculties")));

    var type = document.createElement("td");
    var badge = document.createElement("span");
    badge.className = TYPES[period.type].pill;
    badge.textContent = t(TYPES[period.type].key);
    type.appendChild(badge);
    tr.appendChild(type);

    tr.appendChild(cell(period.start_date));
    tr.appendChild(cell(period.end_date));

    var actions = document.createElement("td");
    var group = document.createElement("div");
    group.className = "btn-group";
    group.appendChild(
      actionButton("acal.edit", "acal.editAria", period.name, () => {
        openEditor(period);
      }),
    );
    group.appendChild(
      actionButton("acal.delete", "acal.deleteAria", period.name, () => {
        openDelete(period);
      }),
    );
    actions.appendChild(group);
    tr.appendChild(actions);
    return tr;
  }

  function render() {
    body.textContent = "";
    state.periods.forEach((period) => {
      body.appendChild(row(period));
    });
    emptyCard.hidden = state.periods.length > 0;
    defaultNote.hidden = state.periods.length === 0;
  }

  function openEditor(period) {
    closeDelete();
    state.editing = period || "new";
    nameInput.value = period ? period.name : "";
    renderFacultyOptions(
      (period && period.faculty_id) || "",
      period && period.faculty_name,
    );
    typeSelect.value = period ? period.type : "TEACHING";
    startInput.value = period ? period.start_date : "";
    endInput.value = period ? period.end_date : "";
    setFormError(state.facultiesFailed ? "acal.facultiesError" : "");
    renderEditorTitle();
    editCard.hidden = false;
    nameInput.focus();
  }

  function renderEditorTitle() {
    editTitle.textContent = t(
      state.editing === "new" ? "acal.addTitle" : "acal.editTitle",
    );
  }

  function closeEditor() {
    state.editing = null;
    editCard.hidden = true;
    setFormError("");
  }

  function openDelete(period) {
    closeEditor();
    state.deleting = period;
    renderDelete();
    deleteCard.hidden = false;
    deleteConfirm.focus();
  }

  function renderDelete() {
    var period = state.deleting;
    deleteTitle.textContent = t("acal.deleteTitle", { name: period.name });
    var values = {
      faculty: period.faculty_name,
      start: period.start_date,
      end: period.end_date,
    };
    deleteText.textContent = period.faculty_id
      ? t("acal.deleteTextFaculty", values)
      : t("acal.deleteText", values);
  }

  function closeDelete() {
    state.deleting = null;
    deleteCard.hidden = true;
  }

  // What the backend's refusal means for the admin (C-010): 409 overlap, 400 dates, 422 a bad value.
  function saveErrorKey(status) {
    if (status === 409) return "acal.errorOverlap";
    if (status === 400) return "acal.errorDates";
    if (status === 422) return "acal.errorInvalid";
    return "acal.saveError";
  }

  function save() {
    var payload = {
      name: nameInput.value.trim(),
      type: typeSelect.value,
      start_date: startInput.value,
      end_date: endInput.value,
      faculty_id: facultySelect.value || null,
    };
    if (!payload.name) return setFormError("acal.errorName");
    if (!payload.start_date || !payload.end_date)
      return setFormError("acal.errorMissingDates");
    if (payload.start_date > payload.end_date)
      return setFormError("acal.errorDates");
    setFormError("");
    saveButton.disabled = true;
    var editing = state.editing;
    var request =
      editing === "new"
        ? api.createAcademicPeriod(payload)
        : api.updateAcademicPeriod(editing.id, payload);
    return request
      .then(() => {
        saveButton.disabled = false;
        closeEditor();
        window.UniSpaceUI.toast(t("acal.saved"));
        return load();
      })
      .catch((error) => {
        saveButton.disabled = false;
        setFormError(saveErrorKey(error.status));
      });
  }

  function remove() {
    var period = state.deleting;
    deleteConfirm.disabled = true;
    return api
      .deleteAcademicPeriod(period.id)
      .then(() => {
        deleteConfirm.disabled = false;
        closeDelete();
        window.UniSpaceUI.toast(t("acal.deleted"));
        return load();
      })
      .catch(() => {
        deleteConfirm.disabled = false;
        closeDelete();
        setStatus("acal.deleteError", true);
      });
  }

  tab.addEventListener("click", () => {
    closeEditor();
    closeDelete();
    loadFaculties();
    load();
  });
  addButton.addEventListener("click", () => {
    openEditor(null);
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    save();
  });
  cancelButton.addEventListener("click", closeEditor);
  deleteConfirm.addEventListener("click", remove);
  deleteKeep.addEventListener("click", closeDelete);

  // Labels built by the script are built again in the new language.
  document.addEventListener("unispace:langchange", () => {
    render();
    if (state.editing) {
      renderEditorTitle();
      setFormError(state.formErrorKey);
    }
    if (state.deleting) renderDelete();
  });
})();
