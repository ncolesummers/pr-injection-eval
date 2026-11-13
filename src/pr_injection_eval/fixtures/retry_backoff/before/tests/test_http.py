from client import http


def test_max_attempts_is_three() -> None:
    assert http.MAX_ATTEMPTS == 3
