"""Issue 229: where a card's face is — the centre of an image's largest face, as fractions of it."""

from portalab.modules.cards.faces import Face, Looked
from portalab.modules.cards.focus import centre


def test_the_largest_face_is_the_one_framed() -> None:
    small = Face(signature=None, share=0.01, box=(10, 10, 20, 20))
    large = Face(signature=None, share=0.2, box=(100, 50, 200, 300))
    assert centre(Looked(faces=[small, large], width=400, height=800)) == [0.5, 0.25, 0.375]
    assert centre(Looked(faces=[], width=400, height=800)) is None
