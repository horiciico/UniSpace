/*
 * Orar (timetable) page. The tabs choose what to show (group, professor or room), the
 * faculty narrows the list, and the entity input (with a datalist) picks one. The week comes
 * from /api/schedule and is drawn by grid.js. The selection is kept in the URL, so
 * /timetable?mode=room&faculty_id=...&id=... opens a room (from the free-rooms page).
 * Names and times from the backend are shown as they arrive (D-012).
 */
(() => {
  var t = window.UniSpaceI18n.t;
  var api = window.UniSpaceApi;
  var grid = window.UniSpaceGrid;

  var gridElement = document.getElementById("tt-grid");
  if (!gridElement) return;
  var body = document.getElementById("tt-body");
  var emptyNote = document.getElementById("tt-empty");
  var statusLine = document.getElementById("tt-status");
  var facultySelect = /** @type {HTMLSelectElement} */ (
    document.getElementById("tt-faculty")
  );
  var entityInput = /** @type {HTMLInputElement} */ (
    document.getElementById("tt-entity")
  );
  var entityLabel = document.getElementById("tt-entity-label");
  var entityList = document.getElementById("entity-list");
  var weekLabel = document.getElementById("tt-week-label");
  var dialog = /** @type {HTMLDialogElement} */ (
    document.getElementById("tt-dialog")
  );
  var tabs = document.querySelectorAll("[role='tab'][data-mode]");
  var bookHint = document.getElementById("tt-hint");
  var roomBox = document.getElementById("tt-room");
  var roomAccess = document.getElementById("tt-room-access");
  var mineTab = document.getElementById("tt-tab-mine");
  var facultyField = document.getElementById("tt-filter-faculty");
  var entityField = document.getElementById("tt-filter-entity");
  var unlinkedNote = document.getElementById("tt-unlinked");
  var moveBar = document.getElementById("tt-move-bar");
  var moveButton = /** @type {HTMLButtonElement} */ (
    document.getElementById("tt-move")
  );
  var examButton = document.getElementById("tt-exam");
  var periodNote = document.getElementById("tt-period");
  var periodPill = document.getElementById("tt-period-pill");
  var periodText = document.getElementById("tt-period-text");
  var periodMore = document.getElementById("tt-period-more");

  var ENTITY_LABEL_KEYS = {
    group: "timetable.entityGroup",
    professor: "timetable.entityProfessor",
    room: "timetable.entityRoom",
  };
  var PARITY_KEYS = {
    ALL: "timetable.parityAll",
    ODD: "timetable.parityOdd",
    EVEN: "timetable.parityEven",
  };
  var DAY_KEYS = [
    "day.mon",
    "day.tue",
    "day.wed",
    "day.thu",
    "day.fri",
    "day.sat",
    "day.sun",
  ];
  // The banner of a week that is not a teaching week (D-027): the pill, the pill class, the text
  // when every day has the type, and the text that names the days when only some do.
  var PERIOD_BANNERS = {
    EXAM_SESSION: {
      pill: "timetable.periodExamPill",
      pillClass: "pill pill--pending",
      text: "timetable.periodExamText",
      partText: "timetable.periodExamPartText",
      facultyText: "timetable.periodExamFaculty",
    },
    HOLIDAY: {
      pill: "timetable.periodHolidayPill",
      pillClass: "pill pill--busy",
      text: "timetable.periodHolidayText",
      partText: "timetable.periodHolidayPartText",
      facultyText: "timetable.periodHolidayFaculty",
    },
  };
  var KIND_KEYS = {
    COURSE: "kind.course",
    SEMINAR: "kind.seminar",
    LAB: "kind.lab",
    EXAM: "kind.exam",
    RESERVATION: "kind.reservation",
    BOOKING: "kind.booking",
  };

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
    monday: mondayOf(
      /^\d{4}-\d{2}-\d{2}$/.test(params.get("date") || "")
        ? parseIso(params.get("date"))
        : new Date(),
    ),
    week: null,
    // The academic periods (C-010). Empty until loaded, or when they cannot be: every week is then
    // a teaching week.
    periods: [],
    // The faculties of the professor's courses, for "Orarul meu" (C-009).
    mineFaculties: [],
    items: null,
    statusKey: "",
    statusError: false,
    requestNumber: 0,
    entityRequestNumber: 0,
    // "Orarul meu" (mode mine) is for professors only: the tab shows once the role is known,
    // and a link that asks for it opens it only for a professor (wantMine).
    wantMine: params.get("mode") === "mine",
    canMine: false,
    unlinked: false,
  };

  function setStatus(key, isError) {
    state.statusKey = key;
    state.statusError = Boolean(isError);
    statusLine.textContent = key ? t(key) : "";
    statusLine.className = state.statusError ? "notice notice--error" : "muted";
  }

  function renderWeek() {
    var sunday = addDays(state.monday, 6);
    var format = new Intl.DateTimeFormat(locale(), {
      day: "numeric",
      month: "short",
    });
    var range = format.format(state.monday) + " – " + format.format(sunday);
    if (state.week && state.week.number) {
      const parity = t(PARITY_KEYS[state.week.parity] || "timetable.parityAll");
      weekLabel.textContent =
        range +
        " · " +
        t("timetable.weekLabel", { n: state.week.number, parity: parity });
    } else {
      weekLabel.textContent = range;
    }
    renderPeriod();
  }

  // The faculties whose calendar the view follows (D-028): the professor's in "Orarul meu", the
  // room's in the room view, otherwise the selected one. "" is no faculty: only the periods of
  // all faculties count.
  function viewFaculties() {
    if (state.mode === "mine")
      return state.mineFaculties.length ? state.mineFaculties : [{ id: "" }];
    if (state.mode === "room" && state.entity)
      return [{ id: state.entity.facultyId || "" }];
    return [{ id: state.facultyId }];
  }

  // The week for each of those faculties, and what the grid shows: hourly when any of them is in
  // an exam session; a day has a type only when all of them agree on it.
  function weekInfo() {
    var weeks = viewFaculties().map((faculty) =>
      Object.assign(
        { name: faculty.name },
        window.UniSpaceModules.weekInfo(
          state.periods,
          isoDate(state.monday),
          faculty.id,
        ),
      ),
    );
    var days = weeks[0].days.map((type, index) =>
      weeks.every((week) => week.days[index] === type) ? type : "TEACHING",
    );
    return { weeks: weeks, days: days, hourly: weeks.some((w) => w.hourly) };
  }

  function dayNames(days, type) {
    return DAY_KEYS.filter((_, index) => days[index] === type)
      .map((key) => t(key))
      .join(", ");
  }

  // The banner lines. When the faculties share the week, one line as for a single faculty;
  // otherwise one line for each faculty and each type it has this week.
  function bannerLines(info) {
    var first = info.weeks[0];
    if (info.weeks.every((week) => week.days.join() === first.days.join())) {
      const banner = PERIOD_BANNERS[first.type];
      if (!banner) return [];
      const whole = first.days.every((type) => type === first.type);
      const text = whole
        ? t(banner.text)
        : t(banner.partText, { days: dayNames(first.days, first.type) });
      return [{ banner: banner, text: text }];
    }
    var lines = [];
    info.weeks.forEach((week) => {
      Object.keys(PERIOD_BANNERS).forEach((type) => {
        if (week.days.indexOf(type) === -1) return;
        const banner = PERIOD_BANNERS[type];
        lines.push({
          banner: banner,
          text: t(banner.facultyText, {
            faculty: week.name,
            days: dayNames(week.days, type),
          }),
        });
      });
    });
    return lines;
  }

  function extraLine(line) {
    var paragraph = document.createElement("p");
    paragraph.className = "m-0 mt-3";
    var pill = document.createElement("span");
    pill.className = line.banner.pillClass;
    pill.textContent = t(line.banner.pill);
    var text = document.createElement("span");
    text.textContent = line.text;
    paragraph.append(pill, " ", text);
    return paragraph;
  }

  function nextSession() {
    return window.UniSpaceModules.nextExamSession(
      state.periods,
      isoDate(new Date()),
      viewFaculties().map((faculty) => faculty.id),
    );
  }

  // The banner for an exam-session or holiday week, and the "Sesiune" jump while a current or
  // upcoming exam session exists.
  function renderPeriod() {
    var lines = bannerLines(weekInfo());
    periodNote.hidden = !lines.length;
    periodMore.textContent = "";
    if (lines.length) {
      periodPill.className = lines[0].banner.pillClass;
      periodPill.textContent = t(lines[0].banner.pill);
      periodText.textContent = lines[0].text;
      lines.slice(1).forEach((line) => {
        periodMore.appendChild(extraLine(line));
      });
    }
    examButton.hidden = !nextSession();
  }

  function renderEntityLabel() {
    if (state.mode === "mine") return; // the filters are hidden in this view
    entityLabel.textContent = t(ENTITY_LABEL_KEYS[state.mode]);
  }

  // The faculty and entity filters, and the move button, belong to the views that pick an entity
  // or to "Orarul meu" only. The unlinked notice shows in "Orarul meu" for an unlinked account.
  function renderMineControls() {
    var mine = state.mode === "mine";
    facultyField.hidden = mine;
    entityField.hidden = mine;
    moveBar.hidden = !mine;
    moveButton.disabled = state.unlinked;
    unlinkedNote.hidden = !(mine && state.unlinked);
  }

  function renderTabs() {
    tabs.forEach((tab) => {
      tab.setAttribute(
        "aria-selected",
        String(tab.getAttribute("data-mode") === state.mode),
      );
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
      const campus = document.createElement("option");
      campus.value = "campus";
      campus.textContent = t("common.campus");
      facultySelect.appendChild(campus);
    }
    state.faculties.forEach((faculty) => {
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

  // The room's description above the timetable: its access notes (admin-written, C-003). Room view only.
  function renderRoomDescription() {
    roomBox.hidden = state.mode !== "room";
    if (state.mode === "room")
      roomAccess.textContent =
        state.entity.accessNotes || t("rooms.unspecified");
  }

  function showBody() {
    emptyNote.hidden = true;
    body.hidden = false;
  }

  function fillEntityList() {
    entityList.textContent = "";
    state.entities.forEach((entity) => {
      var option = document.createElement("option");
      option.value = entity.name;
      entityList.appendChild(option);
    });
  }

  // Loads the groups, professors or rooms of the faculty into the datalist.
  function loadEntities() {
    if (state.mode === "mine") return Promise.resolve(); // nothing to pick in this view
    var request = ++state.entityRequestNumber;
    entityInput.disabled = !state.facultyId;
    // Drop the previous list at once, so the datalist never offers the old tab's names.
    state.entities = [];
    fillEntityList();
    if (!state.facultyId) return Promise.resolve();
    var source;
    if (state.mode === "group") {
      source = api
        .groups(state.facultyId)
        .then((rows) => rows.map((row) => ({ id: row.id, name: row.name })));
    } else if (state.mode === "professor") {
      source = api
        .professors(state.facultyId)
        .then((rows) => rows.map((row) => ({ id: row.name, name: row.name })));
    } else {
      // A room that cannot be booked stays in the list, but its free modules are not clickable.
      source = api.classrooms(state.facultyId).then((rows) =>
        rows.map((row) => ({
          id: row.id,
          name: row.name,
          bookable: row.is_bookable,
          facultyId: row.faculty_id,
          accessNotes: row.access_notes,
        })),
      );
    }
    return source
      .then((entities) => {
        if (request !== state.entityRequestNumber) return;
        state.entities = entities;
        fillEntityList();
      })
      .catch(() => {
        if (request !== state.entityRequestNumber) return;
        state.entities = [];
        fillEntityList();
        setStatus("timetable.error", true);
      });
  }

  function findEntity(name) {
    for (let i = 0; i < state.entities.length; i++) {
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
    // The faculty picks the planning unit to draw ("campus" is not a faculty id: none is sent).
    if (state.facultyId && state.facultyId !== "campus")
      values.faculty_id = state.facultyId;
    if (state.mode === "group") values.group_id = state.entity.id;
    else if (state.mode === "professor") values.professor = state.entity.name;
    else values.room_id = state.entity.id;
    return values;
  }

  // "Orarul meu": the signed-in professor's own week (C-009). An unlinked account gets the notice
  // and no grid; the move button stays disabled.
  function hideBody() {
    body.hidden = true;
    emptyNote.hidden = true;
  }

  function loadMine() {
    var request = ++state.requestNumber;
    setStatus("timetable.loading");
    api
      .professorTimetable(isoDate(state.monday))
      .then((data) => {
        if (request !== state.requestNumber) return;
        state.unlinked = !data.linked;
        state.mineFaculties = data.faculties || [];
        state.week = null;
        renderWeek();
        renderMineControls();
        if (!data.linked) {
          setStatus("");
          hideBody();
          return;
        }
        state.items = data.activities;
        setStatus(data.activities.length ? "" : "timetable.noItems");
        drawGrid();
        showBody();
      })
      .catch(() => {
        if (request !== state.requestNumber) return;
        state.items = null;
        renderWeek();
        setStatus("timetable.error", true);
        hideBody();
      });
  }

  function loadSchedule() {
    if (state.mode === "mine") return loadMine();
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
    api
      .schedule(scheduleParams())
      .then((data) => {
        if (request !== state.requestNumber) return;
        state.items = data.items;
        state.week = { number: data.week_number, parity: data.parity };
        renderWeek();
        setStatus(data.items.length ? "" : "timetable.noItems");
        drawGrid();
        renderRoomDescription();
        showBody();
      })
      .catch((error) => {
        if (request !== state.requestNumber) return;
        state.items = null;
        renderWeek();
        setStatus(
          error.status === 404 ? "timetable.notFound" : "timetable.error",
          true,
        );
        showEmpty();
      });
  }

  // The free slots of a bookable room, for each day of the week: the modules of a teaching day, or
  // the hours of an exam-session day (D-027), that no activity covers. The day decides, not the
  // week: a mixed week has both on its hourly grid. A slot that has started is shown but
  // disabled. A holiday has none. Each one opens the Bookings page.
  function freeSlots() {
    if (state.mode !== "room" || !state.entity || !state.entity.bookable)
      return [];
    var now = new Date();
    var slots = [];
    var info = weekInfo();
    DAY_KEYS.forEach((dayKey, dayIndex) => {
      if (info.days[dayIndex] === "HOLIDAY") return;
      var date = addDays(state.monday, dayIndex);
      var iso = isoDate(date);
      window.UniSpaceModules.slotsFor(info.days[dayIndex]).forEach((module) => {
        var taken = state.items.some(
          (item) =>
            Number(item.day_of_week) === dayIndex + 1 &&
            grid.toMinutes(item.start_time) < module.endMin &&
            grid.toMinutes(item.end_time) > module.startMin,
        );
        if (taken) return;
        var opens = new Date(
          date.getFullYear(),
          date.getMonth(),
          date.getDate(),
          Math.floor(module.startMin / 60),
          module.startMin % 60,
        );
        var range = module.start + "–" + module.end;
        slots.push({
          day_of_week: dayIndex + 1,
          startMin: module.startMin,
          endMin: module.endMin,
          disabled: opens <= now,
          label: t("bookings.bookSlotShort"),
          ariaLabel:
            opens <= now
              ? t("bookings.slotPast")
              : t("bookings.bookSlotAria", { range: range, day: t(dayKey) }),
          onClick: () => {
            window.location.assign(
              window.UniSpaceBookings.link({
                faculty_id: state.facultyId,
                room: state.entity.id,
                date: iso,
                start: module.start,
                end: module.end,
              }),
            );
          },
        });
      });
    });
    return slots;
  }

  // Callers draw only when there are items. The helper line shows for a bookable room only.
  function drawGrid() {
    var info = weekInfo();
    grid.render(gridElement, state.items, openDetails, freeSlots(), {
      hourly: info.hourly,
      holidays: info.days.map((type) => type === "HOLIDAY"),
    });
    bookHint.hidden = !(
      state.mode === "room" &&
      state.entity &&
      state.entity.bookable
    );
  }

  function openDetails(item) {
    var fill = (id, text) => {
      document.getElementById(id).textContent = text;
    };
    var kind = KIND_KEYS[item.activity_type]
      ? t(KIND_KEYS[item.activity_type])
      : item.activity_type;
    var day = new Intl.DateTimeFormat(locale(), {
      weekday: "long",
      day: "numeric",
      month: "long",
    }).format(parseIso(item.date));
    fill("tt-d-title", item.title);
    fill("tt-d-kind", kind);
    fill("tt-d-date", day);
    fill("tt-d-time", item.start_time + "–" + item.end_time);
    fill("tt-d-room", item.room_name);
    fill("tt-d-professor", item.professor || t("timetable.unknown"));
    fill(
      "tt-d-groups",
      item.groups && item.groups.length
        ? item.groups.join(", ")
        : t("timetable.unknown"),
    );
    // An approved room booking has no priority (C-005): it is not a timetable activity.
    fill(
      "tt-d-priority",
      item.priority === null ? t("timetable.unknown") : String(item.priority),
    );
    fill("tt-d-parity", t(PARITY_KEYS[item.parity] || "timetable.parityAll"));
    fill(
      "tt-d-recurring",
      item.is_recurring ? t("timetable.recurring") : t("timetable.oneOff"),
    );
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
    state.unlinked = false;
    renderTabs();
    renderEntityLabel();
    entityInput.value = "";
    state.entity = null;
    state.items = null;
    populateFaculties();
    updateUrl();
    renderMineControls();
    renderWeek(); // the view decides whose calendar the banner follows
    if (mode === "mine") {
      loadMine();
      return;
    }
    loadEntities();
    setStatus("");
    showEmpty();
  }

  // The "Orarul meu" tab is shown to a professor only. A link asking for it opens it then.
  function showMineTabIfProfessor() {
    if (!window.UniSpaceAuth) return;
    window.UniSpaceAuth.ready.then((user) => {
      if (!user || user.role !== "PROFESSOR") return;
      state.canMine = true;
      mineTab.hidden = false;
      if (state.wantMine) setMode("mine");
    });
  }

  // The academic periods decide the grid of each week. When they cannot be loaded every week is a
  // teaching week, as before.
  function loadPeriods() {
    return api
      .academicPeriods()
      .then((periods) => {
        state.periods = periods;
        renderWeek();
        if (state.items && !body.hidden) drawGrid();
      })
      .catch(() => {
        state.periods = [];
      });
  }

  function init() {
    renderTabs();
    renderEntityLabel();
    renderWeek();
    showEmpty();

    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        setMode(tab.getAttribute("data-mode"));
      });
    });

    facultySelect.addEventListener("change", () => {
      state.facultyId = facultySelect.value;
      entityInput.value = "";
      state.entity = null;
      updateUrl();
      loadEntities();
      loadSchedule();
    });

    entityInput.addEventListener("input", () => {
      onEntityChange(false);
    });
    entityInput.addEventListener("change", () => {
      onEntityChange(true);
    });

    document.getElementById("tt-prev").addEventListener("click", () => {
      state.monday = addDays(state.monday, -7);
      updateUrl();
      loadSchedule();
    });
    document.getElementById("tt-next").addEventListener("click", () => {
      state.monday = addDays(state.monday, 7);
      updateUrl();
      loadSchedule();
    });
    document.getElementById("tt-today").addEventListener("click", () => {
      state.monday = mondayOf(new Date());
      updateUrl();
      loadSchedule();
    });
    // The first week of the current or next exam session.
    examButton.addEventListener("click", () => {
      var session = nextSession();
      state.monday = mondayOf(parseIso(session.start_date));
      updateUrl();
      loadSchedule();
    });
    document.getElementById("tt-d-close").addEventListener("click", () => {
      dialog.close();
    });
    moveButton.addEventListener("click", () => {
      window.UniSpaceMove.open(() => {
        loadMine();
      });
    });
    showMineTabIfProfessor();
    loadPeriods();

    api
      .faculties()
      .then((faculties) => {
        state.faculties = faculties;
        populateFaculties();
        return loadEntities();
      })
      .then(() => {
        // Nothing to look the address up in: no faculty, no entity named, or no list loaded.
        if (!state.facultyId || !state.urlEntityId || !state.entities.length) {
          updateUrl();
          return;
        }
        var match = state.entities.filter(
          (entity) => entity.id === state.urlEntityId,
        )[0];
        if (match) {
          entityInput.value = match.name;
          chooseEntity(match);
        } else {
          setStatus("timetable.notFound", true);
        }
      })
      .catch(() => {
        setStatus("timetable.error", true);
      });
  }

  // Everything built by the script is translated again when the language changes.
  document.addEventListener("unispace:langchange", () => {
    renderTabs();
    renderEntityLabel();
    renderWeek();
    populateFaculties();
    fillEntityList();
    setStatus(state.statusKey, state.statusError);
    if (dialog.open) dialog.close();
    if (state.items && !body.hidden) {
      drawGrid();
      renderRoomDescription();
    }
  });

  init();
})();
