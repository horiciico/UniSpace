"""i18n checks for the frontend: both languages have every key, and every key the pages and
scripts use exists. Reads the frontend folder, mounted read-only at /frontend in compose
(FRONTEND_DIR overrides the location)."""
import json
import os
import re
from pathlib import Path

import pytest

FRONTEND = Path(os.environ.get("FRONTEND_DIR", "/frontend"))
LANGUAGES = ["ro", "en"]

# Keys built at run time in the scripts, so the literal scan cannot see them.
DYNAMIC_KEYS = (
    [f"role.{r}" for r in ("STUDENT", "PROFESSOR", "STUDENT_ORG", "ADMIN")]
    + [f"theme.{m}" for m in ("auto", "light", "dark")]
    + [f"login.{reason}{part}" for reason in ("denied", "failed") for part in ("Title", "Text")]
)
# A key is a dotted name such as "nav.timetable" in quotes.
KEY_IN_SCRIPT = re.compile(r'"((?:nav|header|footer|theme|role|toast|placeholder|login|status|kind|day|timetable|common|home|announce|calendar|changes|admin|bookings|rooms|roomDetail|free|notFound)\.[A-Za-z0-9_.]+)"')


def load_dictionary(language: str) -> dict:
    source = (FRONTEND / "i18n" / f"{language}.js").read_text(encoding="utf-8")
    start = source.index("register(")
    body = source[source.index("{", start): source.rindex("}") + 1]
    return json.loads(body)


def html_pages() -> list[Path]:
    return sorted(FRONTEND.rglob("*.html"))


def script_files() -> list[Path]:
    return sorted((FRONTEND / "js").glob("*.js"))


def keys_used_in_html() -> set[str]:
    keys: set[str] = set()
    for page in html_pages():
        text = page.read_text(encoding="utf-8")
        keys.update(re.findall(r'data-i18n="([^"]+)"', text))
        keys.update(re.findall(r'data-placeholder-action="([^"]+)"', text))
        for spec in re.findall(r'data-i18n-attr="([^"]+)"', text):
            for pair in spec.split(";"):
                if ":" in pair:
                    keys.add(pair.split(":", 1)[1].strip())
    return keys


def keys_used_in_scripts() -> set[str]:
    keys: set[str] = set()
    for script in script_files():
        keys.update(KEY_IN_SCRIPT.findall(script.read_text(encoding="utf-8")))
    return keys | set(DYNAMIC_KEYS)


@pytest.fixture(scope="module")
def dictionaries() -> dict:
    return {language: load_dictionary(language) for language in LANGUAGES}


def test_frontend_is_mounted() -> None:
    assert (FRONTEND / "i18n" / "ro.js").exists(), f"frontend folder not found at {FRONTEND}"


def test_both_languages_have_the_same_keys(dictionaries: dict) -> None:
    ro, en = set(dictionaries["ro"]), set(dictionaries["en"])
    assert ro - en == set(), f"only in ro.js: {sorted(ro - en)}"
    assert en - ro == set(), f"only in en.js: {sorted(en - ro)}"


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_text_is_a_non_empty_string(dictionaries: dict, language: str) -> None:
    empty = [k for k, v in dictionaries[language].items() if not isinstance(v, str) or not v.strip()]
    assert empty == [], f"empty or non-string values in {language}.js: {empty}"


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_key_used_on_a_page_exists(dictionaries: dict, language: str) -> None:
    missing = sorted(keys_used_in_html() - set(dictionaries[language]))
    assert missing == [], f"keys used in HTML but missing from {language}.js: {missing}"


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_key_used_in_a_script_exists(dictionaries: dict, language: str) -> None:
    missing = sorted(keys_used_in_scripts() - set(dictionaries[language]))
    assert missing == [], f"keys used in scripts but missing from {language}.js: {missing}"


def test_no_dictionary_key_is_unused(dictionaries: dict) -> None:
    # Keys kept for the scripts' dynamic lookups are used even though no literal names them.
    used = keys_used_in_html() | keys_used_in_scripts()
    unused = sorted(set(dictionaries["ro"]) - used)
    assert unused == [], f"keys in the dictionaries that no page or script uses: {unused}"


def test_every_page_loads_the_runtime_and_both_dictionaries() -> None:
    for page in html_pages():
        text = page.read_text(encoding="utf-8")
        for script in ("/i18n/i18n.js", "/i18n/ro.js", "/i18n/en.js"):
            assert script in text, f"{page.relative_to(FRONTEND)} does not load {script}"
        assert text.index("/i18n/i18n.js") < text.index("/js/layout.js") or "/js/layout.js" not in text, (
            f"{page.relative_to(FRONTEND)}: i18n.js must load before layout.js"
        )
