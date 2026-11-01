"""#320 — the portal's e-mails in Portalab's look: the site's name and mark, the night card under the brand's
line, every text escaped, plain text turned into paragraphs with its addresses as links, the action a
button."""

from portalab.capabilities.notifications.layout import ACCENT, NIGHT, Brand, button, dress, paragraphs


def test_an_email_wears_the_portal_look_and_escapes_its_words() -> None:
    brand = Brand("Xeno<portal>", "https://home.example.org")
    html = dress(
        brand,
        title="Dune <2> est là",
        body_html=paragraphs("Bonjour <toi>\n\nVoir https://example.org/x")
        + button("Ouvrir", brand.link("/media/a")),
        kicker="Nouveautés",
        note="Selon vos préférences",
        manage=("Gérer", brand.link("/settings/notifications")),
        language="fr",
    )
    assert html.startswith("<!doctype html>") and 'lang="fr"' in html
    assert NIGHT in html and ACCENT in html and "Plus Jakarta Sans" in html
    assert "Xeno&lt;portal&gt;" in html and ">X<" in html  # the name and its mark (its initial)
    assert "Dune &lt;2&gt; est là" in html and "<toi>" not in html
    assert '<a href="https://example.org/x"' in html  # an address in the text is a link
    assert 'href="https://home.example.org/media/a"' in html and "Ouvrir →" in html
    assert 'href="https://home.example.org/settings/notifications"' in html


def test_a_route_is_made_whole_with_the_portal_address() -> None:
    assert Brand(portal="https://p.example/").link("/feed") == "https://p.example/feed"
    assert Brand(portal="").link("/feed") == "/feed"
    assert Brand().link("https://elsewhere.example/x") == "https://elsewhere.example/x"
