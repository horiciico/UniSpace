/*
 * Orar (timetable) page. The tabs choose what to show (group, professor or room), the
 * faculty narrows the list, and the entity input (with a datalist) picks one. The week comes
 * from /api/schedule and is drawn by grid.js. The selection is kept in the URL, so
 * /timetable?mode=room&faculty_id=...&id=... opens a room (from the free-rooms page).
 * Names and times from the backend are shown as they arrive (D-012).
 */
(function () {
  "use strict";

  var t = window.UniSpaceI18n.t;
  var api = window.UniSpaceApi;
  var grid = window.UniSpaceGrid;

  var gridElement = document.getElementById("tt-grid");
  if (!gridElement) return;
  var body = document.getElementById("tt-body");
  var emptyNote = document.getElementById("tt-empty");
  var statusLine = document.getElementById("tt-status");
  var facultySelect = document.getElementById("tt-faculty");
  var entityInput = document.getElementById("tt-entity");
  var entityLabel = document.getElementById("tt-entity-label");
  var entityList = document.getElementById("entity-list");
  var weekLabel = document.getElementById("tt-week-label");
  var dialog = document.getElementById("tt-dialog");
  var tabs = document.querySelectorAll("[role='tab'][data-mode]");

  var ENTITY_LABEL_KEYS = {
    group: "timetable.entityGroup",
    professor: "timetable.entityProfessor",
    room: "timetable.entityRoom"
  };
  var PARITY_KEYS = { ALL: "timetable.parityAll", ODD: "timetable.parityOdd", EVEN: "timetable.parityEven" };
  var KIND_KEYS = {
    COURSE: "kind.course",
    SEMINAR: "kind.seminar",
    LAB: "kind.lab",
    EXAM: "kind.exam",
    RESERVATION: "kind.reservation"
  };

  function pad(value) {
    return String(value).padStart(2, "0");
  }

  function isoDate(date) {
    return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate());
  }

  function parseIso(text) {
    var parts = text.split("-");
    return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
  }

  function addDays(date, days) {
    return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
  }

  // Monday of the week that contains the date (Sunday belongs to the week before).
  function mondayOf(date) {
    return addDays(date, -((date.getDay() + 6) % 7));
  }

  function locale() {
    return window.UniSpaceI18n.current() === "ro" ? "ro-RO" : "en-GB";
  }

  var params = new URLSearchParams(window.location.search);
  var state = {
    mode: ENTITY_LABEL_KEYS[params.get("mode")] ? params.get("mode") : "group",
    facultyId: params.get("faculty_id") || "",
    urlEntityId: params.get("id") || "",
    faculties: [],
    entities: [],
    entity: null,
    monday: mondayOf(/^\d{4}-\d{2}-\d{2}$/.test(params.get("date") || "")
      ? parseIso(params.get("date"))
      : new Date()),
    week: null,
    items: null,
    statusKey: "",
    statusError: false,
    requestNumber: 0,
    entityRequestNumber: 0
  };

  function setStatus(key, isError) {
    state.statusKey = key || "";
    state.statusError = Boolean(isError);
    statusLine.textContent = key ? t(key) : "";
    statusLine.className = state.statusError && key ? "notice notice--error" : "muted";
  }

  function renderWeek() {
    var sunday = addDays(state.monday, 6);
    var format = new Intl.DateTimeFormat(locale(), { day: "numeric", month: "short" });
    var range = format.format(state.monday) + " – " + format.format(sunday);
    if (state.week && state.week.number) {
      var parity = t(PARITY_KEYS[state.week.parity] || "timetable.parityAll");
      weekLabel.textContent = range + " · " + t("timetable.weekLabel", { n: state.week.number, parity: parity });
    } else {
      weekLabel.textContent = range;
    }
  }

  function renderEntityLabel() {
    entityLabel.textContent = t(ENTITY_LABEL_KEYS[state.mode]);
  }

  function renderTabs() {
    tabs.forEach(function (tab) {
      tab.setAttribute("aria-selected", String(tab.getAttribute("data-mode") === state.mode));
    });
  }

  function populateFaculties() {
    var chosen = state.facultyId;
    if (chosen === "campus" && state.mode !== "room") chosen = "";
    facultySelect.textContent = "";
    var placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = t("timetable.chooseFaculty");
    facultySelect.appendChild(placeholder);
    if (state.mode === "room") {
      var campus = document.createElement("option");
      campus.value = "campus";
      campus.textContent = t("common.campus");
      facultySelect.appendChild(campus);
    }
    state.faculties.forEach(function (faculty) {
      var option = document.createElement("option");
      option.value = faculty.id;
      option.textContent = faculty.name;
      facultySelect.appendChild(option);
    });
    facultySelect.value = chosen;
    state.facultyId = facultySelect.value;
  }

  function showEmpty() {
    body.hidden = true;
    emptyNote.hidden = false;
  }

  function showBody() {
    emptyNote.hidden = true;
    body.hidden = false;
  }

  function fillEntityList() {
    entityList.textContent = "";
    state.entities.forEach(function (entity) {
      var option = document.createElement("option");
      option.value = entity.name;
      entityList.appendChild(option);
    });
  }

  // Loads the groups, professors or rooms of the faculty into the datalist.
  function loadEntities() {
    var request = ++state.entityRequestNumber;
    entityInput.disabled = !state.facultyId;
    // Drop the previous list at once, so the datalist never offers the old tab's names.
    state.entities = [];
    fillEntityList();
    if (!state.facultyId) return Promise.resolve();
    var source;
    if (state.mode === "group") {
      source = api.groups(state.facultyId).then(function (rows) {
        return rows.map(function (row) { return { id: row.id, name: row.name }; });
      });
    } else if (state.mode === "professor") {
      source = api.professors(state.facultyId).then(function (rows) {
        return rows.map(function (row) { return { id: row.name, name: row.name }; });
      });
    } else {
      source = api.classrooms(state.facultyId).then(function (rows) {
        return rows.map(function (row) { return { id: row.id, name: row.name }; });
      });
    }
    return source.then(function (entities) {
      if (request !== state.entityRequestNumber) return;
      state.entities = entities;
      fillEntityList();
    }).catch(function () {
      if (request !== state.entityRequestNumber) return;
      state.entities = [];
      fillEntityList();
      setStatus("timetable.error", true);
    });
  }

  function findEntity(name) {
    for (var i = 0; i < state.entities.length; i++) {
      if (state.entities[i].name === name) return state.entities[i];
    }
    return null;
  }

  function updateUrl() {
    var search = new URLSearchParams();
    search.set("mode", state.mode);
    if (state.facultyId) search.set("faculty_id", state.facultyId);
    if (state.entity) search.set("id", state.entity.id);
    search.set("date", isoDate(state.monday));
    window.history.replaceState(null, "", "?" + search.toString());
  }

  function scheduleParams() {
    var values = { date: isoDate(state.monday) };
    if (state.mode === "group") values.group_id = state.entity.id;
    else if (state.mode === "professor") values.professor = state.entity.name;
    else values.room_id = state.entity.id;
    return values;
  }

  function loadSchedule() {
    if (!state.entity) {
      state.items = null;
      state.week = null;
      renderWeek();
      setStatus("");
      showEmpty();
      return;
    }
    var request = ++state.requestNumber;
    setStatus("timetable.loading");
    api.schedule(scheduleParams()).then(function (data) {
      if (request !== state.requestNumber) return;
      state.items = data.items;
      state.week = { number: data.week_number, parity: data.parity };
      renderWeek();
      setStatus(data.items.length ? "" : "timetable.noItems");
      drawGrid();
      showBody();
    }).catch(function (error) {
      if (request !== state.requestNumber) return;
      state.items = null;
      renderWeek();
      setStatus(error.status === 404 ? "timetable.notFound" : "timetable.error", true);
      showEmpty();
    });
  }

  function drawGrid() {
    if (!state.items) return;
    grid.render(gridElement, state.items, openDetails);
  }

  function openDetails(item) {
    var fill = function (id, text) {
      var node = document.getElementById(id);
      if (node) node.textContent = text;
    };
    var kind = KIND_KEYS[item.activity_type] ? t(KIND_KEYS[item.activity_type]) : item.activity_type;
    var day = new Intl.DateTimeFormat(locale(), { weekday: "long", day: "numeric", month: "long" })
      .format(parseIso(item.date));
    fill("tt-d-title", item.title);
    fill("tt-d-kind", kind);
    fill("tt-d-date", day);
    fill("tt-d-time", item.start_time + "–" + item.end_time);
    fill("tt-d-room", item.room_name);
    fill("tt-d-professor", item.professor || t("timetable.unknown"));
    fill("tt-d-groups", item.groups && item.groups.length ? item.groups.join(", ") : t("timetable.unknown"));
    fill("tt-d-priority", String(item.priority));
    fill("tt-d-parity", t(PARITY_KEYS[item.parity] || "timetable.parityAll"));
    fill("tt-d-recurring", item.is_recurring ? t("timetable.recurring") : t("timetable.oneOff"));
    if (!dialog) return;
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  }

  function chooseEntity(entity) {
    state.entity = entity;
    updateUrl();
    loadSchedule();
  }

  function onEntityChange(isFinal) {
    var name = entityInput.value.trim();
    if (!name) {
      if (state.entity) {
        state.entity = null;
        updateUrl();
        loadSchedule();
      }
      return;
    }
    var found = findEntity(name);
    if (found) {
      if (!state.entity || state.entity.id !== found.id) chooseEntity(found);
    } else if (isFinal) {
      state.entity = null;
      state.items = null;
      renderWeek();
      setStatus("timetable.notFound", true);
      showEmpty();
    }
  }

  function setMode(mode) {
    state.mode = mode;
    renderTabs();
    renderEntityLabel();
    entityInput.value = "";
    state.entity = null;
    state.items = null;
    populateFaculties();
    updateUrl();
    loadEntities();
    setStatus("");
    showEmpty();
  }

  function init() {
    renderTabs();
    renderEntityLabel();
    renderWeek();
    showEmpty();

    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        setMode(tab.getAttribute("data-mode"));
      });
    });

    facultySelect.addEventListener("change", function () {
      state.facultyId = facultySelect.value;
      entityInput.value = "";
      state.entity = null;
      updateUrl();
      loadEntities();
      loadSchedule();
    });

    entityInput.addEventListener("input", function () { onEntityChange(false); });
    entityInput.addEventListener("change", function () { onEntityChange(true); });

    document.getElementById("tt-prev").addEventListener("click", function () {
      state.monday = addDays(state.monday, -7);
      updateUrl();
      loadSchedule();
    });
    document.getElementById("tt-next").addEventListener("click", function () {
      state.monday = addDays(state.monday, 7);
      updateUrl();
      loadSchedule();
    });
    document.getElementById("tt-today").addEventListener("click", function () {
      state.monday = mondayOf(new Date());
      updateUrl();
      loadSchedule();
    });
    var close = document.getElementById("tt-d-close");
    if (close && dialog) close.addEventListener("click", function () { dialog.close(); });

    api.faculties().then(function (faculties) {
      state.faculties = faculties;
      populateFaculties();
      return loadEntities();
    }).then(function () {
      if (!state.facultyId || !state.urlEntityId) {
        updateUrl();
        return;
      }
      var match = state.entities.filter(function (entity) {
        return entity.id === state.urlEntityId;
      })[0];
      if (match) {
        entityInput.value = match.name;
        chooseEntity(match);
      } else {
        setStatus("timetable.notFound", true);
      }
    }).catch(function () {
      setStatus("timetable.error", true);
    });
  }

  // Everything built by the script is translated again when the language changes.
  document.addEventListener("unispace:langchange", function () {
    renderTabs();
    renderEntityLabel();
    renderWeek();
    populateFaculties();
    fillEntityList();
    setStatus(state.statusKey, state.statusError);
    if (dialog && dialog.open) dialog.close();
    if (state.items && !body.hidden) drawGrid();
  });

  init();
})();
