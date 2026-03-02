from collections import deque

class DuplicateFilter:
    def __init__(self, max_remembered):
        self.seen = set()
        self.queue = deque(maxlen=max_remembered)

    def is_new(self, key):
        if key in self.seen:
            return False

        if len(self.queue) == self.queue.maxlen:
            old = self.queue.popleft()
            self.seen.remove(old)

        self.queue.append(key)
        self.seen.add(key)
        return True