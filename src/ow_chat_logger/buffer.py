from ow_chat_logger.parser import classify_line


def _is_single_glyph(text: str) -> bool:
    return len(text) == 1 and text.isalnum()


class MessageBuffer:
    def __init__(self):
        self.current = None
        self.in_system_message = False
        self._last_y: float | None = None

    def _start_message(self, classification: dict[str, object], y: float | None):
        self.in_system_message = False
        self._last_y = y
        finished = self.current
        self.current = {
            "player": classification["player"],
            "hero": classification["hero"],
            "msg": classification["msg"],
            "category": classification["category"],
            "ocr_fix_closing_bracket": classification.get("ocr_fix_closing_bracket", False),
        }
        return finished

    def feed(
        self,
        line: str,
        y: float | None = None,
        max_y_gap: float | None = None,
        prefix_evidence: dict | None = None,
    ):
        classification = classify_line(line)
        category = classification["category"]

        # -----------------------
        # SYSTEM MESSAGE
        # -----------------------
        if category == "system":
            finished = self.current
            self.current = None
            self.in_system_message = True
            self._last_y = y
            return finished

        # -----------------------
        # CONTINUATION
        # -----------------------
        if category == "continuation":
            text = classification["msg"].strip()
            if _is_single_glyph(text):
                return None
            if (prefix_evidence or {}).get("has_missing_prefix_evidence"):
                recovered = (prefix_evidence or {}).get("recovered_player")
                player = recovered if isinstance(recovered, str) and recovered else "unknown"
                return self._start_message(
                    {
                        "category": "standard",
                        "player": player,
                        "hero": "",
                        "msg": text,
                        "ocr_fix_closing_bracket": False,
                    },
                    y,
                )
            # Ignore continuation if no active message from a player
            if not self.current or self.in_system_message:
                return None
            # Discard if the vertical gap from the last line is too large
            if (
                y is not None
                and self._last_y is not None
                and max_y_gap is not None
                and (y - self._last_y) > max_y_gap
            ):
                return None
            self._last_y = y
            self.current["msg"] += " " + text
            return None

        # -----------------------
        # NEW PLAYER MESSAGE
        # -----------------------
        return self._start_message(classification, y)

    def flush(self):
        """Return any buffered message and clear state (e.g. on shutdown).

        Does not classify input; only emits the current partial message if any.
        """
        finished = self.current
        self.current = None
        self.in_system_message = False
        self._last_y = None
        return finished
