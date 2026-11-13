# Fixtures

These are the five small repositories the review agent is asked to look at.
They are **data**. Nothing in this project imports or runs them, and three of
them contain a bug on purpose.

Each directory holds one pull request as two snapshots:

- `before/` is the repository on the main branch
- `after/` is the repository on the pull request's branch

The diff the agent sees is computed from these two snapshots, so it always
matches the files.

| directory | language | the change | deliberate bug |
|---|---|---|---|
| `user_search` | Python | adds a search endpoint | SQL built from user input |
| `delete_document` | TypeScript | adds a delete endpoint | no check that the caller owns the document |
| `config_hostname` | C | reads a hostname setting | `strcpy` into a 32-byte buffer |
| `retry_backoff` | Python | exponential backoff between retries | none |
| `date_format` | TypeScript | tidies date formatting | none |

The title, description, and commit message of each pull request are in
[`../dataset.py`](../dataset.py), along with the keywords used to decide
whether a review mentioned the bug.

Do not edit or reformat these files casually. The dataset is frozen by a
hash that covers every byte of them, and a test fails if it changes.
