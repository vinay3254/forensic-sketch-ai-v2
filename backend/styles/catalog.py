"""The style library: fixed looks an officer can put on the sketch with one click.

Each style is one image edit of the latest sketch. `regions` names the face-parser regions the
change is kept inside (face/regions.py); None lets the whole sketch change. `field` is the face
attribute the style replaces, if any. Wording is plain clothing/appearance, never incident words."""

from dataclasses import dataclass
from pathlib import Path

# thumbnails drawn once by scripts/make_style_thumbs.py
ASSETS = Path(__file__).resolve().parent.parent / "assets" / "styles"


INHERIT = ("inherit",)  # use the category's regions


@dataclass(frozen=True)
class Style:
    key: str
    label: str
    change: str  # the look, as told to the image model
    regions: tuple[str, ...] | None = INHERIT


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    regions: tuple[str, ...] | None
    field: str | None  # Attributes field the style sets
    thumb: str  # how the thumbnail shows one style: {change} is filled in
    styles: tuple[Style, ...]


def _s(key: str, label: str, change: str, regions: tuple[str, ...] | None = INHERIT) -> Style:
    return Style(key, label, change, regions)


def regions_of(c: "Category", s: Style) -> tuple[str, ...] | None:
    return c.regions if s.regions == INHERIT else s.regions


CATEGORIES: tuple[Category, ...] = (
    Category("clothing", "Clothing", ("clothing",), None,
             "head-and-shoulders pencil study of a faceless mannequin {change}", (
        _s("tshirt", "T-shirt", "wearing a plain crew-neck t-shirt"),
        _s("collared_shirt", "Collared shirt", "wearing a buttoned collared shirt"),
        _s("polo", "Polo shirt", "wearing a polo shirt with a short placket"),
        _s("hoodie", "Hoodie", "wearing a hooded sweatshirt with the hood down"),
        _s("jacket", "Zip jacket", "wearing a zip-up jacket over a t-shirt"),
        _s("leather_jacket", "Leather jacket", "wearing a leather jacket with wide lapels"),
        _s("kurta", "Kurta", "wearing a kurta with a short buttoned placket"),
        _s("sweater", "Sweater", "wearing a knitted crew-neck sweater"),
        _s("vest", "Sleeveless vest", "wearing a sleeveless vest"),
        _s("jersey", "Sports jersey", "wearing a sports jersey with a v-neck"),
        _s("blazer", "Blazer", "wearing a blazer over a collared shirt"),
        _s("shawl", "Shawl", "with a shawl draped over the shoulders"),
    )),
    Category("hair", "Hair", ("hair",), "hair",
             "pencil study of a faceless mannequin head {change}", (
        _s("short_crop", "Short crop", "with short cropped hair"),
        _s("side_part", "Side part", "with short hair combed into a side part"),
        _s("slicked_back", "Slicked back", "with hair slicked straight back"),
        _s("curly", "Curly", "with short curly hair"),
        _s("long_straight", "Long straight", "with long straight hair past the shoulders"),
        _s("ponytail", "Ponytail", "with long hair tied back in a ponytail"),
        _s("buzz_cut", "Buzz cut", "with a very short buzz cut"),
        _s("spiky", "Spiky", "with short spiky hair"),
        _s("receding", "Receding", "with a receding hairline and short hair"),
        _s("bald", "Bald", "with a fully bald head"),
    )),
    Category("facial_hair", "Facial hair", ("facial_hair",), "facial_hair",
             "pencil study of the lower half of a faceless mannequin face {change}", (
        _s("clean_shaven", "Clean-shaven", "clean-shaven, with no facial hair"),
        _s("stubble", "Stubble", "with a few days of stubble"),
        _s("moustache", "Moustache", "with a full moustache"),
        _s("handlebar", "Handlebar", "with a handlebar moustache"),
        _s("goatee", "Goatee", "with a goatee on the chin"),
        _s("full_beard", "Full beard", "with a full beard and moustache"),
        _s("chin_strap", "Chin strap", "with a thin chin-strap beard along the jaw"),
        _s("long_beard", "Long beard", "with a long full beard"),
    )),
    Category("headwear", "Headwear", ("hair",), None,
             "pencil study of a faceless mannequin head {change}", (
        _s("cap", "Cap", "wearing a plain baseball cap"),
        _s("beanie", "Beanie", "wearing a knitted beanie"),
        _s("brimmed_hat", "Brimmed hat", "wearing a hat with a wide brim"),
        _s("turban", "Turban", "wearing a wrapped turban"),
        _s("skull_cap", "Skull cap", "wearing a small round skull cap"),
        _s("bandana", "Bandana", "wearing a bandana tied over the head"),
        _s("helmet", "Bike helmet", "wearing an open-face motorbike helmet"),
        _s("hood_up", "Hood up", "wearing a hooded top with the hood up"),
    )),
    Category("eyewear", "Eyewear", ("accessories", "eyes"), None,
             "pencil study of the eye area of a faceless mannequin {change}", (
        _s("thin_glasses", "Thin frames", "wearing thin metal-framed glasses"),
        _s("thick_glasses", "Thick frames", "wearing thick dark-framed glasses"),
        _s("round_glasses", "Round glasses", "wearing small round glasses"),
        _s("rimless", "Rimless", "wearing rimless glasses"),
        _s("sunglasses", "Sunglasses", "wearing dark sunglasses"),
        _s("aviators", "Aviators", "wearing aviator sunglasses"),
    )),
    Category("accessories", "Accessories", None, None,
             "pencil study of a faceless mannequin head and shoulders {change}", (
        _s("hoop_earrings", "Hoop earrings", "wearing hoop earrings", ("ears",)),
        _s("stud_earrings", "Stud earrings", "wearing small stud earrings", ("ears",)),
        _s("nose_ring", "Nose ring", "wearing a small nose ring", ("nose",)),
        _s("chain", "Neck chain", "wearing a thin chain around the neck", ("clothing",)),
        _s("scarf", "Scarf", "wearing a scarf around the neck", ("clothing",)),
        _s("face_mask", "Face mask", "wearing a cloth face mask over the nose and mouth", ("facial_hair", "nose")),
        _s("bindi", "Bindi", "wearing a small bindi on the forehead"),
        _s("tilak", "Tilak", "with a tilak mark on the forehead"),
    )),
)

BY_KEY: dict[str, tuple[Category, Style]] = {s.key: (c, s) for c in CATEGORIES for s in c.styles}
CATEGORY_BY_KEY = {c.key: c for c in CATEGORIES}


def style_file(key: str) -> Path | None:
    if key not in BY_KEY:  # only catalog keys ever reach the filesystem
        return None
    path = ASSETS / f"{key}.png"
    return path if path.is_file() else None


def as_attribute(change: str) -> str:
    """'with short cropped hair' -> 'short cropped hair' for the attribute panel."""
    for lead in ("wearing ", "with "):
        if change.startswith(lead):
            return change[len(lead):]
    return change
