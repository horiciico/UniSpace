"""Academic periods API (D-027, Task 2): admin CRUD and the read endpoint for every user.

DB tests run against the rolled-back `db` fixture (PATTERN-005, PATTERN-006).
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import oauth
from app.db import get_db
from app.main import app
from app.models import AcademicPeriod, Role, User

URL = "/api/admin/academic-periods"


@pytest.fixture(autouse=True)
def reset_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


def make_client(db: Session) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, base_url="https://testserver")


def sign_in(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    sub: str,
    email: str,
    role: Role = Role.STUDENT,
) -> User:
    claims = {
        "sub": sub,
        "email": email,
        "email_verified": True,
        "hd": "ulbsibiu.ro",
        "name": "Test",
    }

    async def fake(request):
        return {"userinfo": claims}

    monkeypatch.setattr(oauth.google, "authorize_access_token", fake)
    client.get("/auth/callback", follow_redirects=False)
    user = db.scalar(select(User).where(User.email == email))
    user.role = role
    db.flush()
    return user


@pytest.fixture
def admin(db: Session, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    client = make_client(db)
    sign_in(db, client, monkeypatch, "sub-ap-admin", "ap.admin@ulbsibiu.ro", role=Role.ADMIN)
    return client


def body(
    name: str = "Semestrul 1",
    kind: str = "TEACHING",
    start: str = "2041-10-01",
    end: str = "2041-12-20",
) -> dict:
    return {"name": name, "type": kind, "start_date": start, "end_date": end}


def test_an_admin_creates_lists_updates_and_deletes_a_period(admin: TestClient) -> None:
    created = admin.post(URL, json=body())
    assert created.status_code == 201
    period = created.json()
    assert period["name"] == "Semestrul 1"
    assert period["type"] == "TEACHING"
    assert period["start_date"] == "2041-10-01"
    assert period["end_date"] == "2041-12-20"
    assert set(period) == {"id", "name", "type", "start_date", "end_date"}

    assert period in admin.get(URL).json()

    changed = admin.put(
        f"{URL}/{period['id']}", json=body(name="Sesiune", kind="EXAM_SESSION", end="2041-12-31")
    )
    assert changed.status_code == 200
    assert changed.json()["name"] == "Sesiune"
    assert changed.json()["type"] == "EXAM_SESSION"
    assert changed.json()["end_date"] == "2041-12-31"

    assert admin.delete(f"{URL}/{period['id']}").status_code == 204
    assert period["id"] not in {row["id"] for row in admin.get(URL).json()}


def test_the_lists_are_ordered_by_start_date(admin: TestClient) -> None:
    admin.post(URL, json=body("C", "HOLIDAY", "2042-03-01", "2042-03-05"))
    admin.post(URL, json=body("A", "TEACHING", "2042-01-01", "2042-01-31"))
    admin.post(URL, json=body("B", "EXAM_SESSION", "2042-02-01", "2042-02-20"))
    for url in (URL, "/api/academic-periods"):
        rows = admin.get(url).json()
        mine = [row["name"] for row in rows if row["start_date"].startswith("2042")]
        assert mine == ["A", "B", "C"]
        starts = [row["start_date"] for row in rows]
        assert starts == sorted(starts)


def test_any_signed_in_user_reads_the_periods_but_only_an_admin_manages_them(
    db: Session, admin: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    period = admin.post(URL, json=body()).json()
    student = make_client(db)
    assert student.get("/api/academic-periods").status_code == 401
    sign_in(db, student, monkeypatch, "sub-ap-student", "ap.student@ulbsibiu.ro")

    assert period["id"] in {row["id"] for row in student.get("/api/academic-periods").json()}
    other = body("X", start="2043-01-01", end="2043-01-02")
    assert student.get(URL).status_code == 403
    assert student.post(URL, json=other).status_code == 403
    assert student.put(f"{URL}/{period['id']}", json=body()).status_code == 403
    assert student.delete(f"{URL}/{period['id']}").status_code == 403


def test_signed_out_is_refused_everywhere(db: Session) -> None:
    client = make_client(db)
    some_id = uuid.uuid4()
    assert client.get(URL).status_code == 401
    assert client.post(URL, json=body()).status_code == 401
    assert client.put(f"{URL}/{some_id}", json=body()).status_code == 401
    assert client.delete(f"{URL}/{some_id}").status_code == 401


def test_inverted_dates_are_a_400(admin: TestClient) -> None:
    assert admin.post(URL, json=body(start="2044-02-02", end="2044-02-01")).status_code == 400
    period = admin.post(URL, json=body(start="2044-05-01", end="2044-05-10")).json()
    r = admin.put(f"{URL}/{period['id']}", json=body(start="2044-05-10", end="2044-05-01"))
    assert r.status_code == 400


def test_a_one_day_period_is_allowed(admin: TestClient) -> None:
    r = admin.post(URL, json=body("Zi", "HOLIDAY", "2045-04-04", "2045-04-04"))
    assert r.status_code == 201


def test_an_overlapping_period_is_a_409_and_is_not_saved(db: Session, admin: TestClient) -> None:
    admin.post(URL, json=body("A", start="2046-02-01", end="2046-02-28"))
    r = admin.post(URL, json=body("B", "HOLIDAY", "2046-02-28", "2046-03-05"))
    assert r.status_code == 409
    assert "'A'" in r.json()["detail"]
    assert db.scalar(select(AcademicPeriod).where(AcademicPeriod.name == "B")) is None


def test_an_update_may_overlap_itself_but_not_another_period(admin: TestClient) -> None:
    a = admin.post(URL, json=body("A", start="2047-02-01", end="2047-02-28")).json()
    b = admin.post(URL, json=body("B", "HOLIDAY", "2047-03-01", "2047-03-10")).json()

    shrunk = admin.put(f"{URL}/{a['id']}", json=body("A2", start="2047-02-05", end="2047-02-28"))
    assert shrunk.status_code == 200
    same = admin.put(f"{URL}/{b['id']}", json=body("B", "HOLIDAY", "2047-03-01", "2047-03-10"))
    assert same.status_code == 200
    clash = admin.put(f"{URL}/{b['id']}", json=body("B", "HOLIDAY", "2047-02-10", "2047-03-10"))
    assert clash.status_code == 409
    assert admin.get(URL).json().count(b) == 1  # the rejected update changed nothing


def test_an_unknown_period_is_a_404(admin: TestClient) -> None:
    unknown = uuid.uuid4()
    assert admin.put(f"{URL}/{unknown}", json=body()).status_code == 404
    assert admin.delete(f"{URL}/{unknown}").status_code == 404


def test_a_bad_body_is_a_422(admin: TestClient) -> None:
    assert admin.post(URL, json=body(kind="VACATION")).status_code == 422
    assert admin.post(URL, json=body(name="   ")).status_code == 422
    assert admin.post(URL, json=body(name="x" * 151)).status_code == 422
    assert admin.post(URL, json=body(start="not-a-date")).status_code == 422
    assert admin.post(URL, json={"name": "A"}).status_code == 422


def test_the_name_is_trimmed(admin: TestClient) -> None:
    r = admin.post(
        URL, json=body(name="  Vacanță  ", kind="HOLIDAY", start="2048-01-01", end="2048-01-02")
    )
    assert r.json()["name"] == "Vacanță"
