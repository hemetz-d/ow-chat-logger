from parser import classify_line

class MessageBuffer:
    def __init__(self):
        self.current = None

    def feed(self, line):
        classification = classify_line(line)

        # New message start
        if classification is not None:
            finished = self.current
            self.current = {
                "player": classification["player"],
                "hero": classification["hero"],
                "msg": classification["msg"],
                "category": classification["category"],
            }
            return finished

        # Continuation
        if self.current:
            self.current["msg"] += " " + line.strip()

        return None

    def flush(self):
        finished = self.current
        self.current = None
        return finished