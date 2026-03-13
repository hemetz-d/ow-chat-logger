import re

STANDARD_PATTERN = re.compile(
    r'^\[(?P<player>[^\]]+)\]\s*:\s*(?P<msg>.*)$'
)

HERO_PATTERN = re.compile(
    r'^(?P<player>[^()]+)\s*\((?P<hero>[^)]+)\)(?:\s*:\s*(?P<msg>.*))?$'
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
    r".*voice lines muted for.*"
    r".*team voice chat.*",
    r".*player in channel.*",
    r".*players in channel.*",
    r".*to access voice.*",
    r"channels",
]

SYSTEM_MESSAGES = [
    "Chat and/or Voice enabled. Voice chat may be recorded to investigate and verify reports of disruptive behavior. Remember to act responsibly, protect your personal information, and report anything offensive.",
    "Voice chat may be recorded to investigate and verify reports of disruptive behavior.",
    "Constant voice line use can distract others Unlockable voice lines muted for",
    "Joined team voice chat - Push to talk. player in channel. Press P to access voice channels"
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

def normalize(text):
    text = text.strip()

    # collapse whitespace
    text = re.sub(r"\s+", " ", text)

    # common OCR punctuation fixes
    text = text.replace(";", ":")
    text = text.replace("|", "I")

    return text

def contains_fragment(line, fragments):
    lower = line.lower()
    return any(f in lower for f in fragments)

def classify_line(line):
    line = normalize(line)

    if not line:
        return {"category": "empty"}

    # Detect system messages
    if SYSTEM_REGEX.search(line) or contains_fragment(line, SYSTEM_FRAGMENTS):
        return {
            "category": "system",
            "msg": line
        }

    # Standard chat format
    m1 = STANDARD_PATTERN.match(line)
    if m1:
        return {
            "category": "standard",
            "player": m1.group("player").strip(),
            "hero": "",
            "msg": m1.group("msg").strip()
        }

    # Hero format
    m2 = HERO_PATTERN.match(line)
    if m2:
        return {
            "category": "hero",
            "player": m2.group("player").strip(),
            "hero": m2.group("hero").strip(),
            "msg": (m2.group("msg") or "").strip()
        }

    # fallback
    return {
        "category": "continuation",
        "msg": line
    }
    
