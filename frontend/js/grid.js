/*
 * Weekly timetable grid (CSS Grid), drawn into an element with class .tt-grid.
 *
 * Columns: a time column, then Monday to Sunday. Rows: 10-minute slots from 08:00 to
 * 21:10, 79 rows in all. The university's modules are 90 minutes, with a 10-minute break:
 * 08:00-09:30, 09:40-11:10, ... 19:40-21:10 (eight modules, one every 100 minutes). The time
 * column shows each module's range, and the day lines fall at the start of each module. Each
 * day is one grid cell; the activities sit inside it at their start and height. Activities
 * that overlap in time (a subgroup, an optional course) share the day's width side by side
 * ("lanes"), so the grid keeps its shape.
 *
 * Text comes from the backend as it arrives (D-012). Labels are from the i18n dictionaries.
 */
(function () {
  "use strict";

  var FIRST_MINUTE = 8 * 60;
  var MODULE_COUNT = 8;
  var MODULE_LENGTH = 90;   // minutes of teaching
  var MODULE_PERIOD = 100;  // a module and the 10-minute break after it
  var LAST_MINUTE = FIRST_MINUTE + (MODULE_COUNT - 1) * MODULE_PERIOD + MODULE_LENGTH; // 21:10
  var SLOT_MINUTES = 10;
  var SLOT_COUNT = (LAST_MINUTE - FIRST_MINUTE) / SLOT_MINUTES; // 79
  var DAY_KEYS = ["day.mon", "day.tue", "day.wed", "day.thu", "day.fri", "day.sat", "day.sun"];
  var KIND_KEYS = {
    COURSE: "kind.course",
    SEMINAR: "kind.seminar",
    LAB: "kind.lab",
    EXAM: "kind.exam",
    RESERVATION: "kind.reservation"
  };
  var KIND_CLASS = { COURSE: "course", SEMINAR: "seminar", LAB: "lab" };

  function toMinutes(hhmm) {
    var parts = String(hhmm).split(":");
    return Number(parts[0]) * 60 + Number(parts[1]);
  }

  function clock(minutes) {
    return String(Math.floor(minutes / 60)).padStart(2, "0") + ":" + String(minutes % 60).padStart(2, "0");
  }

  function element(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  // Places items that overlap in time side by side. Returns the entries with lane/lanes set.
  function layoutDay(entries) {
    var sorted = entries.slice().sort(function (a, b) {
      return a.startMin - b.startMin || a.endMin - b.endMin;
    });
    var placed = [];
    var cluster = [];
    var clusterEnd = 0;

    function closeCluster() {
      var laneEnds = [];
      cluster.forEach(function (entry) {
        var lane = 0;
        while (lane < laneEnds.length && laneEnds[lane] > entry.startMin) lane++;
        laneEnds[lane] = entry.endMin;
        entry.lane = lane;
      });
      cluster.forEach(function (entry) {
        entry.lanes = laneEnds.length;
        placed.push(entry);
      });
      cluster = [];
    }

    sorted.forEach(function (entry) {
      if (cluster.length && entry.startMin >= clusterEnd) closeCluster();
      clusterEnd = cluster.length ? Math.max(clusterEnd, entry.endMin) : entry.endMin;
      cluster.push(entry);
    });
    if (cluster.length) closeCluster();
    return placed;
  }

  function percentOf(minutes) {
    return (minutes - FIRST_MINUTE) / (SLOT_COUNT * SLOT_MINUTES) * 100;
  }

  function placeBlock(block, entry) {
    var top = percentOf(entry.startMin);
    var height = percentOf(entry.endMin) - top;
    var share = 100 / entry.lanes;
    block.style.top = "calc(" + top + "% + 1px)";
    block.style.height = "calc(" + height + "% - 2px)";
    block.style.left = "calc(" + (entry.lane * share) + "% + 2px)";
    block.style.width = "calc(" + share + "% - 4px)";
  }

  /**
   * Draws the week. items: [{ day_of_week (1 Mon .. 7 Sun), start_time "HH:MM", end_time,
   * activity_type, title, room_name, ... }]. Times outside 08:00-21:10 are left
   * out of the grid. onSelect(item) runs when a block is clicked.
   */
  function render(container, items, onSelect) {
    var t = window.UniSpaceI18n.t;
    container.textContent = "";

    container.appendChild(element("div", "tt-corner", t("timetable.time")));
    DAY_KEYS.forEach(function (key, index) {
      var head = element("div", "tt-head", t(key));
      head.style.gridColumn = String(index + 2);
      head.style.gridRow = "1";
      container.appendChild(head);
    });

    for (var module = 0; module < MODULE_COUNT; module++) {
      var start = FIRST_MINUTE + module * MODULE_PERIOD;
      var label = element("div", "tt-time", clock(start) + "–" + clock(start + MODULE_LENGTH));
      label.style.gridColumn = "1";
      label.style.gridRow = ((start - FIRST_MINUTE) / SLOT_MINUTES + 2) + " / span " + (MODULE_LENGTH / SLOT_MINUTES);
      container.appendChild(label);
    }

    var columns = [];
    for (var day = 0; day < DAY_KEYS.length; day++) {
      var column = element("div", "tt-day");
      column.style.gridColumn = String(day + 2);
      column.style.gridRow = "2 / " + (SLOT_COUNT + 2);
      container.appendChild(column);
      columns.push({ element: column, entries: [] });
    }

    items.forEach(function (item) {
      var dayIndex = Number(item.day_of_week) - 1;
      if (dayIndex < 0 || dayIndex >= columns.length) return;
      var startMin = Math.max(toMinutes(item.start_time), FIRST_MINUTE);
      var endMin = Math.min(toMinutes(item.end_time), LAST_MINUTE);
      if (endMin <= startMin) return;
      columns[dayIndex].entries.push({ item: item, startMin: startMin, endMin: endMin });
    });

    columns.forEach(function (column) {
      layoutDay(column.entries).forEach(function (entry) {
        var item = entry.item;
        var kindClass = KIND_CLASS[item.activity_type] || "other";
        var block = element("button", "tt-block tt-block--" + kindClass);
        block.type = "button";
        block.setAttribute("data-kind", item.activity_type);
        block.appendChild(element("strong", null, item.title));
        var kind = KIND_KEYS[item.activity_type] ? t(KIND_KEYS[item.activity_type]) : item.activity_type;
        block.appendChild(element("span", null, kind + " · " + item.room_name));
        block.appendChild(element("span", null, item.start_time + "–" + item.end_time));
        placeBlock(block, entry);
        block.addEventListener("click", function () {
          if (onSelect) onSelect(item);
        });
        column.element.appendChild(block);
      });
    });

    return container;
  }

  window.UniSpaceGrid = { render: render, toMinutes: toMinutes };
})();
