/*
 * Admin: the booking requests waiting for a decision (issue #23, C-006). Each request shows who asked,
 * their role, the request and the room and time. Accept books the room; Reject opens a box for an
 * optional message the requester will see. The backend decides: it refuses a clash (409) and a request
 * already decided (409). Names and times from the backend are shown as they arrive (D-012).
 */
(function () {
  "use strict";

  var t = window.UniSpaceI18n.t;
  var api = window.UniSpaceApi;

  var queue = document.getElementById("bk-admin-queue");
  if (!queue) return;
  var statusLine = document.getElementById("bk-admin-status");
  var emptyCard = document.getElementById("bk-admin-empty");

  var MESSAGE_LIMIT = 100;
  var state = { requests: [], statusKey: "", statusError: false, busy: false };

  function locale() {
    return window.UniSpaceI18n.current() === "ro" ? "ro-RO" : "en-GB";
  }

  // "Mon 14 Dec", from the date the backend sent (YYYY-MM-DD).
  function formatDay(iso) {
    var parts = iso.split("-");
    var day = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
    return new Intl.DateTimeFormat(locale(), { weekday: "short", day: "numeric", month: "short" }).format(day);
  }

  function formatRequested(stamp) {
    return new Intl.DateTimeFormat(locale(), { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })
      .format(new Date(stamp));
  }

  function setStatus(key, isError) {
    state.statusKey = key || "";
    state.statusError = Boolean(isError);
    statusLine.hidden = !key;
    statusLine.textContent = key ? t(key) : "";
    statusLine.className = state.statusError ? "notice notice--error" : "notice";
  }

  function cell() {
    return document.createElement("td");
  }

  function button(label, className, onClick) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = className;
    b.textContent = label;
    b.addEventListener("click", onClick);
    return b;
  }

  // The request's row: requester, request, room and time, and the two decisions.
  function requestRow(request) {
    var row = document.createElement("tr");
    row.className = "request";

    var who = cell();
    var name = document.createElement("strong");
    name.textContent = request.requester.name;
    who.appendChild(name);
    who.appendChild(document.createElement("br"));
    var email = document.createElement("span");
    email.className = "muted requester";
    email.textContent = request.requester.email;
    who.appendChild(email);
    who.appendChild(document.createElement("br"));
    var role = document.createElement("span");
    role.className = "pill";
    role.textContent = t("role." + request.requester.role);
    who.appendChild(role);
    row.appendChild(who);

    var asked = cell();
    asked.textContent = request.title;
    asked.appendChild(document.createElement("br"));
    var when = document.createElement("span");
    when.className = "muted requester";
    when.textContent = t("admin.requested", { when: formatRequested(request.created_at) });
    asked.appendChild(when);
    row.appendChild(asked);

    var room = cell();
    room.textContent = request.room_name + (request.faculty_name ? " · " + request.faculty_name : "");
    room.appendChild(document.createElement("br"));
    var slot = document.createElement("span");
    slot.className = "muted requester";
    slot.textContent = formatDay(request.specific_date) + " · " + request.start_time + "–" + request.end_time;
    room.appendChild(slot);
    row.appendChild(room);

    var actions = cell();
    var group = document.createElement("div");
    group.className = "btn-group";
    group.appendChild(button(t("admin.accept"), "btn btn-primary btn-small", function () {
      decide(request, { decision: "approve" });
    }));
    group.appendChild(button(t("admin.reject"), "btn btn-small", function () {
      openReject(request, row);
    }));
    actions.appendChild(group);
    row.appendChild(actions);
    return row;
  }

  // The box under a request that is being rejected: an optional message, then the decision.
  function openReject(request, row) {
    closeRejects();
    var panel = document.createElement("tr");
    panel.className = "decide";
    var td = document.createElement("td");
    td.colSpan = 4;

    var field = document.createElement("div");
    field.className = "field";
    var label = document.createElement("label");
    label.setAttribute("for", "bk-reject-" + request.id);
    label.textContent = t("admin.messageLabel", { name: request.requester.name });
    field.appendChild(label);
    var box = document.createElement("textarea");
    box.id = "bk-reject-" + request.id;
    box.maxLength = MESSAGE_LIMIT;
    box.setAttribute("data-i18n-attr", "placeholder:admin.messagePlaceholder");
    box.placeholder = t("admin.messagePlaceholder");
    field.appendChild(box);
    var hint = document.createElement("span");
    hint.className = "muted";
    hint.textContent = t("admin.messageHint", { name: request.requester.name });
    field.appendChild(hint);
    td.appendChild(field);

    var group = document.createElement("div");
    group.className = "btn-group mt-3";
    group.appendChild(button(t("admin.rejectConfirm"), "btn btn-primary", function () {
      var message = box.value.trim();
      var body = { decision: "reject" };
      if (message) body.message = message;
      decide(request, body);
    }));
    group.appendChild(button(t("admin.cancel"), "btn", closeRejects));
    td.appendChild(group);

    panel.appendChild(td);
    row.parentNode.insertBefore(panel, row.nextSibling);
    box.focus();
  }

  function closeRejects() {
    var panels = queue.querySelectorAll("tr.decide");
    for (var i = 0; i < panels.length; i++) queue.removeChild(panels[i]);
  }

  function draw() {
    queue.textContent = "";
    state.requests.forEach(function (request) {
      queue.appendChild(requestRow(request));
    });
    emptyCard.hidden = state.requests.length > 0;
  }

  function load() {
    return api.pendingBookings().then(function (requests) {
      state.requests = requests;
      draw();
    }).catch(function () {
      state.requests = [];
      draw();
      setStatus("admin.loadError", true);
    });
  }

  // The backend's answer to a decision, in words the administrator can act on.
  function errorKey(status) {
    return status === 409 ? "admin.errorClash" : "admin.errorGeneric";
  }

  function decide(request, body) {
    if (state.busy) return;
    state.busy = true;
    var accepted = body.decision === "approve";
    api.decideBooking(request.id, body).then(function () {
      state.busy = false;
      state.requests = state.requests.filter(function (item) { return item.id !== request.id; });
      draw();
      setStatus(accepted ? "admin.accepted" : "admin.rejected");
    }).catch(function (error) {
      state.busy = false;
      setStatus(errorKey(error.status), true);
    });
  }

  // Everything built by the script is translated again when the language changes.
  document.addEventListener("unispace:langchange", function () {
    draw();
    setStatus(state.statusKey, state.statusError);
  });

  load();
})();
