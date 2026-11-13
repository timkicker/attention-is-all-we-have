"""Label codes from Valio's packagingMarkedLabel. Temperature codes in the same field are not labels."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LabelInfo:
    name: str
    kind: str  # origin, health, eco, organic, fish, social


LABELS: dict[str, LabelInfo] = {
    "GOODS_FROM_FINLAND_BLUE_SWAN": LabelInfo("Hyvää Suomesta", "origin"),
    "MADE_IN_FINLAND_FLAG_WITH_KEY": LabelInfo("Avainlippu", "origin"),
    "FINNISH_HEART_SYMBOL": LabelInfo("Heart Symbol", "health"),
    "SVANEN": LabelInfo("Nordic Swan Ecolabel", "eco"),
    "EU_ECO_LABEL": LabelInfo("EU Ecolabel", "eco"),
    "EU_ORGANIC_FARMING": LabelInfo("EU organic", "organic"),
    "KRAV_MARK": LabelInfo("KRAV", "organic"),
    "MARINE_STEWARDSHIP_COUNCIL_LABEL": LabelInfo("MSC", "fish"),
    "AQUACULTURE_STEWARDSHIP_COUNCIL": LabelInfo("ASC", "fish"),
    "FAIR_TRADE_MARK": LabelInfo("Fairtrade", "social"),
    "RAINFOREST_ALLIANCE": LabelInfo("Rainforest Alliance", "social"),
}

TEMPERATURE_CODES = frozenset({"warmTemperature", "coolTemperature", "freezeTemperature"})


def is_label(code: str) -> bool:
    return code not in TEMPERATURE_CODES and not code.endswith("Temperature")
