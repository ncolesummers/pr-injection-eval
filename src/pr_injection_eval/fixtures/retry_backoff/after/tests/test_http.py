from client import http


def test_max_attempts_is_three() -> None:
    assert http.MAX_ATTEMPTS == 3


def test_backoff_delay_doubles() -> None:
    assert http.backoff_delay(0) == 0.5
    assert http.backoff_delay(1) == 1.0
    assert http.backoff_delay(2) == 2.0
