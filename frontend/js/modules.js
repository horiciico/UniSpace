/*
 * The university's module schedule, shared by the timetable grid and the free-rooms page.
 * Eight modules of 90 minutes, each followed by a 10-minute break: 08:00-09:30, 09:40-11:10,
 * ... 19:40-21:10. A room is booked for whole modules, and nothing is booked after 21:10.
 * The backend has the same table (backend/app/planning.py, MODULES).
 *
 * The academic calendar (D-027) changes the grid. On a date in an EXAM_SESSION period a room is
 * booked by whole hours from 08:00 to 22:00 (`hours`); on a HOLIDAY no room is booked; any other
 * date, also one no period covers, uses the modules. The helpers below read the periods of
 * GET /api/academic-periods ([{ type, name, start_date, end_date }], dates "YYYY-MM-DD").
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

  // The exam-session grid: fourteen hours, 08:00-09:00 ... 21:00-22:00.
  var HOURS_END = 22 * 60;
  var hours = [];
  for (let start = FIRST_START; start < HOURS_END; start += 60) {
    hours.push({
      number: hours.length + 1,
      startMin: start,
      endMin: start + 60,
      start: clock(start),
      end: clock(start + 60),
    });
  }

  function addDays(iso, days) {
    var date = new Date(iso + "T00:00:00Z");
    date.setUTCDate(date.getUTCDate() + days);
    return date.toISOString().slice(0, 10);
  }

  // The type of the period that covers the date; TEACHING when none does.
  function typeOnDate(periods, iso) {
    for (let index = 0; index < periods.length; index++) {
      const period = periods[index];
      if (period.start_date <= iso && iso <= period.end_date)
        return period.type;
    }
    return "TEACHING";
  }

  // How a week (Monday to Sunday) is drawn. The whole week is hourly when any day is in an
  // exam session; otherwise "HOLIDAY" when any day is a holiday; otherwise "TEACHING".
  // days: the type of each day, Monday first.
  function weekInfo(periods, mondayIso) {
    var days = [];
    for (let offset = 0; offset < 7; offset++) {
      days.push(typeOnDate(periods, addDays(mondayIso, offset)));
    }
    var type = "TEACHING";
    if (days.indexOf("EXAM_SESSION") !== -1) type = "EXAM_SESSION";
    else if (days.indexOf("HOLIDAY") !== -1) type = "HOLIDAY";
    return { type: type, hourly: type === "EXAM_SESSION", days: days };
  }

  // The first exam session that has not ended by the date (periods come ordered by start), or null.
  function nextExamSession(periods, todayIso) {
    for (let index = 0; index < periods.length; index++) {
      const period = periods[index];
      if (period.type === "EXAM_SESSION" && period.end_date >= todayIso)
        return period;
    }
    return null;
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
