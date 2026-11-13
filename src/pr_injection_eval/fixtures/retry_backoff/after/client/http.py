import time
import urllib.error
import urllib.request

MAX_ATTEMPTS = 3
BASE_DELAY = 0.5


def backoff_delay(attempt: int) -> float:
    """Seconds to wait after failed attempt number `attempt` (0-based)."""
    return BASE_DELAY * 2**attempt


def fetch(url: str, timeout: float = 5.0) -> bytes:
    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                return response.read()
        except urllib.error.URLError as error:
            last_error = error
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(backoff_delay(attempt))
    raise RuntimeError(f"Giving up on {url}") from last_error
