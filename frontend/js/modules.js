/*
 * The university's module schedule, shared by the timetable grid and the free-rooms page.
 * Eight modules of 90 minutes, each followed by a 10-minute break: 08:00-09:30, 09:40-11:10,
 * ... 19:40-21:10. A room is booked for whole modules, and nothing is booked after 21:10.
 * The backend has the same table (backend/app/planning.py, MODULES).
 */
(function () {
  "use strict";

  var FIRST_START = 8 * 60;
  var COUNT = 8;
  var LENGTH = 90;
  var PERIOD = 100;

  function clock(minutes) {
    return String(Math.floor(minutes / 60)).padStart(2, "0") + ":" + String(minutes % 60).padStart(2, "0");
  }

  var list = [];
  for (var index = 0; index < COUNT; index++) {
    var start = FIRST_START + index * PERIOD;
    list.push({
      number: index + 1,
      startMin: start,
      endMin: start + LENGTH,
      start: clock(start),
      end: clock(start + LENGTH)
    });
  }

  window.UniSpaceModules = {
    list: list,
    clock: clock,
    // The booking day ends with the last module: no room can be booked after this time.
    endMin: list[list.length - 1].endMin,
    end: clock(list[list.length - 1].endMin)
  };
})();
