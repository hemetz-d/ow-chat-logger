import re

from ow_chat_logger.matcher import AhoCorasickMatcher

STANDARD_PATTERN = re.compile(
    r'^\[(?P<player>[^\]]+)\]\s*:\s*(?P<msg>.*)$'
)

MISSING_CLOSING_BRACKET_PATTERN = re.compile(
    r'^\[(?P<player>[^\s:\]]+)(?:\s*:\s*|\s+)(?P<msg>.*)$'
)

MISSING_OPENING_BRACKET_PATTERN = re.compile(
    r'^(?P<player>[^\s:\[]+)\](?:\s*:\s*|\s+)(?P<msg>.*)$'
)

HERO_PATTERN = re.compile(
    r'^(?!\[)(?P<player>[^()]+)\s*\((?P<hero>[^)]+)\)\s*:\s*(?P<msg>.*)$'
)

# Matches lines where OCR introduced spaces inside the player name AND misread ']' as 'l'/'I',
# with no brackets surviving at all. Player segment is alphanumeric-only (spaces stripped on
# extraction). Length-bounded to ~25 chars to guard against false positives on continuation text.
NO_BRACKET_SPACED_NAME_PATTERN = re.compile(
    r'^(?P<player>[A-Za-z0-9](?:[A-Za-z0-9 ]{0,23}[A-Za-z0-9])?)\s+[lI]:\s+(?P<msg>\S.*)$'
)

TARGETED_HERO_CHAT_PATTERN = re.compile(
    r'^.+\([^)]*\)\s+to\s+.+(?:\s*:.*)?$',
    re.IGNORECASE,
)

SYSTEM_PATTERNS = [
    r".*left the game",
    r".*joined the game",
    r".*has left the voice channel.*",
    r".*has joined the voice channel.*",
    r".*switched to .*",
    r".*is waiting to respawn.*",
    r".*endorsement received.*",
    r".*this match will shut down.*",
    r".*voice line use can distract.*",
    r".*voice lines muted for.*",
    r".*team voice chat.*",
    r".*player in channel.*",
    r".*players in channel.*",
    r".*to access voice.*",
]

# Single-character OCR corrections: maps misread char → canonical char.
# Add new pairs here as they are discovered from regression failures.
_OCR_CHAR_MAP = str.maketrans({
    ";": ":",   # semicolon misread as colon
    ",": ".",   # comma / period
    "=": "-",   # equals / minus
})

SYSTEM_MESSAGES = [
    "Chat and/or Voice enabled. Voice chat may be recorded to investigate and verify reports of disruptive behavior. Remember to act responsibly, protect your personal information, and report anything offensive.",
    "Voice chat may be recorded to investigate and verify reports of disruptive behavior.",
    "Constant voice line use can distract others Unlockable voice lines muted for",
    "Joined team voice chat - Push to talk. player in channel. Press P to access voice channels",
    "The number of messages that can be sent to this channel is limited, please wait to send another message.",
]

def generate_fragments(messages, size=15, step=1):
    fragments = set()

    for msg in messages:
        text = msg.lower()

        if len(text) <= size:
            fragments.add(text)
            continue

        for i in range(0, len(text) - size + 1, step):
            fragments.add(text[i:i+size])

    return fragments

SYSTEM_FRAGMENTS = generate_fragments(SYSTEM_MESSAGES)
SYSTEM_REGEX = re.compile("|".join(SYSTEM_PATTERNS), re.IGNORECASE)
SYSTEM_MATCHER = AhoCorasickMatcher(SYSTEM_FRAGMENTS)

def normalize(text):
    text = text.strip()

    # collapse whitespace
    text = re.sub(r"\s+", " ", text)

    # single-character OCR corrections (see _OCR_CHAR_MAP)
    text = text.translate(_OCR_CHAR_MAP)

    # Canonicalize standard chat prefix spacing once OCR has found "[player] : msg".
    text = re.sub(r"^\[([^\]]+)\]\s*:\s*", r"[\1]: ", text)

    return text

def contains_fragment(line, matcher=SYSTEM_MATCHER):
    return matcher.contains_any(line.lower())

def classify_line(line):
    line = normalize(line)

    if not line:
        return {"category": "empty"}

    # Detect system messages
    if TARGETED_HERO_CHAT_PATTERN.match(line) or SYSTEM_REGEX.search(line) or contains_fragment(line):
        return {
            "category": "system",
            "msg": line
        }

    # Standard chat format
    m1 = STANDARD_PATTERN.match(line)
    if m1:
        return {
            "category": "standard",
            "player": m1.group("player").strip().replace("|", "I"),
            "hero": "",
            "msg": m1.group("msg").strip(),
            "ocr_fix_closing_bracket": False,
        }

    for pattern in (MISSING_CLOSING_BRACKET_PATTERN, MISSING_OPENING_BRACKET_PATTERN):
        match = pattern.match(line)
        if match:
            player = match.group("player").strip().replace("|", "I")
            return {
                "category": "standard",
                "player": player,
                "hero": "",
                "msg": match.group("msg").strip(),
                "ocr_fix_closing_bracket": (
                    pattern is MISSING_CLOSING_BRACKET_PATTERN
                    and line.startswith("[")
                    and player[-1:] in ("l", "I")
                ),
            }

    # No-bracket, spaced-name, l:/I: suffix (multi-error OCR: missing both brackets,
    # spaces inserted into player name, ] misread as l or I)
    m_spaced = NO_BRACKET_SPACED_NAME_PATTERN.match(line)
    if m_spaced:
        player = m_spaced.group("player").replace(" ", "").replace("|", "I")
        return {
            "category": "standard",
            "player": player,
            "hero": "",
            "msg": m_spaced.group("msg").strip(),
            "ocr_fix_closing_bracket": False,
        }

    # Hero format
    m2 = HERO_PATTERN.match(line)
    if m2:
        return {
            "category": "hero",
            "player": m2.group("player").strip().replace("|", "I"),
            "hero": m2.group("hero").strip(),
            "msg": m2.group("msg").strip()
        }

    # fallback
    return {
        "category": "continuation",
        "msg": line
    }
    
