import pytest

from limiter import RateLimiter


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_first_request_allowed():
    assert RateLimiter(1, 10, Clock()).allow() is True


def test_allows_up_to_limit():
    limiter = RateLimiter(3, 10, Clock())
    assert [limiter.allow() for _ in range(3)] == [True, True, True]


def test_blocks_over_limit():
    limiter = RateLimiter(3, 10, Clock())
    results = [limiter.allow() for _ in range(4)]
    assert results == [True, True, True, False]


def test_window_expires():
    clock = Clock()
    limiter = RateLimiter(2, 10, clock)
    assert limiter.allow() and limiter.allow()
    clock.t = 5
    assert limiter.allow() is False
    clock.t = 10
    assert limiter.allow() is True


def test_invalid_limit_rejected():
    with pytest.raises(ValueError):
        RateLimiter(0, 10, Clock())
