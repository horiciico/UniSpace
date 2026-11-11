# CONTEXT — UniSpace vocabulary

<!-- graffino-agentic:begin v1 -->
> The approved terms for this project. Use each term exactly as defined, in the part
> of speech given. Never swap in a synonym; never use a word on an _Avoid_ line.
<!-- graffino-agentic:end -->

**UniSpace** (noun) — the web platform this repository builds.
_Avoid_: "the app" when you mean the whole platform

**Backend** (noun) — the FastAPI service in `backend/`, which serves the API and talks to the database.
_Avoid_: "server", "API" when you mean the whole service

**Frontend** (noun) — the static HTML, CSS and JS in `frontend/`, served by nginx.
_Avoid_: "client", "UI" when you mean the code files

**Migration** (noun) — an Alembic revision in `backend/alembic/versions/` that changes the database schema.
_Avoid_: "schema change" when you mean the file itself
