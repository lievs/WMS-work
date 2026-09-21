"""Canonical marketplace shipping destinations."""

import re


CITY_ALIASES = {
    "екб": "Екатеринбург",
    "екатеринбург": "Екатеринбург",
    "спб": "Санкт-Петербург",
    "питер": "Санкт-Петербург",
    "санкт петербург": "Санкт-Петербург",
    "санкт-петербург": "Санкт-Петербург",
    "москва": "Москва",
    "москва 1": "Москва",
    "москва 2": "Москва",
}

MARKETPLACE_ALIASES = {"озон": "ozon", "ozon": "ozon", "вб": "wb", "wb": "wb", "wildberries": "wb"}
MARKETPLACE_LABELS = {"ozon": "ОЗОН", "wb": "ВБ"}


def _spaces(value):
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_marketplace(value):
    return MARKETPLACE_ALIASES.get(_spaces(value).casefold().replace("ё", "е"), _spaces(value).casefold())


def canonical_city(value):
    """Strip marketplace prefixes and normalize spelling/case/spacing."""
    text = _spaces(value).replace("ё", "е")
    text = re.sub(r"^(?:озон|ozon|вб|wb|wildberries)\s*[:\-–—]?\s*", "", text, flags=re.I)
    text = _spaces(text)
    key = text.casefold()
    if key in CITY_ALIASES:
        return CITY_ALIASES[key]
    # Number suffixes in marketplace exports usually denote a gate/slot,
    # not another city (МОСКВА 1 / МОСКВА 2).
    key_without_slot = re.sub(r"\s+[12]$", "", key)
    if key_without_slot in CITY_ALIASES:
        return CITY_ALIASES[key_without_slot]
    return " ".join(part.capitalize() for part in text.split())


def direction_key(marketplace, city):
    return f"{normalize_marketplace(marketplace)}|{canonical_city(city).casefold()}"


def direction_name(marketplace, city):
    mp = normalize_marketplace(marketplace)
    return f"{MARKETPLACE_LABELS.get(mp, mp.upper())}: {canonical_city(city)}"
