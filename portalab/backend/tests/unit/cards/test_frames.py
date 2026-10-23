"""Issue 230: a character's image taken from the film — the moments, the frame around the face, which actor
gets which image."""

from portalab.modules.cards.faces import Face
from portalab.modules.cards.frames import SAME_ACTOR, assign, crop_box, moments


def test_moments_spread_over_the_film_before_its_credits() -> None:
    at = moments()
    assert len(at) == 96 and at[0] == 0.06 and at[-1] == 0.9
    assert at == sorted(at)


def test_the_frame_around_a_face() -> None:
    left, top, width, height = crop_box((600, 200, 120, 150), 1280, 720)
    assert (width, height) == (640, 480) and width * 3 == height * 4  # 4:3, head and shoulders
    assert left == 340 and top == 83  # centred on the face, the face at two fifths of the height
    # at the image's edge: kept within it
    left, top, width, height = crop_box((1200, 650, 60, 60), 1280, 720)
    assert left + width <= 1280 and top + height <= 720 and (width, height) == (480, 360)
    # a film in a wider format, black bars above and below: the frame stays on the picture
    left, top, width, height = crop_box((600, 160, 60, 60), 1280, 720, 88, 632)
    assert top >= 88 and top + height <= 632
    # a face filling a narrow image: the frame as wide as the image
    assert crop_box((0, 0, 400, 700), 600, 800)[2] == 600


def test_each_actor_gets_the_image_where_their_face_is_clearest() -> None:
    def face(who: str, height: int) -> Face:
        return Face(who, 0.05, (0, 0, height, height), 100.0)

    def similar(a: Face, b: Face) -> float:
        return 0.9 if a.signature == b.signature else 0.2

    portraits = {"cruise": face("cruise", 300), "teller": face("teller", 300)}
    frames = [
        [face("cruise", 80)],  # him, small
        [face("cruise", 220), face("teller", 220)],  # both, large
        [face("teller", 60)],  # too small: someone in the background
        [face("x", 200), face("y", 200), face("z", 200), face("teller", 240)],  # a crowd
    ]
    picks = assign(portraits, frames, similar)
    assert picks["cruise"].frame == 1 and picks["teller"].frame == 1
    assert assign({"cruise": portraits["cruise"]}, [[face("teller", 220)]], similar) == {}  # not him

    def alike(a: Face, b: Face) -> float:  # two actors alike: a face close to both is nobody's
        return (
            0.9 if a.signature == b.signature else (0.87 if {a.signature, b.signature} == {"a", "b"} else 0.1)
        )

    assert assign({"a": face("a", 300), "b": face("b", 300)}, [[face("a", 200)]], alike) == {}
    assert SAME_ACTOR >= 0.4


def test_a_stock_photograph_is_never_kept() -> None:
    """Its site's watermark is printed over it."""
    from portalab.modules.cards.faces import Candidate, score

    def kept(url: str) -> float | None:
        return score(
            Candidate(url, "Tom Sizemore as Horvath in Saving Private Ryan", "bing", 0.8, 1280, 720),
            "Sergeant Horvath",
            "Saving Private Ryan",
        )

    assert kept("https://images.example.org/horvath.jpg") is not None
    assert kept("https://c8.alamy.com/comp/X1/horvath.jpg") is None
    assert kept("https://www.shutterstock.com/image-photo/horvath.jpg") is None
