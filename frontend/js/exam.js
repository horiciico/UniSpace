/*
 * Schedule Exam: the dialog where a professor schedules an exam from "Orarul meu" (D-030, C-011).
 * Subject, its groups (one or more), a date and half-hour times (08:00 to 22:00, at least one hour).
 * Every change asks the server (C-011) whether the date is in those groups' exam session, whether
 * the professor and the groups are free, and which rooms are free; only then can it be sent.
 *
 * UniSpaceExam.open(onDone) opens the dialog. Subjects, groups, rooms and the reasons from the
 * backend are shown as they arrive (D-012). Labels come from the i18n dictionaries.
 */
(() => {
  var dialog = /** @type {HTMLDialogElement} */ (
    document.getElementById("ex-dialog")
  );
  if (!dialog) return; // a page without the dialog has nothing to do here
  var t = window.UniSpaceI18n.t;
  var api = window.UniSpaceApi;

  var DAY_START = 8 * 60;
  var DAY_END = 22 * 60;
  var STEP = 30;
  var SHORTEST = 60;

  var subjects = [];
  var onDoneCallback = null;
  var checkRequest = 0;

  // Typed loosely: the dialog's controls are inputs, selects and buttons, read as they are used.
  /** @param {string} id @returns {any} */
  function $(id) {
    return document.getElementById(id);
  }

  function clock(minutes) {
    return (
      String(Math.floor(minutes / 60)).padStart(2, "0") +
      ":" +
      String(minutes % 60).padStart(2, "0")
    );
  }

  function todayIso() {
    var now = new Date();
    return (
      now.getFullYear() +
      "-" +
      String(now.getMonth() + 1).padStart(2, "0") +
      "-" +
      String(now.getDate()).padStart(2, "0")
    );
  }

  function option(value, text) {
    var item = document.createElement("option");
    item.value = value;
    item.textContent = text;
    return item;
  }

  function showError(text) {
    $("ex-error-text").textContent = text;
    $("ex-error").hidden = !text;
  }

  // The half hours from first to last, in minutes, as options of the select.
  function fillTimes(select, first, last) {
    select.textContent = "";
    for (let minutes = first; minutes <= last; minutes += STEP) {
      select.appendChild(option(clock(minutes), clock(minutes)));
    }
  }

  function toMinutes(hhmm) {
    var parts = hhmm.split(":");
    return Number(parts[0]) * 60 + Number(parts[1]);
  }

  // The ends of the chosen start: at least an hour later. The chosen end stays when it still fits.
  function fillEnds() {
    var first = toMinutes($("ex-start").value) + SHORTEST;
    var wanted = $("ex-end").value;
    fillTimes($("ex-end"), first, DAY_END);
    if (wanted && toMinutes(wanted) >= first) $("ex-end").value = wanted;
  }

  function chosenGroups() {
    return Array.from($("ex-groups").querySelectorAll("input:checked")).map(
      (box) => /** @type {HTMLInputElement} */ (box).value,
    );
  }

  function groupBox(group) {
    var label = document.createElement("label");
    label.className = "check";
    var box = document.createElement("input");
    box.type = "checkbox";
    box.value = group.id;
    box.addEventListener("change", check);
    var name = document.createElement("span");
    name.textContent = group.name;
    label.append(box, name);
    return label;
  }

  function fillGroups() {
    var box = $("ex-groups");
    box.textContent = "";
    var subject = subjects[$("ex-subject").selectedIndex];
    if (!subject) return;
    subject.groups.forEach((group) => {
      box.appendChild(groupBox(group));
    });
  }

  function fillSubjects() {
    var select = $("ex-subject");
    select.textContent = "";
    subjects.forEach((subject) => {
      select.appendChild(option(subject.name, subject.name));
    });
    $("ex-empty").hidden = subjects.length > 0;
    fillGroups();
  }

  function setStatus(text) {
    $("ex-status").textContent = text;
  }

  function clearRooms() {
    $("ex-room").textContent = "";
    $("ex-submit").disabled = true;
  }

  function roomLabel(room) {
    return room.capacity === null || room.capacity === undefined
      ? room.name
      : room.name + " · " + t("timetable.moveSeats", { n: room.capacity });
  }

  // Why the answer does not allow the exam, or "" when it does.
  function refusal(answer) {
    if (!answer.exam_session) return t("exam.notInSession");
    if (!answer.available)
      return t("exam.busy", { reason: answer.conflict_reason });
    if (!answer.free_classrooms.length) return t("exam.noRoom");
    return "";
  }

  function showAnswer(answer) {
    var reason = refusal(answer);
    setStatus(reason || t("exam.free"));
    if (reason) return;
    answer.free_classrooms.forEach((room) => {
      $("ex-room").appendChild(option(room.id, roomLabel(room)));
    });
    $("ex-submit").disabled = false;
  }

  function check() {
    var request = ++checkRequest;
    var groups = chosenGroups();
    var date = $("ex-date").value;
    showError("");
    clearRooms();
    if (!groups.length || !date) return setStatus(t("exam.chooseFirst"));
    if (date < todayIso()) return setStatus(t("exam.past"));
    setStatus(t("timetable.loading"));
    api
      .professorInterval(date, $("ex-start").value, $("ex-end").value, groups)
      .then((answer) => {
        if (request === checkRequest) showAnswer(answer);
      })
      .catch(() => {
        if (request !== checkRequest) return;
        setStatus("");
        showError(t("exam.checkError"));
      });
  }

  function close() {
    if (typeof dialog.close === "function") dialog.close();
    else dialog.removeAttribute("open");
  }

  function submit(event) {
    event.preventDefault();
    if ($("ex-submit").disabled) return;
    $("ex-submit").disabled = true;
    api
      .scheduleExam({
        subject_name: $("ex-subject").value,
        group_ids: chosenGroups(),
        exam_date: $("ex-date").value,
        start_time: $("ex-start").value,
        end_time: $("ex-end").value,
        classroom_id: $("ex-room").value,
      })
      .then(() => {
        close();
        window.UniSpaceUI.toast(t("exam.done"));
        if (onDoneCallback) onDoneCallback();
      })
      .catch((error) => {
        $("ex-submit").disabled = false;
        // The backend says why (a busy room, no exam session); it is shown as it arrives.
        var detail = error.body && error.body.detail;
        showError(
          t("exam.failed") + (typeof detail === "string" ? " " + detail : ""),
        );
      });
  }

  function open(onDone) {
    onDoneCallback = onDone;
    subjects = [];
    $("ex-form").reset();
    $("ex-date").min = todayIso();
    fillTimes($("ex-start"), DAY_START, DAY_END - SHORTEST);
    $("ex-end").textContent = "";
    fillEnds();
    $("ex-subject").textContent = "";
    $("ex-groups").textContent = "";
    $("ex-empty").hidden = true;
    check();
    api
      .professorSubjects()
      .then((data) => {
        subjects = data.subjects;
        fillSubjects();
      })
      .catch(() => {
        showError(t("exam.loadError"));
      });
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  }

  $("ex-subject").addEventListener("change", () => {
    fillGroups();
    check();
  });
  $("ex-date").addEventListener("change", check);
  $("ex-start").addEventListener("change", () => {
    fillEnds();
    check();
  });
  $("ex-end").addEventListener("change", check);
  $("ex-form").addEventListener("submit", submit);
  $("ex-cancel").addEventListener("click", close);

  // Text built by the script is translated again by closing: the next opening draws it fresh.
  document.addEventListener("unispace:langchange", () => {
    if (dialog.hasAttribute("open")) close();
  });

  window.UniSpaceExam = { open: open };
})();
