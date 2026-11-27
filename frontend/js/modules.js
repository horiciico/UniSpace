/*
 * The university's module schedule, shared by the timetable grid and the free-rooms page.
 * Eight modules of 90 minutes, each followed by a 10-minute break: 08:00-09:30, 09:40-11:10,
 * ... 19:40-21:10. A room is booked for whole modules, and nothing is booked after 21:10.
 * The backend has the same table (backend/app/planning.py, MODULES).
 *
 * The academic calendar (D-028) changes the grid. On a date in an EXAM_SESSION period a room is
 * booked in half-hour steps from 08:00 to 22:00, at least one hour (`hours`, D-030); on a HOLIDAY no room is booked; any other
 * date, also one no period covers, uses the modules. The helpers below read the periods of
 * GET /api/academic-periods ([{ type, name, start_date, end_date, faculty_id }], dates
 * "YYYY-MM-DD"). A period is of one faculty or, with no faculty_id, of all of them (D-028): a
 * faculty's own period wins over an all-faculties one.
 */
(() => {
  var FIRST_START = 8 * 60;
  var COUNT = 8;
  var LENGTH = 90;
  var PERIOD = 100;

  function clock(minutes) {
    return (
      String(Math.floor(minutes / 60)).padStart(2, "0") +
      ":" +
      String(minutes % 60).padStart(2, "0")
    );
  }

  var list = [];
  for (let index = 0; index < COUNT; index++) {
    const start = FIRST_START + index * PERIOD;
    list.push({
      number: index + 1,
      startMin: start,
      endMin: start + LENGTH,
      start: clock(start),
      end: clock(start + LENGTH),
    });
  }

  // The exam-session grid: 28 half hours, 08:00-08:30 ... 21:30-22:00.
  var HOURS_END = 22 * 60;
  var STEP = 30;
  var hours = [];
  for (let start = FIRST_START; start < HOURS_END; start += STEP) {
    hours.push({
      number: hours.length + 1,
      startMin: start,
      endMin: start + STEP,
      start: clock(start),
      end: clock(start + STEP),
    });
  }

  function addDays(iso, days) {
    var date = new Date(iso + "T00:00:00Z");
    date.setUTCDate(date.getUTCDate() + days);
    return date.toISOString().slice(0, 10);
  }

  // The type that counts for the faculty on the date: its own period's, else the all-faculties
  // period's, else TEACHING. With no faculty (or "campus") only all-faculties periods count.
  function typeOnDate(periods, iso, facultyId) {
    var shared = "";
    for (let index = 0; index < periods.length; index++) {
      const period = periods[index];
      if (period.start_date > iso || iso > period.end_date) continue;
      if (!period.faculty_id) shared = period.type;
      else if (period.faculty_id === facultyId) return period.type;
    }
    return shared || "TEACHING";
  }

  // How a faculty's week (Monday to Sunday) is drawn. The whole week is hourly when any day is in
  // an exam session; otherwise "HOLIDAY" when any day is a holiday; otherwise "TEACHING".
  // days: the type of each day, Monday first.
  function weekInfo(periods, mondayIso, facultyId) {
    var days = [];
    for (let offset = 0; offset < 7; offset++) {
      days.push(typeOnDate(periods, addDays(mondayIso, offset), facultyId));
    }
    var type = "TEACHING";
    if (days.indexOf("EXAM_SESSION") !== -1) type = "EXAM_SESSION";
    else if (days.indexOf("HOLIDAY") !== -1) type = "HOLIDAY";
    return { type: type, hourly: type === "EXAM_SESSION", days: days };
  }

  // The first day of a period that is an exam session for one of the faculties, or "" when their
  // own periods override all of it.
  function firstExamDay(periods, period, ids) {
    for (
      let day = period.start_date;
      day <= period.end_date;
      day = addDays(day, 1)
    ) {
      if (ids.some((id) => typeOnDate(periods, day, id) === "EXAM_SESSION"))
        return day;
    }
    return "";
  }

  // The first exam session of the faculties that has not ended by the date, or null. Its
  // start_date is the first day that really is a session for one of them.
  function nextExamSession(periods, todayIso, facultyIds) {
    var ids = facultyIds && facultyIds.length ? facultyIds : [""];
    var next = null;
    periods.forEach((period) => {
      if (period.type !== "EXAM_SESSION" || period.end_date < todayIso) return;
      if (period.faculty_id && ids.indexOf(period.faculty_id) === -1) return;
      const day = firstExamDay(periods, period, ids);
      if (day && (!next || day < next.start_date))
        next = Object.assign({}, period, { start_date: day });
    });
    return next;
  }

  window.UniSpaceModules = {
    hours: hours,
    hoursEndMin: HOURS_END,
    typeOnDate: typeOnDate,
    weekInfo: weekInfo,
    nextExamSession: nextExamSession,
    // The bookable slots of a day of this type: hours in an exam session, modules otherwise.
    slotsFor: (type) => (type === "EXAM_SESSION" ? hours : list),
    list: list,
    clock: clock,
    // The booking day ends with the last module: no room can be booked after this time.
    endMin: list[list.length - 1].endMin,
    end: clock(list[list.length - 1].endMin),
  };
})();
