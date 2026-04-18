from collections import deque


class DuplicateFilter:
    def __init__(self, max_remembered):
        # deque(maxlen=0) breaks eviction (popleft on empty); clamp for safety.
        cap = int(max_remembered) if max_remembered is not None else 2000
        cap = max(1, cap)
        self.seen = set()
        self.queue = deque(maxlen=cap)

    def is_new(self, key):
        if key in self.seen:
            return False

        maxlen = self.queue.maxlen
        if maxlen and len(self.queue) == maxlen:
            old = self.queue.popleft()
            self.seen.remove(old)

        self.queue.append(key)
        self.seen.add(key)
        return True
