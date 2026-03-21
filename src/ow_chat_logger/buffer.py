from ow_chat_logger.parser import classify_line

class MessageBuffer:
    def __init__(self):
        self.current = None
        self.in_system_message = False

    def feed(self, line):
        classification = classify_line(line)
        category = classification["category"]

        # -----------------------
        # SYSTEM MESSAGE
        # -----------------------
        if category == "system":
            finished = self.current
            self.current = None
            self.in_system_message = True
            return finished

        # -----------------------
        # CONTINUATION
        # -----------------------
        if category == "continuation":
            text = classification["msg"].strip()
            # Ignore continuation if no active message from a player
            if not self.current or self.in_system_message:
                return None
            self.current["msg"] += " " + text
            return None

        # -----------------------
        # NEW PLAYER MESSAGE
        # -----------------------
        self.in_system_message = False
        finished = self.current

        self.current = {
            "player": classification["player"],
            "hero": classification["hero"],
            "msg": classification["msg"],
            "category": category,
        }

        return finished

    def flush(self):
        """Return any buffered message and clear state (e.g. on shutdown).

        Does not classify input; only emits the current partial message if any.
        """
        finished = self.current
        self.current = None
        self.in_system_message = False
        return finished
