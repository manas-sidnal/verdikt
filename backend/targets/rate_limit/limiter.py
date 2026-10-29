class RateLimiter:
    """Sliding-window limiter: at most `limit` calls per `window` seconds."""

    def __init__(self, limit, window, clock):
        self.limit = limit
        self.window = window
        self.clock = clock
        self.hits = []

    def allow(self):
        now = self.clock()
        self.hits = [t for t in self.hits if now - t < self.window]
        if len(self.hits) > self.limit:
            return False
        self.hits.append(now)
        return True
