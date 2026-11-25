/*
 * Admin: booking history (C-006). Two tabs on the admin page: the pending requests, and this history.
 * The history lists every booking, past and current, newest first, 15 to a page. The filters are
 * faculty (or Campus), room (the rooms of that faculty, or all rooms when no faculty is chosen) and
 * status; with no faculty chosen, every booking is listed. An approved booking that has not started
 * can be cancelled by an admin, after a confirmation. The backend decides and answers 400, 409 or 403.
 */
(function () {
  "use strict";

  var t = window.UniSpaceI18n.t;
  var api = window.UniSpaceApi;
  var statuses = window.UniSpaceBookings;

  var panel = document.getElementById("panel-history");
  if (!panel) return;
  var body = document.getElementById("hist-body");
  var facultySelect = document.getElementById("hist-faculty");
  var roomSelect = document.getElementById("hist-room");
  var statusSelect = document.getElementById("hist-status");
  var statusLine = document.getElementById("hist-status-line");
  var emptyCard = document.getElementById("hist-empty");
  var pager = document.getElementById("hist-pager");
  var prevButton = document.getElementById("hist-prev");
  var nextButton = document.getElementById("hist-next");
  var rangeLabel = document.getElementById("hist-range");
  var clearButton = document.getElementById("hist-clear");
  var tabs = document.querySelectorAll('[role="tab"][data-tab]');

  var PAGE_SIZE = 15;
  var state = {
    page: 0,
    total: 0,
    items: [],
    loaded: false,
    listRequest: 0,
    roomRequest: 0,
    statusKey: "",
    statusError: false
  };

  function locale() {
    return window.UniSpaceI18n.current() === "ro" ? "ro-RO" : "en-GB";
  }

  // "Fri 18 Dec" from a date the backend sent (YYYY-MM-DD).
  function formatDay(iso) {
    var parts = iso.split("-");
    var day = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
    return new Intl.DateTimeFormat(locale(), { weekday: "short", day: "numeric", month: "short" }).format(day);
  }

  // True when the booking has not started yet (local time).
  function notStarted(item) {
    var parts = item.specific_date.split("-");
    var clock = item.start_time.split(":");
    var start = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]), Number(clock[0]), Number(clock[1]));
    return start > new Date();
  }

  function setStatus(key, isError) {
    state.statusKey = key || "";
    state.statusError = Boolean(isError);
    statusLine.hidden = !key;
    statusLine.textContent = key ? t(key) : "";
    statusLine.className = state.statusError ? "notice notice--error" : "notice";
  }

  function cell() {
    return document.createElement("td");
  }

  function placeholderOption(text) {
    var option = document.createElement("option");
    option.value = "";
    option.textContent = text;
    return option;
  }

  // The faculties, then "Campus" for rooms with no faculty. Keeps the choice that is on screen.
  function loadFaculties() {
    var chosen = facultySelect.value;
    return api.faculties().then(function (faculties) {
      facultySelect.textContent = "";
      facultySelect.appendChild(placeholderOption(t("adminHistory.allFaculties")));
      var campus = document.createElement("option");
      campus.value = "campus";
      campus.textContent = t("common.campus");
      facultySelect.appendChild(campus);
      faculties.forEach(function (faculty) {
        var option = document.createElement("option");
        option.value = faculty.id;
        option.textContent = faculty.name;
        facultySelect.appendChild(option);
      });
      facultySelect.value = chosen;
    }).catch(function () {
      setStatus("adminHistory.loadError", true);
    });
  }

  // The rooms of the chosen faculty, or every room when no faculty is chosen.
  function loadRooms() {
    var request = ++state.roomRequest;
    var chosen = roomSelect.value;
    return api.classrooms(facultySelect.value || undefined).then(function (rooms) {
      if (request !== state.roomRequest) return;
      roomSelect.textContent = "";
      roomSelect.appendChild(placeholderOption(t("adminHistory.allRooms")));
      rooms.forEach(function (room) {
        var option = document.createElement("option");
        option.value = room.id;
        option.textContent = room.name;
        roomSelect.appendChild(option);
      });
      roomSelect.value = chosen;
    }).catch(function () {
      if (request !== state.roomRequest) return;
      setStatus("adminHistory.loadError", true);
    });
  }

  function row(item) {
    var tr = document.createElement("tr");
    tr.className = "row";

    var when = cell();
    when.textContent = formatDay(item.specific_date) + " · " + item.start_time + "–" + item.end_time;
    tr.appendChild(when);

    var room = cell();
    room.textContent = item.classroom_name + " (" + (item.faculty_name || t("common.campus")) + ")";
    tr.appendChild(room);

    var title = cell();
    title.textContent = item.title;
    tr.appendChild(title);

    var requester = cell();
    requester.textContent = item.user_email;
    requester.appendChild(document.createElement("br"));
    var role = document.createElement("span");
    role.className = "pill";
    role.textContent = t("role." + item.user_role);
    requester.appendChild(role);
    tr.appendChild(requester);

    var info = statuses.statusInfo(item.status);
    var stateCell = cell();
    var pill = document.createElement("span");
    pill.className = info.pill;
    pill.textContent = info.key ? t(info.key) : item.status;
    stateCell.appendChild(pill);
    tr.appendChild(stateCell);

    var actions = cell();
    if (item.status === "approved" && notStarted(item)) {
      var cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "btn btn-small";
      cancel.textContent = t("adminHistory.cancel");
      cancel.setAttribute("aria-label", t("adminHistory.cancelAria", { title: item.title }));
      cancel.addEventListener("click", function () {
        openConfirm(item, tr);
      });
      actions.appendChild(cancel);
    }
    tr.appendChild(actions);
    return tr;
  }

  function closeConfirm() {
    var open = body.querySelectorAll("tr.confirm");
    for (var i = 0; i < open.length; i++) body.removeChild(open[i]);
  }

  // The question under a row: is this cancellation meant? Nothing changes until the admin says yes.
  function openConfirm(item, tr) {
    closeConfirm();
    var panelRow = document.createElement("tr");
    panelRow.className = "confirm";
    var td = document.createElement("td");
    td.colSpan = 6;
    var question = document.createElement("p");
    var strong = document.createElement("strong");
    strong.textContent = t("adminHistory.confirmTitle", { title: item.title });
    question.appendChild(strong);
    question.appendChild(document.createElement("br"));
    question.appendChild(document.createTextNode(t("adminHistory.confirmText", {
      room: item.classroom_name,
      when: formatDay(item.specific_date) + " · " + item.start_time
    })));
    td.appendChild(question);

    // The cancellation is a rejection: an optional message to the requester, as on the pending requests.
    var field = document.createElement("div");
    field.className = "field";
    var label = document.createElement("label");
    label.setAttribute("for", "hist-cancel-" + item.id);
    label.textContent = t("adminHistory.messageLabel");
    field.appendChild(label);
    var box = document.createElement("textarea");
    box.id = "hist-cancel-" + item.id;
    box.maxLength = 100;
    box.placeholder = t("admin.messagePlaceholder");
    field.appendChild(box);
    var hint = document.createElement("span");
    hint.className = "muted";
    hint.textContent = t("adminHistory.messageHint");
    field.appendChild(hint);
    td.appendChild(field);

    var group = document.createElement("div");
    group.className = "btn-group";
    var yes = document.createElement("button");
    yes.type = "button";
    yes.className = "btn btn-primary btn-small";
    yes.textContent = t("adminHistory.confirmYes");
    yes.addEventListener("click", function () {
      var message = box.value.trim();
      cancelBooking(item, message ? { message: message } : {});
    });
    var keep = document.createElement("button");
    keep.type = "button";
    keep.className = "btn btn-small";
    keep.textContent = t("adminHistory.keep");
    keep.addEventListener("click", closeConfirm);
    group.appendChild(yes);
    group.appendChild(keep);
    td.appendChild(group);

    panelRow.appendChild(td);
    tr.parentNode.insertBefore(panelRow, tr.nextSibling);
  }

  function cancelBooking(item, body) {
    api.adminCancelBooking(item.id, body).then(function () {
      closeConfirm();
      return load();
    }).then(function () {
      setStatus("adminHistory.cancelled");
    }).catch(function (error) {
      closeConfirm();
      setStatus(error.status === 409 ? "adminHistory.cancelRefused" : "admin.errorGeneric", true);
    });
  }

  function draw() {
    body.textContent = "";
    state.items.forEach(function (item) {
      body.appendChild(row(item));
    });
    emptyCard.hidden = state.total > 0;
    pager.hidden = state.total === 0;
    if (state.total > 0) {
      var from = state.page * PAGE_SIZE + 1;
      var to = Math.min((state.page + 1) * PAGE_SIZE, state.total);
      rangeLabel.textContent = t("adminHistory.range", { from: from, to: to, total: state.total });
    } else {
      rangeLabel.textContent = "";
    }
    prevButton.disabled = state.page === 0;
    nextButton.disabled = (state.page + 1) * PAGE_SIZE >= state.total;
  }

  // One page of bookings, for the filters on screen.
  function load() {
    var request = ++state.listRequest;
    var params = { limit: PAGE_SIZE, offset: state.page * PAGE_SIZE };
    if (facultySelect.value) params.faculty_id = facultySelect.value;
    if (roomSelect.value) params.classroom_id = roomSelect.value;
    if (statusSelect.value) params.status = statusSelect.value;
    return api.adminBookings(params).then(function (answer) {
      if (request !== state.listRequest) return;
      state.items = answer.items;
      state.total = answer.total;
      draw();
      if (state.statusError) setStatus("");
    }).catch(function () {
      if (request !== state.listRequest) return;
      state.items = [];
      state.total = 0;
      draw();
      setStatus("adminHistory.loadError", true);
    });
  }

  // A filter changed: the first page of the new list.
  function filtersChanged() {
    state.page = 0;
    load();
  }

  function showTab(name) {
    tabs.forEach(function (tab) {
      tab.setAttribute("aria-selected", String(tab.getAttribute("data-tab") === name));
    });
    document.getElementById("panel-pending").hidden = name !== "pending";
    document.getElementById("panel-rooms").hidden = name !== "rooms";
    panel.hidden = name !== "history";
    if (name === "history" && !state.loaded) {
      state.loaded = true;
      loadFaculties();
      loadRooms();
      load();
    }
  }

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      showTab(tab.getAttribute("data-tab"));
    });
  });

  facultySelect.addEventListener("change", function () {
    roomSelect.value = "";
    loadRooms();
    filtersChanged();
  });
  roomSelect.addEventListener("change", filtersChanged);
  statusSelect.addEventListener("change", filtersChanged);
  prevButton.addEventListener("click", function () {
    state.page -= 1;
    load();
  });
  nextButton.addEventListener("click", function () {
    state.page += 1;
    load();
  });
  clearButton.addEventListener("click", function () {
    facultySelect.value = "";
    roomSelect.value = "";
    statusSelect.value = "";
    loadRooms();
    filtersChanged();
  });

  // Everything built by the script is translated again when the language changes; the choices stay.
  document.addEventListener("unispace:langchange", function () {
    if (!state.loaded) return;
    loadFaculties();
    loadRooms();
    draw();
    setStatus(state.statusKey, state.statusError);
  });
})();
