class FakeClient:
    """Stands in for the HTTP client `sync_users` expects."""

    def __init__(self, pages: list[dict]):
        self.pages = pages
        self.calls = []

    def fetch_users(self, page: int) -> dict:
        self.calls.append(page)
        return self.pages[page - 1]


class FakeStore:
    """Stands in for the database `sync_users` writes to."""

    def __init__(self, failures: set | None = None):
        self.saved = []
        self.failures = failures or set()

    def upsert(self, user: dict) -> None:
        if user["id"] in self.failures:
            raise RuntimeError(f"could not save {user['id']}")
        self.saved.append(user)
