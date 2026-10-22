"""A wiki card's summary: the page's first paragraph of prose, without Markdown, cut cleanly."""

from portalab.modules.wiki.pages import summary_of


def test_first_prose_paragraph_without_markdown() -> None:
    body = (
        "# Title\n\n> [!TIP]\n> A tip.\n\n- a list\n\n"
        "Read [the shop](portalab://wiki/shop) **first**.\n\nNext."
    )
    assert summary_of(body) == "Read the shop first."


def test_cut_at_a_sentence_or_a_word() -> None:
    long = "First sentence here. " + "word " * 60
    assert summary_of(long, limit=30) == "First sentence here."
    assert summary_of("word " * 60, limit=30).endswith("…")
    assert len(summary_of("word " * 60, limit=30)) <= 31


def test_no_prose() -> None:
    assert summary_of("## Only a heading\n\n- and a list") == ""


def test_a_line_of_tags_is_not_a_summary() -> None:
    assert (
        summary_of("`Public : Utilisateur` · `MAJ : 08/2026`\n\n## En bref\n\nUne phrase.") == "Une phrase."
    )


def test_a_sentence_announcing_a_list_is_left_out() -> None:
    assert summary_of("RomM est la ludothèque. Deux façons d'y jouer :\n\n- ici") == "RomM est la ludothèque."


def test_a_caption_in_italics_is_not_a_summary() -> None:
    assert summary_of("*Public : Utilisateur · MAJ : 08/2026*\n\nUne phrase.") == "Une phrase."
