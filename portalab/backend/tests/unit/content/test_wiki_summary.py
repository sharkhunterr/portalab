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
