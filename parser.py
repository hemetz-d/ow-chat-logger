import re

STANDARD_PATTERN = re.compile(
    r'^\[(?P<player>[^\]]+)\]\s*:\s*(?P<msg>.*)$'
)

HERO_PATTERN = re.compile(
    r'^(?P<player>[^()]+)\s*\((?P<hero>[^)]+)\)(?:\s*:\s*(?P<msg>.*))?$'
)


def classify_line(line):
    line = normalize(line)

    # fix OCR colon issue
    line = line.replace(";", ":")

    m1 = STANDARD_PATTERN.match(line)
    if m1:
        return {
            "category": "standard",
            "player": m1.group("player").strip(),
            "hero": "",
            "msg": m1.group("msg").strip()
        }

    m2 = HERO_PATTERN.match(line)
    if m2:
        return {
            "category": "hero",
            "player": m2.group("player").strip(),
            "hero": m2.group("hero").strip(),
            "msg": (m2.group("msg") or "").strip()
        }

    return None  # continuation

def normalize(text):
    return re.sub(r'\s+', ' ', text.strip())