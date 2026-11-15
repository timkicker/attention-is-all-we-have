"""Valio's product groups: the first three digits of a product's category, with a short plain name each.

Valio's product file carries the category code only, no names. These names were written from the products in each
group of the hackathon catalogue (data/raw, 17,546 products in 43 groups), so the Rules can say "Fruit and
vegetables" where the Spend Pass says "174". The pass signs codes, never names: a name only reads a code out.
"""

from collections.abc import Iterable

GROUPS: dict[str, str] = {
    "104": "Milk and dairy drinks",
    "105": "Butter, oils and eggs",
    "106": "Cheese",
    "109": "Bread",
    "110": "Sweet pastries and cakes",
    "172": "Cold cuts and sausages",
    "173": "Ready meals and salads",
    "174": "Fruit and vegetables",
    "187": "Meat and fish",
    "200": "Kitchenware and tableware",
    "211": "Biscuits and snack bars",
    "212": "Crispbread",
    "213": "Flour, rice and pasta",
    "214": "Jams, juices and nuts",
    "215": "Tinned and pickled food",
    "216": "Baby food",
    "219": "Sauces, dressings and stock",
    "221": "Sugar, honey and syrups",
    "223": "Ground coffee",
    "224": "Coffee beans and coffee drinks",
    "225": "Tea and cocoa",
    "226": "Spices and baking",
    "227": "Soft drinks and water",
    "300": "Garden and pest control",
    "329": "Matches and lighters",
    "417": "Frozen food",
    "418": "Ice cream and frozen desserts",
    "522": "Sweets and chocolate",
    "630": "Hygiene and first aid",
    "631": "Cleaning and laundry",
    "632": "Napkins and paper towels",
    "633": "Workwear",
    "639": "Kitchen appliances",
    "640": "Take-away packaging",
    "641": "Charcoal and outdoor",
    "643": "Household and batteries",
    "645": "Gift boxes and wrapping",
    "677": "Newspapers",
    "678": "Party decorations",
    "777": "Drink gases",
    "849": "Alcohol-free beer and cider",
    "850": "Alcohol-free beer and wine",
    "900": "Office supplies",
}


def group_of(category: str) -> str:
    """The three-digit group of a Valio category: "17413" is in "174"."""
    return (category or "")[:3]


def group_name(code: str) -> str:
    """The plain name of a group or of a category inside it; the code itself when Valio added a group since."""
    return GROUPS.get(group_of(code), f"Product group {group_of(code) or code}")


def unknown(codes: Iterable[str]) -> list[str]:
    """The codes that are not one of Valio's three-digit groups."""
    return [c for c in codes if c not in GROUPS]
