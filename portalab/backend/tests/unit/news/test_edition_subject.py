"""#325 — an automatic newsletter's e-mail subject: its variables (in English or in French) replaced, an
unknown one left as written, never more than a subject's length."""

from portalab.modules.news.editions.service import subject_of

VALUES = {
    "site": "Xenoportal",
    "date": "1 novembre 2026",
    "day": "1 nov.",
    "week": "44",
    "month": "novembre",
    "year": "2026",
    "period": "Du 25 oct. au 1 nov.",
    "number": "12",
    "channel": "Annonce",
}


def test_the_variables_are_filled_in_english_or_in_french() -> None:
    assert subject_of("{site} — semaine {semaine} ({année})", VALUES) == "Xenoportal — semaine 44 (2026)"
    assert subject_of("Letter #{number}, {Month} {year}", VALUES) == "Letter #12, novembre 2026"
    assert subject_of("{chaîne} · {période}", VALUES) == "Annonce · Du 25 oct. au 1 nov."


def test_an_unknown_variable_stays_and_nothing_runs() -> None:
    assert (
        subject_of("{weather} {site.__class__} {{site}}", VALUES) == "{weather} {site.__class__} {Xenoportal}"
    )
    assert len(subject_of("{site} " * 80, VALUES)) == 200
