from __future__ import annotations

import re
import unicodedata


CANONICAL_HEROES = (
    "Anran",
    "Ana",
    "Ashe",
    "Baptiste",
    "Bastion",
    "Brigitte",
    "Cassidy",
    "D.Va",
    "Domina",
    "Doomfist",
    "Echo",
    "Emre",
    "Freja",
    "Genji",
    "Hanzo",
    "Hazard",
    "Illari",
    "Jetpack Cat",
    "Junker Queen",
    "Junkrat",
    "Juno",
    "Kiriko",
    "Lifeweaver",
    "Lucio",
    "Lúcio",
    "Mauga",
    "Mei",
    "Mercy",
    "Mizuki",
    "Moira",
    "Orisa",
    "Pharah",
    "Ramattra",
    "Reaper",
    "Reinhardt",
    "Roadhog",
    "Sigma",
    "Sojourn",
    "Soldier 76",
    "Soldier: 76",
    "Sombra",
    "Symmetra",
    "Torbjorn",
    "Torbjörn",
    "Tracer",
    "Venture",
    "Vendetta",
    "Widowmaker",
    "Winston",
    "Wrecking Ball",
    "Wuyang",
    "Zarya",
    "Zenyatta",
)

_SPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^a-z0-9]+")

_EXPLICIT_ALIASES = {
    "dva": "D.Va",
    "lucio": "Lúcio",
    "soldier76": "Soldier: 76",
    "torbjorn": "Torbjörn",
}


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _hero_key(text: str) -> str:
    text = _strip_accents(text).casefold().strip()
    text = _SPACE_RE.sub(" ", text)
    return _PUNCT_RE.sub("", text)


_CANONICAL_BY_KEY = {}
for hero in CANONICAL_HEROES:
    _CANONICAL_BY_KEY.setdefault(_hero_key(hero), hero)

for alias_key, canonical in _EXPLICIT_ALIASES.items():
    _CANONICAL_BY_KEY[alias_key] = canonical


def canonicalize_hero_name(raw_hero: str) -> str:
    """Return the canonical hero name or an empty string when it is not whitelisted."""
    if not raw_hero:
        return ""
    return _CANONICAL_BY_KEY.get(_hero_key(raw_hero), "")
