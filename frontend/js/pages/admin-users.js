/*
 * Admin: the Users tab (C-008, D-025). Three parts: a card that invites an email with a non-admin
 * role (a 409 names an existing account), the pending invitations (copy the link, revoke), and the
 * users (filter by role, search by email, change a non-admin's role; an ADMIN row shows a badge).
 * The lists load when the tab is opened. The backend decides who may do each thing.
 */
(() => {
  var t = window.UniSpaceI18n.t;
  var api = window.UniSpaceApi;

  var PAGE_SIZE = 15;
  var SEARCH_PAUSE = 300;
  var NON_ADMIN_ROLES = ["STUDENT", "PROFESSOR", "STUDENT_ORG"];

  var tab = document.querySelector('[role="tab"][data-tab="users"]');
  var inviteForm = /** @type {HTMLFormElement} */ (
    document.getElementById("inv-form")
  );
  var inviteEmail = /** @type {HTMLInputElement} */ (
    document.getElementById("inv-email")
  );
  var inviteRole = /** @type {HTMLSelectElement} */ (
    document.getElementById("inv-role")
  );
  var inviteStatus = document.getElementById("inv-status");
  var copyWrap = document.getElementById("inv-copy-wrap");
  var copyButton = document.getElementById("inv-copy");
  var pendingStatus = document.getElementById("inv-list-status");
  var pendingBody = document.getElementById("inv-body");
  var pendingEmpty = document.getElementById("inv-empty");
  var roleFilter = /** @type {HTMLSelectElement} */ (
    document.getElementById("usr-role")
  );
  var searchInput = /** @type {HTMLInputElement} */ (
    document.getElementById("usr-search")
  );
  var usersStatus = document.getElementById("usr-status");
  var usersBody = document.getElementById("usr-body");
  var usersEmpty = document.getElementById("usr-empty");
  var pager = document.getElementById("usr-pager");
  var prevButton = /** @type {HTMLButtonElement} */ (
    document.getElementById("usr-prev")
  );
  var nextButton = /** @type {HTMLButtonElement} */ (
    document.getElementById("usr-next")
  );
  var rangeLabel = document.getElementById("usr-range");

  var state = {
    page: 0,
    total: 0,
    users: [],
    invitations: [],
    lastInviteUrl: "",
    searchTimer: null,
  };

  function setNotice(element, key, isError, vars) {
    element.hidden = false;
    element.textContent = t(key, vars);
    element.className = isError ? "notice notice--error" : "notice";
  }

  function hideNotice(element) {
    element.hidden = true;
    element.textContent = "";
  }

  function roleLabel(role) {
    return t(`role.${role}`);
  }

  function formatDate(iso) {
    var locale = window.UniSpaceI18n.current() === "ro" ? "ro-RO" : "en-GB";
    return new Date(iso).toLocaleString(locale, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  }

  function cell(text) {
    var td = document.createElement("td");
    td.textContent = text;
    return td;
  }

  function button(className, label, onClick) {
    var element = document.createElement("button");
    element.type = "button";
    element.className = className;
    element.textContent = label;
    element.addEventListener("click", onClick);
    return element;
  }

  // Copies the link with this site's address in front of it. The toast says how it went.
  function copyLink(path) {
    return navigator.clipboard
      .writeText(window.location.origin + path)
      .then(() => {
        window.UniSpaceUI.toast(t("usersPage.copied"));
      })
      .catch(() => {
        window.UniSpaceUI.toast(t("usersPage.copyFailed"));
      });
  }

  // ---- The users -------------------------------------------------------------

  function loadUsers() {
    return api
      .adminUsers({
        role: roleFilter.value,
        search: searchInput.value.trim(),
        limit: PAGE_SIZE,
        offset: state.page * PAGE_SIZE,
      })
      .then((data) => {
        state.total = data.total;
        state.users = data.items;
        hideNotice(usersStatus);
        renderUsers();
      })
      .catch(() => {
        setNotice(usersStatus, "usersPage.loadError", true);
      });
  }

  function groupLabel(user) {
    var parts = [user.faculty_name, user.study_formation_name].filter(Boolean);
    return parts.length ? parts.join(" · ") : t("usersPage.notSet");
  }

  // The role dropdown of a non-admin. A refused change puts back the role it had.
  function roleSelect(user) {
    var select = document.createElement("select");
    select.setAttribute(
      "aria-label",
      t("usersPage.roleAria", { email: user.email }),
    );
    var saved = user.role;
    NON_ADMIN_ROLES.forEach((role) => {
      var option = document.createElement("option");
      option.value = role;
      option.textContent = roleLabel(role);
      option.selected = role === saved;
      select.appendChild(option);
    });
    select.addEventListener("change", () => {
      var chosen = select.value;
      api
        .changeUserRole(user.id, chosen)
        .then(() => {
          saved = chosen;
          state.users = state.users.map((item) =>
            item.id === user.id
              ? Object.assign({}, item, { role: chosen })
              : item,
          );
          window.UniSpaceUI.toast(t("usersPage.roleSaved"));
        })
        .catch(() => {
          select.value = saved;
          window.UniSpaceUI.toast(t("usersPage.roleError"));
        });
    });
    return select;
  }

  function userRow(user) {
    var tr = document.createElement("tr");
    tr.appendChild(cell(user.email));
    tr.appendChild(cell(user.name));
    tr.appendChild(cell(groupLabel(user)));
    var role = document.createElement("td");
    if (user.role === "ADMIN") {
      const badge = document.createElement("span");
      badge.className = "pill";
      badge.textContent = roleLabel("ADMIN");
      role.appendChild(badge);
    } else {
      role.appendChild(roleSelect(user));
    }
    tr.appendChild(role);
    return tr;
  }

  function renderUsers() {
    usersBody.textContent = "";
    state.users.forEach((user) => {
      usersBody.appendChild(userRow(user));
    });
    usersEmpty.hidden = state.total > 0;
    pager.hidden = state.total === 0;
    var start = state.page * PAGE_SIZE;
    rangeLabel.textContent =
      state.total > 0
        ? t("adminHistory.range", {
            from: start + 1,
            to: start + state.users.length,
            total: state.total,
          })
        : "";
    prevButton.disabled = state.page === 0;
    nextButton.disabled = start + PAGE_SIZE >= state.total;
  }

  // ---- The invitations -------------------------------------------------------

  function loadInvitations() {
    return api
      .adminInvitations()
      .then((items) => {
        state.invitations = items;
        hideNotice(pendingStatus);
        renderInvitations();
      })
      .catch(() => {
        setNotice(pendingStatus, "usersPage.pendingLoadError", true);
      });
  }

  function revoke(invitation) {
    return api
      .revokeInvitation(invitation.id)
      .then(() => {
        window.UniSpaceUI.toast(t("usersPage.revoked"));
        return loadInvitations();
      })
      .catch(() => {
        window.UniSpaceUI.toast(t("usersPage.revokeError"));
      });
  }

  function invitationRow(invitation) {
    var tr = document.createElement("tr");
    tr.appendChild(cell(invitation.email));
    tr.appendChild(cell(roleLabel(invitation.role)));
    tr.appendChild(cell(formatDate(invitation.expires_at)));
    var actions = document.createElement("td");
    actions.appendChild(
      button("btn btn-secondary btn-small", t("usersPage.copyLinkShort"), () =>
        copyLink(invitation.invite_url),
      ),
    );
    var revokeButton = button("btn btn-small", t("usersPage.revoke"), () =>
      revoke(invitation),
    );
    revokeButton.setAttribute(
      "aria-label",
      t("usersPage.revokeAria", { email: invitation.email }),
    );
    actions.appendChild(revokeButton);
    tr.appendChild(actions);
    return tr;
  }

  function renderInvitations() {
    pendingBody.textContent = "";
    state.invitations.forEach((invitation) => {
      pendingBody.appendChild(invitationRow(invitation));
    });
    pendingEmpty.hidden = state.invitations.length > 0;
  }

  // ---- The invite card -------------------------------------------------------

  // 409 with a body that names the account: that person is already registered (D-025).
  // Any other 409 means an invitation for this email is already waiting.
  function inviteFailed(error) {
    copyWrap.hidden = true;
    if (error.status === 409 && error.body && error.body.existing_user) {
      const existing = error.body.existing_user;
      setNotice(inviteStatus, "usersPage.existing", true, {
        email: existing.email,
        role: roleLabel(existing.role),
      });
    } else if (error.status === 409) {
      setNotice(inviteStatus, "usersPage.pending", true);
    } else {
      setNotice(inviteStatus, "usersPage.inviteError", true);
    }
  }

  function sendInvitation() {
    return api
      .createInvitation({
        email: inviteEmail.value.trim(),
        role: inviteRole.value,
      })
      .then((created) => {
        state.lastInviteUrl = created.invite_url;
        inviteEmail.value = "";
        setNotice(inviteStatus, "usersPage.sent", false, {
          email: created.email,
        });
        copyWrap.hidden = false;
        return loadInvitations();
      })
      .catch(inviteFailed);
  }

  // ---- Wiring ----------------------------------------------------------------

  tab.addEventListener("click", () => {
    state.page = 0;
    loadUsers();
    loadInvitations();
  });
  inviteForm.addEventListener("submit", (event) => {
    event.preventDefault();
    sendInvitation();
  });
  copyButton.addEventListener("click", () => {
    copyLink(state.lastInviteUrl);
  });
  roleFilter.addEventListener("change", () => {
    state.page = 0;
    loadUsers();
  });
  // The search runs once the typing pauses, not on every key.
  searchInput.addEventListener("input", () => {
    clearTimeout(state.searchTimer);
    state.searchTimer = setTimeout(() => {
      state.page = 0;
      loadUsers();
    }, SEARCH_PAUSE);
  });
  prevButton.addEventListener("click", () => {
    state.page -= 1;
    loadUsers();
  });
  nextButton.addEventListener("click", () => {
    state.page += 1;
    loadUsers();
  });

  // The labels built by the script are drawn again in the new language.
  document.addEventListener("unispace:langchange", () => {
    renderUsers();
    renderInvitations();
  });
})();
