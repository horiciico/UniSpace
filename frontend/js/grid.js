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
 * In an exam session (D-028) the grid runs to 22:00 instead: 84 rows, the time column shows one
 * range per half hour, and the day lines fall at each half hour (render option hourly, D-030).
 *
 * Text comes from the backend as it arrives (D-012). Labels are from the i18n dictionaries.
 */
(() => {
  var MODULES = window.UniSpaceModules;
  var FIRST_MINUTE = MODULES.list[0].startMin; // 08:00
  var SLOT_MINUTES = 10;

  // The rows of the grid: modules to 21:10 (79 rows), or hours to 22:00 (84 rows).
  function layoutFor(hourly) {
    var lastMinute = hourly ? MODULES.hoursEndMin : MODULES.endMin;
    return {
      lastMinute: lastMinute,
      slotCount: (lastMinute - FIRST_MINUTE) / SLOT_MINUTES,
      slots: hourly ? MODULES.hours : MODULES.list,
    };
  }
  var DAY_KEYS = [
    "day.mon",
    "day.tue",
    "day.wed",
    "day.thu",
    "day.fri",
    "day.sat",
    "day.sun",
  ];
  var KIND_KEYS = {
    COURSE: "kind.course",
    SEMINAR: "kind.seminar",
    LAB: "kind.lab",
    EXAM: "kind.exam",
    RESERVATION: "kind.reservation",
    BOOKING: "kind.booking",
  };
  var KIND_CLASS = {
    COURSE: "course",
    SEMINAR: "seminar",
    LAB: "lab",
    BOOKING: "booking",
  };

  function toMinutes(hhmm) {
    var parts = String(hhmm).split(":");
    return Number(parts[0]) * 60 + Number(parts[1]);
  }

  function element(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  // Places items that overlap in time side by side. Returns the entries with lane/lanes set.
  function layoutDay(entries) {
    var sorted = entries
      .slice()
      .sort((a, b) => a.startMin - b.startMin || a.endMin - b.endMin);
    var placed = [];
    var cluster = [];
    var clusterEnd = 0;

    function closeCluster() {
      var laneEnds = [];
      cluster.forEach((entry) => {
        var lane = 0;
        while (lane < laneEnds.length && laneEnds[lane] > entry.startMin)
          lane++;
        laneEnds[lane] = entry.endMin;
        entry.lane = lane;
      });
      cluster.forEach((entry) => {
        entry.lanes = laneEnds.length;
        placed.push(entry);
      });
      cluster = [];
    }

    sorted.forEach((entry) => {
      if (cluster.length && entry.startMin >= clusterEnd) closeCluster();
      clusterEnd = cluster.length
        ? Math.max(clusterEnd, entry.endMin)
        : entry.endMin;
      cluster.push(entry);
    });
    if (cluster.length) closeCluster();
    return placed;
  }

  function percentOf(minutes, layout) {
    return ((minutes - FIRST_MINUTE) / (layout.slotCount * SLOT_MINUTES)) * 100;
  }

  function placeBlock(block, entry, layout) {
    var top = percentOf(entry.startMin, layout);
    var height = percentOf(entry.endMin, layout) - top;
    var share = 100 / entry.lanes;
    block.style.top = "calc(" + top + "% + 1px)";
    block.style.height = "calc(" + height + "% - 2px)";
    block.style.left = "calc(" + entry.lane * share + "% + 2px)";
    block.style.width = "calc(" + share + "% - 4px)";
  }

  /**
   * Draws the week. items: [{ day_of_week (1 Mon .. 7 Sun), start_time "HH:MM", end_time,
   * activity_type, title, room_name, ... }]. Times outside 08:00-21:10 are left
   * out of the grid. onSelect(item) runs when a block is clicked.
   * freeSlots (optional): [{ day_of_week, startMin, endMin, label, ariaLabel, disabled, onClick }]
   * are drawn as dashed buttons under the blocks (a free module that can be booked).
   * options.hourly: draw the exam-session grid (hours, 08:00-22:00) instead of the modules.
   * options.holidays (optional): one boolean per day, Monday first; those days are marked.
   */
  function render(container, items, onSelect, freeSlots, options) {
    var t = window.UniSpaceI18n.t;
    var hourly = Boolean(options && options.hourly);
    var layout = layoutFor(hourly);
    container.textContent = "";
    container.classList.toggle("tt-grid--hourly", hourly);

    container.appendChild(element("div", "tt-corner", t("timetable.time")));
    DAY_KEYS.forEach((key, index) => {
      var head = element("div", "tt-head", t(key));
      head.style.gridColumn = String(index + 2);
      head.style.gridRow = "1";
      container.appendChild(head);
    });

    layout.slots.forEach((module) => {
      var label = element("div", "tt-time", module.start + "–" + module.end);
      label.style.gridColumn = "1";
      label.style.gridRow =
        (module.startMin - FIRST_MINUTE) / SLOT_MINUTES +
        2 +
        " / span " +
        (module.endMin - module.startMin) / SLOT_MINUTES;
      container.appendChild(label);
    });

    var columns = [];
    for (let day = 0; day < DAY_KEYS.length; day++) {
      const column = element("div", "tt-day");
      column.style.gridColumn = String(day + 2);
      column.style.gridRow = "2 / " + (layout.slotCount + 2);
      container.appendChild(column);
      columns.push({ element: column, entries: [] });
      if (options && options.holidays && options.holidays[day]) {
        column.appendChild(
          element("span", "tt-off", t("timetable.periodHolidayPill")),
        );
      }
    }

    (freeSlots || []).forEach((slot) => {
      // A free slot is blank until it is hovered or focused, when its label appears (see timetable.css).
      // A past slot is blank and cannot be clicked.
      var button = element("button", "tt-free");
      button.type = "button";
      button.disabled = Boolean(slot.disabled);
      if (slot.disabled) {
        button.classList.add("tt-free--past");
      } else {
        const plus = element("span", "tt-free__plus", "+");
        plus.setAttribute("aria-hidden", "true");
        button.appendChild(plus);
        button.appendChild(element("span", "tt-free__label", slot.label));
      }
      if (slot.ariaLabel) button.setAttribute("aria-label", slot.ariaLabel);
      placeBlock(
        button,
        {
          startMin: slot.startMin,
          endMin: slot.endMin,
          lane: 0,
          lanes: 1,
        },
        layout,
      );
      button.addEventListener("click", slot.onClick);
      columns[slot.day_of_week - 1].element.appendChild(button);
    });

    items.forEach((item) => {
      var dayIndex = Number(item.day_of_week) - 1;
      if (dayIndex < 0 || dayIndex >= columns.length) return;
      var startMin = Math.max(toMinutes(item.start_time), FIRST_MINUTE);
      var endMin = Math.min(toMinutes(item.end_time), layout.lastMinute);
      if (endMin <= startMin) return;
      columns[dayIndex].entries.push({
        item: item,
        startMin: startMin,
        endMin: endMin,
      });
    });

    columns.forEach((column) => {
      layoutDay(column.entries).forEach((entry) => {
        var item = entry.item;
        var kindClass = KIND_CLASS[item.activity_type] || "other";
        var block = element("button", "tt-block tt-block--" + kindClass);
        block.type = "button";
        block.setAttribute("data-kind", item.activity_type);
        block.appendChild(element("strong", null, item.title));
        var kind = KIND_KEYS[item.activity_type]
          ? t(KIND_KEYS[item.activity_type])
          : item.activity_type;
        block.appendChild(element("span", null, kind + " · " + item.room_name));
        block.appendChild(
          element("span", null, item.start_time + "–" + item.end_time),
        );
        placeBlock(block, entry, layout);
        block.addEventListener("click", () => {
          if (onSelect) onSelect(item);
        });
        column.element.appendChild(block);
      });
    });

    return container;
  }

  window.UniSpaceGrid = { render: render, toMinutes: toMinutes };
})();
