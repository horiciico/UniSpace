/*
 * Move Activity: the dialog where a professor moves one occurrence of an activity (D-026, C-009).
 * Four steps: the activity and its original date; the new date; a free module of that date (live from
 * /api/professors/me/availability, busy modules disabled with the reason); a bookable room free in that
 * module. Submit posts the move, shows a toast, closes, and calls onMoved so the timetable reloads.
 *
 * UniSpaceMove.open(onMoved) opens the dialog. Records and reasons from the backend are shown as they
 * arrive (D-012). Labels come from the i18n dictionaries.
 */
(() => {
  var dialog = /** @type {HTMLDialogElement} */ (
    document.getElementById("mv-dialog")
  );
  if (!dialog) return; // a page without the dialog has nothing to do here
  var t = window.UniSpaceI18n.t;
  var api = window.UniSpaceApi;

  var DAY_KEYS = [
    "day.mon",
    "day.tue",
    "day.wed",
    "day.thu",
    "day.fri",
    "day.sat",
    "day.sun",
  ];

  var activities = [];
  var current = null; // the activity chosen in step 1
  var originalDate = ""; // its original date (ISO)
  var newDate = ""; // the new date (ISO)
  var chosen = null; // the module chosen in step 3
  var onMovedCallback = null;
  var moduleRequest = 0;

  // Typed loosely: the dialog's controls are inputs, selects and buttons, read as they are used.
  /** @param {string} id @returns {any} */
  function $(id) {
    return document.getElementById(id);
  }

  function pad(value) {
    return String(value).padStart(2, "0");
  }

  function isoDate(date) {
    return (
      date.getFullYear() +
      "-" +
      pad(date.getMonth() + 1) +
      "-" +
      pad(date.getDate())
    );
  }

  function parseIso(text) {
    var parts = text.split("-");
    return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
  }

  // ISO weekday of a date: Monday = 1 (D-008).
  function weekdayOf(iso) {
    return ((parseIso(iso).getDay() + 6) % 7) + 1;
  }

  // The first date from today on that falls on the weekday (ISO, Monday = 1).
  function nextOnWeekday(dayOfWeek) {
    var date = new Date();
    while (((date.getDay() + 6) % 7) + 1 !== dayOfWeek) {
      date.setDate(date.getDate() + 1);
    }
    return isoDate(date);
  }

  function showStep(number) {
    for (let i = 1; i <= 4; i++) {
      $("mv-step-" + i).hidden = i !== number;
      let pill = $("mv-pill-" + i);
      pill.className = i === number ? "pill pill--info" : "pill";
      pill.setAttribute("aria-current", i === number ? "step" : "false");
    }
  }

  function showError(text) {
    $("mv-error-text").textContent = text;
    $("mv-error").hidden = !text;
  }

  function describe(activity) {
    return (
      activity.title +
      " · " +
      (activity.groups.join(", ") || "–") +
      " · " +
      t(DAY_KEYS[activity.day_of_week - 1]) +
      " " +
      activity.start_time +
      "–" +
      activity.end_time +
      " · " +
      activity.room_name
    );
  }

  // Step 1 default: the next date that falls on the activity's weekday, or its one-off date.
  function setOriginalDefault() {
    var activity = findActivity($("mv-activity").value);
    if (!activity) return;
    var date = activity.is_recurring
      ? nextOnWeekday(activity.day_of_week)
      : activity.specific_date;
    $("mv-original").value = date;
    $("mv-original").min = isoDate(new Date());
  }

  function findActivity(id) {
    for (let i = 0; i < activities.length; i++) {
      if (activities[i].id === id) return activities[i];
    }
    return null;
  }

  function fillActivities() {
    var select = $("mv-activity");
    select.textContent = "";
    activities.forEach((activity) => {
      var option = document.createElement("option");
      option.value = activity.id;
      option.textContent = describe(activity);
      select.appendChild(option);
    });
    $("mv-empty").hidden = activities.length > 0;
    $("mv-next-1").disabled = activities.length === 0;
    if (activities.length) setOriginalDefault();
  }

  function moduleButton(module) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-small mv-module";
    button.setAttribute("aria-pressed", "false");
    button.disabled = !module.available;
    var range = document.createElement("span");
    range.textContent = module.start_time + "–" + module.end_time;
    var state = document.createElement("small");
    state.textContent = module.available
      ? t("timetable.moveFree")
      : t("timetable.moveBusy") + ": " + module.conflict_reason;
    button.appendChild(range);
    button.appendChild(state);
    button.addEventListener("click", () => {
      chosen = module;
      document.querySelectorAll(".mv-module").forEach((other) => {
        other.setAttribute("aria-pressed", String(other === button));
      });
      $("mv-next-3").disabled = false;
    });
    return button;
  }

  function loadModules(day) {
    var request = ++moduleRequest;
    var box = $("mv-modules");
    box.textContent = "";
    chosen = null;
    $("mv-next-3").disabled = true;
    $("mv-module-status").textContent = t("timetable.loading");
    api
      .professorAvailability(day, current.group_ids, current.id)
      .then((data) => {
        if (request !== moduleRequest) return;
        $("mv-module-status").textContent = "";
        data.modules.forEach((module) => {
          box.appendChild(moduleButton(module));
        });
      })
      .catch(() => {
        if (request !== moduleRequest) return;
        $("mv-module-status").textContent = "";
        showError(t("timetable.moveModulesError"));
      });
  }

  // The free rooms of the module, and the faculty filter over them. A room with no faculty is
  // a campus room, keyed "campus" in the filter.
  var roomsOfModule = [];

  function facultyKey(room) {
    return room.faculty_id || "campus";
  }

  function option(value, text) {
    var item = document.createElement("option");
    item.value = value;
    item.textContent = text;
    return item;
  }

  function roomOption(room) {
    return option(
      room.id,
      room.capacity === null || room.capacity === undefined
        ? room.name
        : room.name + " · " + t("timetable.moveSeats", { n: room.capacity }),
    );
  }

  // One entry per faculty that owns a free room, in the order the rooms arrive.
  function fillFaculties(rooms) {
    var select = $("mv-faculty");
    select.textContent = "";
    select.appendChild(option("", t("timetable.moveAllFaculties")));
    var seen = {};
    rooms.forEach((room) => {
      var key = facultyKey(room);
      if (seen[key]) return;
      seen[key] = true;
      select.appendChild(
        option(key, room.faculty_id ? room.faculty_name : t("common.campus")),
      );
    });
    select.value = "";
  }

  function renderRooms() {
    var chosen = $("mv-faculty").value;
    var shown = roomsOfModule.filter(
      (room) => chosen === "" || facultyKey(room) === chosen,
    );
    var select = $("mv-room");
    select.textContent = "";
    shown.forEach((room) => {
      select.appendChild(roomOption(room));
    });
    $("mv-noroom").hidden = shown.length > 0;
    $("mv-submit").disabled = shown.length === 0;
  }

  function fillRooms(rooms) {
    roomsOfModule = rooms;
    fillFaculties(rooms);
    renderRooms();
  }

  function toStep2() {
    var activity = findActivity($("mv-activity").value);
    var date = $("mv-original").value;
    if (!activity) return showError(t("timetable.moveNeedActivity"));
    if (!date) return showError(t("timetable.moveNeedDate"));
    if (weekdayOf(date) !== activity.day_of_week)
      return showError(t("timetable.moveDayMismatch"));
    current = activity;
    originalDate = date;
    showError("");
    $("mv-new").value = date;
    $("mv-new").min = isoDate(new Date());
    showStep(2);
  }

  function toStep3() {
    var date = $("mv-new").value;
    if (!date) return showError(t("timetable.moveNeedDate"));
    if (date < isoDate(new Date())) return showError(t("timetable.movePast"));
    newDate = date;
    showError("");
    showStep(3);
    loadModules(date);
  }

  function toStep4() {
    if (!chosen) return showError(t("timetable.moveNeedModule"));
    showError("");
    fillRooms(chosen.free_classrooms);
    showStep(4);
  }

  function submit() {
    var room = $("mv-room").value;
    if (!room) return showError(t("timetable.moveNeedRoom"));
    $("mv-submit").disabled = true;
    api
      .moveActivity(current.id, {
        original_date: originalDate,
        new_date: newDate,
        start_time: chosen.start_time,
        end_time: chosen.end_time,
        new_classroom_id: room,
      })
      .then(() => {
        $("mv-submit").disabled = false;
        dialog.close();
        window.UniSpaceUI.toast(t("timetable.moveDone"));
        if (onMovedCallback) onMovedCallback();
      })
      .catch((error) => {
        $("mv-submit").disabled = false;
        // The backend says why (a busy room, a bad date); it is shown as it arrives.
        var detail = error.body && error.body.detail;
        showError(
          t("timetable.moveFailed") +
            (typeof detail === "string" ? " " + detail : ""),
        );
      });
  }

  function open(onMoved) {
    onMovedCallback = onMoved;
    showError("");
    showStep(1);
    $("mv-activity").textContent = "";
    api
      .movableActivities()
      .then((data) => {
        activities = data.linked ? data.activities : [];
        fillActivities();
      })
      .catch(() => {
        activities = [];
        fillActivities();
        showError(t("timetable.error"));
      });
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  }

  $("mv-activity").addEventListener("change", setOriginalDefault);
  $("mv-next-1").addEventListener("click", toStep2);
  $("mv-back-2").addEventListener("click", () => showStep(1));
  $("mv-next-2").addEventListener("click", toStep3);
  $("mv-back-3").addEventListener("click", () => showStep(2));
  $("mv-next-3").addEventListener("click", toStep4);
  $("mv-back-4").addEventListener("click", () => showStep(3));
  $("mv-faculty").addEventListener("change", renderRooms);
  $("mv-submit").addEventListener("click", submit);
  $("mv-cancel").addEventListener("click", () => dialog.close());

  // Text built by the script is translated again by closing: the next opening draws it fresh.
  document.addEventListener("unispace:langchange", () => {
    if (dialog.open) dialog.close();
  });

  window.UniSpaceMove = { open: open };
})();
