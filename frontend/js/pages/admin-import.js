/*
 * Admin: the Data import tab (D-031, C-012). A button starts the import of the timetable and the
 * professors on the server; the tab then asks for its state every 3 seconds until it ends, and
 * shows the counts, what could not be imported and the clashes to resolve.
 * Room names and titles are shown as they arrive (D-012); the words around them are translated.
 */
(() => {
  var t = window.UniSpaceI18n.t;
  var api = window.UniSpaceApi;
  var POLL_MS = 3000;

  var tab = document.querySelector('[role="tab"][data-tab="import"]');
  var startButton = /** @type {HTMLButtonElement} */ (
    document.getElementById("imp-start")
  );
  var statusLine = document.getElementById("imp-status");
  var resultBox = document.getElementById("imp-result");
  var counts = document.getElementById("imp-counts");
  var problemsBlock = document.getElementById("imp-problems-block");
  var problems = document.getElementById("imp-problems");
  var noClashes = document.getElementById("imp-no-clashes");
  var clashesWrap = document.getElementById("imp-clashes-wrap");
  var clashes = document.getElementById("imp-clashes");

  // Literal keys, so the key check reads them.
  var STEPS = {
    faculties: "admin.import.stepFaculties",
    planning_units: "admin.import.stepPlanningUnits",
    schedules: "admin.import.stepSchedules",
    timetable: "admin.import.stepTimetable",
    professors: "admin.import.stepProfessors",
    clashes: "admin.import.stepClashes",
  };
  var COUNTS = {
    inserted: "admin.import.inserted",
    updated: "admin.import.updated",
    unchanged: "admin.import.unchanged",
    restored: "admin.import.restored",
    cancelled: "admin.import.cancelled",
    kept_edited: "admin.import.keptEdited",
    unread_entries: "admin.import.unread",
  };
  var PROBLEMS = {
    planning: "admin.import.problemPlanning",
    download: "admin.import.problemDownload",
    empty: "admin.import.problemEmpty",
    load: "admin.import.problemLoad",
    professors: "admin.import.problemProfessors",
    professors_save: "admin.import.problemProfessorsSave",
  };
  var KINDS = {
    booking: "admin.import.whatBooking",
    class: "admin.import.whatClass",
    exam: "admin.import.whatExam",
  };
  var REASONS = {
    room: "admin.import.reasonRoom",
    professor: "admin.import.reasonProfessor",
    group: "admin.import.reasonGroup",
  };

  var current = null; // the last state the server answered
  var errorKey = "";
  var request = 0;
  var timer = 0;

  function element(tag, text) {
    var node = document.createElement(tag);
    node.textContent = text;
    return node;
  }

  function statusText() {
    if (errorKey) return t(errorKey);
    if (current.status === "running")
      return t("admin.import.running", {
        step: t(STEPS[current.step] || STEPS.faculties),
      });
    if (current.status === "failed")
      return t("admin.import.failed", {
        step: t(STEPS[current.step] || STEPS.faculties),
      });
    if (current.status === "done")
      return t("admin.import.done", {
        time: new Date(current.finished_at).toLocaleString(
          window.UniSpaceI18n.current(),
        ),
      });
    return "";
  }

  function renderResult(result) {
    counts.textContent = "";
    Object.keys(COUNTS).forEach((name) => {
      counts.appendChild(
        element("li", t(COUNTS[name], { n: result.schedule[name] })),
      );
    });
    counts.appendChild(
      element(
        "li",
        t("admin.import.professorsSaved", { n: result.professors.stored }),
      ),
    );

    problems.textContent = "";
    result.problems.forEach((problem) => {
      problems.appendChild(
        element(
          "li",
          t(PROBLEMS[problem.kind], { faculty: problem.faculty || "" }),
        ),
      );
    });
    problemsBlock.hidden = result.problems.length === 0;

    clashes.textContent = "";
    result.clashes.forEach((clash) => {
      var row = document.createElement("tr");
      [
        clash.date + " " + clash.start + "–" + clash.end,
        clash.room,
        t(KINDS[clash.what]) + ": " + clash.title,
        clash.class_room + ", " + clash.class_start + "–" + clash.class_end,
        clash.reasons.map((reason) => t(REASONS[reason])).join(", "),
      ].forEach((text) => {
        row.appendChild(element("td", text));
      });
      clashes.appendChild(row);
    });
    clashesWrap.hidden = result.clashes.length === 0;
    noClashes.hidden = result.clashes.length !== 0;
  }

  function render() {
    var text = statusText();
    var failed = Boolean(errorKey) || current?.status === "failed";
    statusLine.hidden = !text;
    statusLine.textContent = text;
    statusLine.className = failed ? "notice notice--error mt-3" : "notice mt-3";
    startButton.disabled = current?.status === "running";
    resultBox.hidden = !current?.result;
    if (current?.result) renderResult(current.result);
  }

  function later() {
    window.clearTimeout(timer);
    timer = window.setTimeout(load, POLL_MS);
  }

  function load() {
    var mine = ++request;
    window.clearTimeout(timer);
    return api
      .dataImport()
      .then((state) => {
        if (mine !== request) return;
        current = state;
        errorKey = "";
        render();
        if (state.status === "running") later();
      })
      .catch(() => {
        if (mine !== request) return;
        errorKey = "admin.import.stateError";
        render();
        if (current?.status === "running") later();
      });
  }

  function start() {
    startButton.disabled = true;
    return api
      .startDataImport()
      .then(load)
      .catch((error) => {
        if (error.status === 409) return load(); // one is already running: follow it
        errorKey = "admin.import.startError";
        render();
      });
  }

  tab.addEventListener("click", load);
  startButton.addEventListener("click", start);
  document.addEventListener("unispace:langchange", () => {
    if (current || errorKey) render();
  });
})();
