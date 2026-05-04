import time
import anthropic
import anthropic.types
from dotenv import load_dotenv

load_dotenv()

# Maximum number of retry attempts before giving up.
MAX_RETRIES = 3

# Base delay in seconds. Each retry doubles this.
# Retry 1: 2s, Retry 2: 4s, Retry 3: 8s.
BASE_DELAY = 2


def call_with_retry(client: anthropic.Anthropic, **kwargs) -> anthropic.types.Message:
    """
    Wraps client.messages.create() with retry logic and exponential backoff.
    Retries on rate limits, network errors, and server overload (529).
    Raises immediately on client errors (400, 401, 404) — those are your fault,
    not transient, and retrying will not fix them.
    """
    last_exception = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            if "betas" in kwargs:
                betas = kwargs.pop("betas")
                return client.beta.messages.create(betas=betas, **kwargs)
            return client.messages.create(**kwargs)

        except anthropic.RateLimitError as e:
            # Rate limit: too many requests per minute.
            # Always retry with backoff.
            last_exception = e
            if attempt < MAX_RETRIES:
                delay = BASE_DELAY ** (attempt + 1)
                print(f"[Retry] Rate limit hit. Waiting {delay}s before retry {attempt + 1}/{MAX_RETRIES}...")
                time.sleep(delay)

        except anthropic.APIStatusError as e:
            # Server-side error. Only retry on 529 (overloaded).
            # Do not retry on 400/401/404 — those require fixing the request.
            last_exception = e
            if e.status_code == 529 and attempt < MAX_RETRIES:
                delay = BASE_DELAY ** (attempt + 1)
                print(f"[Retry] API overloaded (529). Waiting {delay}s before retry {attempt + 1}/{MAX_RETRIES}...")
                time.sleep(delay)
            else:
                # Non-retryable status code. Raise immediately.
                raise

        except anthropic.APIConnectionError as e:
            # Network error. Retry.
            last_exception = e
            if attempt < MAX_RETRIES:
                delay = BASE_DELAY ** (attempt + 1)
                print(f"[Retry] Connection error. Waiting {delay}s before retry {attempt + 1}/{MAX_RETRIES}...")
                time.sleep(delay)

    # All retries exhausted. Raise the last exception.
    raise last_exception