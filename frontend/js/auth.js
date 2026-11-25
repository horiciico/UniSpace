/*
 * Session for the browser. The real check is on the server: nginx asks the backend
 * (GET /auth/me) before it serves any page, so a signed-out visitor never gets one.
 * This script only learns who is signed in, for the header and the greeting, and
 * sends the person to /login if the session ended while the page was open.
 *
 * UniSpaceAuth.ready  promise: the user ({ id, email, name, role }) or null when signed out
 * UniSpaceAuth.user() the user once ready, else null
 * UniSpaceAuth.roleLabel(role), UniSpaceAuth.isAdmin(), UniSpaceAuth.logout()
 */
(() => {
  var current = null;

  function onLoginPage() {
    var path = window.location.pathname
      .replace(/\.html$/, "")
      .replace(/\/+$/, "");
    return path === "/login";
  }

  // 401 means signed out. Anything else that is not a user (server down) shows no user
  // and leaves the page as it is: the server already decided this visitor may see it.
  var ready = fetch("/auth/me", { credentials: "same-origin" })
    .then((response) => {
      if (response.status === 401) return null;
      if (!response.ok)
        throw new Error("Unexpected /auth/me status " + response.status);
      return response.json();
    })
    .then((user) => {
      current = user;
      if (!user && !onLoginPage()) {
        document.documentElement.style.display = "none";
        window.location.replace("/login");
      }
      return user;
    })
    .catch((error) => {
      console.error("Could not read the session:", error);
      return null;
    });

  window.UniSpaceAuth = {
    ready: ready,
    user: () => current,
    roleLabel: (role) => window.UniSpaceI18n.t("role." + role),
    isAdmin: () => !!current && current.role === "ADMIN",
    logout: () =>
      fetch("/auth/logout", { method: "POST", credentials: "same-origin" })
        .catch((error) => {
          console.error("Log out request failed:", error);
        })
        .then(() => {
          current = null;
          window.location.replace("/login");
        }),
  };
})();
