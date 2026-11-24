/*
 * Rezervări (room bookings) page. A signed-in user asks for a room: faculty, room (only the rooms
 * that can be booked), date, a module range and a title. The backend decides: it checks the
 * clashes and the dates, and answers 201, 400, 404 or 409. The list shows the user's own requests,
 * upcoming first, and a pending one can be cancelled. The link from the timetable or Free Now
 * fills the form in (see js/bookings.js for the link). Names and times from the backend are shown
 * as they arrive (D-012); the words around them come from the dictionaries.
 */
(function () {
  "use strict";

  var t = window.UniSpaceI18n.t;
  var api = window.UniSpaceApi;
  var modules = window.UniSpaceModules;
  var bookings = window.UniSpaceBookings;

  var list = document.getElementById("bk-list");
  if (!list) return;
  var mineStatus = document.getElementById("bk-mine-status");
  var facultySelect = document.getElementById("bk-faculty");
  var roomSelect = document.getElementById("bk-room");
  var roomNote = document.getElementById("bk-room-note");
  var dateInput = document.getElementById("bk-date");
  var fromSelect = document.getElementById("bk-from");
  var toSelect = document.getElementById("bk-to");
  var titleInput = document.getElementById("bk-title");
  var formStatus = document.getElementById("bk-form-status");
  var sendButton = document.getElementById("bk-send");
  var form = document.getElementById("bk-form");
  var prefillNote = document.getElementById("bk-prefill-note");
  var adminNote = document.getElementById("bk-admin-note");

  var prefill = bookings.readPrefill(window.location.search);
  var state = {
    user: null,
    mineKey: "", mineError: false,
    formKey: "", formError: false,
    facultyRequest: 0,
    roomRequest: 0
  };

  function pad(value) {
    return String(value).padStart(2, "0");
  }

  function todayIso() {
    var now = new Date();
    return now.getFullYear() + "-" + pad(now.getMonth() + 1) + "-" + pad(now.getDate());
  }

  function locale() {
    return window.UniSpaceI18n.current() === "ro" ? "ro-RO" : "en-GB";
  }

  function formatDate(iso) {
    var parts = iso.split("-");
    var day = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
    return new Intl.DateTimeFormat(locale(), { weekday: "short", day: "numeric", month: "short" }).format(day);
  }

  function setMineStatus(key, isError) {
    state.mineKey = key || "";
    state.mineError = Boolean(isError);
    mineStatus.textContent = key ? t(key) : "";
    mineStatus.className = state.mineError ? "notice notice--error" : "muted";
  }

  function setFormStatus(key, isError) {
    state.formKey = key || "";
    state.formError = Boolean(isError);
    formStatus.hidden = !key;
    formStatus.textContent = key ? t(key) : "";
    formStatus.className = state.formError ? "notice notice--error" : "notice";
  }

  // The index of the module whose start (or end) is this clock time, or -1.
  function moduleIndex(clock, field) {
    for (var index = 0; index < modules.list.length; index++) {
      if (modules.list[index][field] === clock) return index;
    }
    return -1;
  }

  // Fills the two module pickers, each option reads "1 · 08:00–09:30".
  function fillModules(fromIndex, toIndex) {
    [fromSelect, toSelect].forEach(function (select) {
      select.textContent = "";
      modules.list.forEach(function (module, index) {
        var option = document.createElement("option");
        option.value = String(index);
        option.textContent = module.number + " · " + module.start + "–" + module.end;
        select.appendChild(option);
      });
    });
    fromSelect.value = String(fromIndex);
    toSelect.value = String(toIndex);
  }

  function placeholder(text) {
    var option = document.createElement("option");
    option.value = "";
    option.textContent = text;
    return option;
  }

  // The faculties, then "Campus" for rooms with no faculty. Keeps the choice that is on screen.
  function loadFaculties() {
    var chosen = facultySelect.value || prefill.faculty_id;
    return api.faculties().then(function (faculties) {
      facultySelect.textContent = "";
      facultySelect.appendChild(placeholder(t("bookings.chooseFaculty")));
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
      setFormStatus("bookings.loadError", true);
    });
  }

  // The rooms of the chosen faculty that can be booked. Keeps the room on screen if it is still listed.
  function loadRooms() {
    var request = ++state.roomRequest;
    var wanted = roomSelect.value || prefill.room;
    roomSelect.textContent = "";
    roomSelect.appendChild(placeholder(t("bookings.chooseRoom")));
    roomSelect.disabled = !facultySelect.value;
    roomNote.textContent = t("bookings.onlyBookable");
    if (!facultySelect.value) return Promise.resolve();
    return api.classrooms(facultySelect.value).then(function (rows) {
      if (request !== state.roomRequest) return;
      var bookable = rows.filter(function (row) { return row.is_bookable; });
      bookable.forEach(function (room) {
        var option = document.createElement("option");
        option.value = room.id;
        option.textContent = room.name;
        roomSelect.appendChild(option);
      });
      roomSelect.value = wanted;
      if (!bookable.length) roomNote.textContent = t("bookings.noRooms");
    }).catch(function () {
      if (request !== state.roomRequest) return;
      setFormStatus("bookings.loadError", true);
    });
  }

  // One request of the signed-in user, as a list row.
  function row(booking) {
    var item = document.createElement("li");
    var text = document.createElement("span");
    var title = document.createElement("strong");
    title.textContent = booking.title;
    text.appendChild(title);
    text.appendChild(document.createElement("br"));
    var meta = document.createElement("span");
    meta.className = "muted booking-meta";
    meta.textContent = booking.room_name + " · " + (booking.faculty_name || t("common.campus")) + " · " +
      formatDate(booking.specific_date) + " · " + booking.start_time + "–" + booking.end_time;
    text.appendChild(meta);
    // The administrator's message on a decided request (issue #23): shown only when there is one.
    if (booking.decision_message) {
      text.appendChild(document.createElement("br"));
      var note = document.createElement("span");
      note.className = "muted decision-note";
      note.textContent = t("bookings.decisionNote", { message: booking.decision_message });
      text.appendChild(note);
    }
    item.appendChild(text);

    var actions = document.createElement("span");
    actions.className = "btn-group";
    var info = bookings.statusInfo(booking.status);
    var pill = document.createElement("span");
    pill.className = info.pill;
    pill.textContent = info.key ? t(info.key) : booking.status;
    actions.appendChild(pill);
    if (bookings.canCancel(booking)) {
      var cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "btn btn-small";
      cancel.textContent = t("bookings.cancel");
      cancel.setAttribute("aria-label", t("bookings.cancelAria", { title: booking.title }));
      cancel.addEventListener("click", function () {
        cancelRequest(booking.id);
      });
      actions.appendChild(cancel);
    }
    item.appendChild(actions);
    return item;
  }

  function loadMine() {
    setMineStatus("bookings.loading");
    return api.myBookings().then(function (rows) {
      list.textContent = "";
      rows.forEach(function (booking) {
        list.appendChild(row(booking));
      });
      setMineStatus(rows.length ? "" : "bookings.emptyMine");
    }).catch(function () {
      list.textContent = "";
      setMineStatus("bookings.loadError", true);
    });
  }

  function cancelRequest(id) {
    api.cancelBooking(id).then(function () {
      setMineStatus("bookings.cancelled");
      return loadMine();
    }).catch(function (error) {
      setMineStatus(error.status === 409 ? "bookings.errorCancelState" : "bookings.errorGeneric", true);
    });
  }

  // The error the backend's status stands for, in words the user can act on.
  function errorKey(status) {
    if (status === 409) return "bookings.errorClash";
    if (status === 400) return "bookings.errorInvalid";
    if (status === 404) return "bookings.errorRoom";
    return "bookings.errorGeneric";
  }

  function send(event) {
    event.preventDefault();
    var from = Number(fromSelect.value);
    var to = Number(toSelect.value);
    if (!roomSelect.value) return setFormStatus("bookings.errorNoRoom", true);
    if (!dateInput.value) return setFormStatus("bookings.errorNoDate", true);
    if (!titleInput.value.trim()) return setFormStatus("bookings.errorNoTitle", true);
    if (to < from) return setFormStatus("bookings.errorRange", true);

    sendButton.disabled = true;
    api.createBooking({
      classroom_id: roomSelect.value,
      specific_date: dateInput.value,
      start_time: modules.list[from].start,
      end_time: modules.list[to].end,
      title: titleInput.value.trim()
    }).then(function () {
      sendButton.disabled = false;
      titleInput.value = "";
      setFormStatus(state.user && state.user.role === "ADMIN" ? "bookings.sentApproved" : "bookings.sentPending");
      return loadMine();
    }).catch(function (error) {
      sendButton.disabled = false;
      setFormStatus(errorKey(error.status), true);
    });
  }

  // The link may have filled the form in: say so, and set the date and the modules it gave.
  function applyPrefill() {
    var given = prefill.faculty_id || prefill.room || prefill.date || prefill.start || prefill.end;
    prefillNote.hidden = !given;
    dateInput.value = prefill.date || todayIso();
    fillModules(
      prefill.start ? Math.max(moduleIndex(prefill.start, "start"), 0) : 0,
      prefill.end ? Math.max(moduleIndex(prefill.end, "end"), 0) : 0
    );
  }

  function init() {
    dateInput.min = todayIso();
    applyPrefill();
    facultySelect.addEventListener("change", function () {
      // A new faculty starts with no room chosen; the room from the link applies only once.
      prefill.room = "";
      roomSelect.value = "";
      loadRooms();
    });
    form.addEventListener("submit", send);
    window.UniSpaceAuth.ready.then(function (user) {
      state.user = user;
      adminNote.hidden = !(user && user.role === "ADMIN");
    });
    loadFaculties().then(loadRooms).then(loadMine);
  }

  // Everything built by the script is translated again when the language changes; the
  // choices on screen stay as they are.
  document.addEventListener("unispace:langchange", function () {
    var from = Number(fromSelect.value);
    var to = Number(toSelect.value);
    fillModules(from, to);
    setFormStatus(state.formKey, state.formError);
    setMineStatus(state.mineKey, state.mineError);
    loadFaculties().then(loadRooms).then(loadMine);
  });

  init();
})();
