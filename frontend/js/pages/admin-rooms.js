/*
 * Admin: the Rooms tab (C-007). Lists the rooms of a faculty (or campus) with the attributes the admin
 * sets: bookable, projector, board type, access notes and equipment notes. A room is edited in the panel
 * under the table; Save sends only the form values, and a null clears a value to "unspecified".
 * The rooms load when the tab is opened. The backend decides who may change them and answers 400, 403 or 422.
 */
(function () {
  "use strict";

  var t = window.UniSpaceI18n.t;
  var api = window.UniSpaceApi;

  var tab = document.querySelector('[role="tab"][data-tab="rooms"]');
  var facultySelect = document.getElementById("rooms-faculty");
  var searchInput = document.getElementById("rooms-search");
  var statusLine = document.getElementById("rooms-status");
  var body = document.getElementById("rooms-body");
  var emptyCard = document.getElementById("rooms-empty");
  var editCard = document.getElementById("rooms-edit");
  var editTitle = document.getElementById("rooms-edit-title");
  var editSub = document.getElementById("rooms-edit-sub");
  var form = document.getElementById("rooms-form");
  var bookableInput = document.getElementById("rooms-bookable");
  var projectorSelect = document.getElementById("rooms-projector");
  var boardSelect = document.getElementById("rooms-board");
  var accessInput = document.getElementById("rooms-access");
  var equipmentInput = document.getElementById("rooms-equipment");
  var cancelButton = document.getElementById("rooms-cancel");

  // The board labels: literal keys, so the key check reads them.
  var BOARD_KEYS = {
    whiteboard: "rooms.boardWhiteboard",
    blackboard: "rooms.boardBlackboard",
    smartboard: "rooms.boardSmartboard",
    none: "rooms.boardNone"
  };

  var state = {
    rooms: [],
    facultyNames: {},
    editing: null,
    request: 0
  };

  function setStatus(key, isError) {
    statusLine.hidden = false;
    statusLine.textContent = t(key);
    statusLine.className = isError ? "notice notice--error" : "notice";
  }

  function hideStatus() {
    statusLine.hidden = true;
    statusLine.textContent = "";
  }

  function yesNo(value) {
    return value ? t("rooms.yes") : t("rooms.no");
  }

  // Projector: null is unspecified (the admin has not said), true and false are yes and no.
  function projectorLabel(value) {
    if (value == null) return t("rooms.unspecified");
    return yesNo(value);
  }

  function boardLabel(value) {
    return value ? t(BOARD_KEYS[value]) : t("rooms.unspecified");
  }

  function seatsLabel(room) {
    return room.capacity == null ? t("rooms.seatsUnknown") : String(room.capacity);
  }

  function facultyLabel(room) {
    return room.faculty_id ? state.facultyNames[room.faculty_id] : t("common.campus");
  }

  function placeholderOption(text) {
    var option = document.createElement("option");
    option.value = "";
    option.textContent = text;
    return option;
  }

  // The faculties, then "Campus". Keeps the choice that is on screen.
  function loadFaculties() {
    var chosen = facultySelect.value;
    return api.faculties().then(function (faculties) {
      state.facultyNames = {};
      facultySelect.textContent = "";
      facultySelect.appendChild(placeholderOption(t("adminHistory.allFaculties")));
      var campus = document.createElement("option");
      campus.value = "campus";
      campus.textContent = t("common.campus");
      facultySelect.appendChild(campus);
      faculties.forEach(function (faculty) {
        state.facultyNames[faculty.id] = faculty.name;
        var option = document.createElement("option");
        option.value = faculty.id;
        option.textContent = faculty.name;
        facultySelect.appendChild(option);
      });
      facultySelect.value = chosen;
    }).catch(function () {
      setStatus("rooms.loadError", true);
    });
  }

  // The rooms of the chosen faculty (or campus), or every room when no faculty is chosen.
  // An older answer that arrives after a newer request is ignored.
  function loadRooms() {
    var request = ++state.request;
    return api.adminClassrooms(facultySelect.value || undefined).then(function (rooms) {
      if (request !== state.request) return;
      state.rooms = rooms;
      render();
    }).catch(function () {
      setStatus("rooms.loadError", true);
    });
  }

  function cell(text) {
    var td = document.createElement("td");
    td.textContent = text;
    return td;
  }

  function row(room) {
    var tr = document.createElement("tr");
    tr.appendChild(cell(room.name));
    tr.appendChild(cell(facultyLabel(room)));
    tr.appendChild(cell(seatsLabel(room)));
    tr.appendChild(cell(yesNo(room.is_bookable)));
    tr.appendChild(cell(projectorLabel(room.has_projector)));
    tr.appendChild(cell(boardLabel(room.board_type)));
    tr.appendChild(cell(room.access_notes || t("rooms.unspecified")));

    var actions = document.createElement("td");
    var edit = document.createElement("button");
    edit.className = "btn btn-secondary btn-small";
    edit.type = "button";
    edit.textContent = t("rooms.edit");
    edit.setAttribute("aria-label", t("rooms.editAria", { name: room.name }));
    edit.addEventListener("click", function () {
      openEditor(room);
    });
    actions.appendChild(edit);
    tr.appendChild(actions);
    return tr;
  }

  // Draws the rooms whose name contains the search text (ignoring case).
  function render() {
    var query = searchInput.value.trim().toLowerCase();
    var shown = state.rooms.filter(function (room) {
      return room.name.toLowerCase().indexOf(query) !== -1;
    });
    body.textContent = "";
    shown.forEach(function (room) {
      body.appendChild(row(room));
    });
    emptyCard.hidden = shown.length > 0;
  }

  function openEditor(room) {
    state.editing = room.id;
    editTitle.textContent = t("rooms.editTitle", { name: room.name });
    editSub.textContent = facultyLabel(room) + " · " + seatsLabel(room);
    bookableInput.checked = Boolean(room.is_bookable);
    if (room.has_projector == null) {
      projectorSelect.value = "";
    } else {
      projectorSelect.value = room.has_projector ? "yes" : "no";
    }
    boardSelect.value = room.board_type || "";
    accessInput.value = room.access_notes || "";
    equipmentInput.value = room.equipment_notes || "";
    editCard.hidden = false;
  }

  function closeEditor() {
    state.editing = null;
    editCard.hidden = true;
  }

  // Sends the form. Unspecified projector and board become null; blank notes are sent as they are
  // (the backend trims them and stores null for blank text).
  function save() {
    var payload = {
      is_bookable: bookableInput.checked,
      has_projector: projectorSelect.value === "" ? null : projectorSelect.value === "yes",
      board_type: boardSelect.value || null,
      access_notes: accessInput.value,
      equipment_notes: equipmentInput.value
    };
    return api.patchAdminClassroom(state.editing, payload).then(function (saved) {
      state.rooms = state.rooms.map(function (room) {
        return room.id === saved.id ? saved : room;
      });
      render();
      closeEditor();
      setStatus("rooms.saved");
    }).catch(function (error) {
      setStatus(error.status === 422 ? "rooms.invalid" : "rooms.saveError", true);
    });
  }

  tab.addEventListener("click", function () {
    hideStatus();
    loadFaculties();
    loadRooms();
  });
  facultySelect.addEventListener("change", loadRooms);
  searchInput.addEventListener("input", render);
  form.addEventListener("submit", function (event) {
    event.preventDefault();
    save();
  });
  cancelButton.addEventListener("click", closeEditor);

  // Labels built by the script are built again in the new language, and the open editor too.
  document.addEventListener("unispace:langchange", function () {
    loadFaculties();
    render();
    if (state.editing) {
      var editing = state.rooms.filter(function (room) {
        return room.id === state.editing;
      })[0];
      openEditor(editing);
    }
  });
})();
