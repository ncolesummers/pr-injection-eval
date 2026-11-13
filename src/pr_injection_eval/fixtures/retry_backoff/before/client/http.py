import time
import urllib.error
import urllib.request

MAX_ATTEMPTS = 3


def fetch(url: str, timeout: float = 5.0) -> bytes:
    last_error: Exception | None = None
    for _ in range(MAX_ATTEMPTS):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                return response.read()
        except urllib.error.URLError as error:
            last_error = error
            time.sleep(1.0)
    raise RuntimeError(f"Giving up on {url}") from last_error
