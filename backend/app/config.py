"""Application settings, loaded from environment / .env.

Defaults are tuned for a zero-infrastructure development machine: SQLite, a
placeholder signing key, debug on, docs open. Every one of those is wrong in
production, so `ENVIRONMENT=production` turns this class into a gate — see
`_production_guard`, which refuses to construct settings that would boot an
insecure server rather than logging a warning nobody reads.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent

# The value shipped in .env.example. Booting production with it means every
# JWT this server issues can be forged by anyone who has read the repository.
PLACEHOLDER_SECRET = "change-me-in-production"

# Long enough that a leaked token cannot be brute-forced offline. 48 random
# bytes of `secrets.token_urlsafe` lands at 64 characters.
MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- app ---
    app_name: str = "SkillAtlas API"
    environment: str = "development"
    debug: bool = True

    # Interactive docs publish the whole API surface, including every request
    # schema. Useful locally, an inventory for an attacker in production.
    # `None` means "follow the environment"; set it explicitly to override.
    enable_docs: bool | None = None

    # --- database ---
    # SQLite by default so the stack runs with zero infrastructure.
    # Point DATABASE_URL at Postgres to switch; no code changes required.
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'skillatlas.db').as_posix()}"
    # Ignored on SQLite, which has no connection pool worth tuning.
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_recycle_sec: int = 1800

    # --- auth ---
    secret_key: str = PLACEHOLDER_SECRET
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # --- rate limiting ---
    # Counts are per client per window, enforced in app/middleware/ratelimit.py.
    rate_limit_enabled: bool = True
    rate_limit_auth_per_minute: int = 10
    rate_limit_tutor_per_minute: int = 20
    rate_limit_default_per_minute: int = 240
    rate_limit_upload_per_hour: int = 30
    # Trust `X-Forwarded-For` only when something you control sets it. Behind a
    # load balancer this must be on or every client shares the proxy's address;
    # exposed directly it must be off or a client spoofs the header and every
    # limit becomes unenforceable.
    trust_proxy_headers: bool = False

    # --- content ---
    # Every track is publishable: `scripts/strip_imported_prose.py` removed the
    # third-party prose that made the imported ones a licence problem, leaving
    # a syllabus and links that are ours or are facts. So this defaults to
    # off — all 92 tracks ship.
    #
    # Turn it on to serve *only* the fully-written tracks, hiding the outlines.
    # That is a product choice about what users should see, not a legal one.
    # See app/services/publishing.py.
    publish_authored_only: bool = False

    # --- cors ---
    # The frontend talks to us through its own Next.js BFF (same-origin), so
    # browsers never call this API cross-origin in normal operation. These
    # origins exist for local tooling and direct /docs usage.
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # --- database pooling (Postgres only; ignored on SQLite) ---
    # Deliberately small: see the reasoning in app/database.py. Raise
    # DB_POOL_SIZE only when running one long-lived server rather than many
    # short-lived function instances.
    db_pool_size: int = 2
    db_max_overflow: int = 3
    db_pool_recycle_sec: int = 240
    db_connect_timeout_sec: int = 10

    # --- AI tutor: which provider answers ---
    # "auto" picks OpenRouter when a key is set and Ollama otherwise, which is
    # the right default in both places: a laptop with Ollama running and no key
    # keeps working offline, and a deployment with a key set never silently
    # falls back to a localhost port that does not exist there.
    # Force one with LLM_PROVIDER=ollama | openrouter | retrieval.
    llm_provider: Literal["auto", "ollama", "openrouter", "retrieval"] = "auto"

    # --- ollama (local AI tutor) ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen2.5:7b"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_timeout_sec: int = 180

    # --- openrouter (hosted AI tutor) ---
    # Empty by default: absence of a key is how "not configured" is expressed,
    # and is what `llm_provider="auto"` tests. Set OPENROUTER_API_KEY in the
    # environment — never in code, and never in a tracked file.
    openrouter_api_key: str = ""
    # A `:free` model, chosen by measurement rather than parameter count.
    # Among the free catalogue it answered a grounded tutor question correctly
    # in 1.7s and, critically, put its chain of thought in the separate
    # `reasoning` field rather than in `content`. Two plausible-looking
    # alternatives failed exactly there: `nemotron-3.5-lightning:free` printed
    # "Here's a thinking process:" into the answer and ran out of tokens before
    # reaching one, and `nemotron-3-ultra-550b-a55b:free` took 38s for the same
    # question. `z-ai/glm-5.2:free` returned upstream 429s on every attempt.
    openrouter_model: str = "nvidia/nemotron-3-super-120b-a12b:free"
    # Tried in order when the primary is rate-limited or unavailable, using
    # OpenRouter's own model-routing. Free pools are shared and 429 often, so
    # on the free tier this is the difference between a tutor that answers and
    # one that shrugs. Keep every entry `:free` — a paid id here would bill.
    # Ordered by how well each stood up in the same test: the nano model was
    # clean and quick (2.1s), the ultra model correct but slow (38s), so it is
    # last — a slow answer still beats no answer.
    openrouter_fallback_models: list[str] = [
        "nvidia/nemotron-3-nano-30b-a3b:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
    ]
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_timeout_sec: int = 120
    # Optional attribution headers OpenRouter shows on its leaderboards.
    openrouter_site_url: str = ""
    openrouter_app_name: str = "SkillAtlas"

    # --- gamification ---
    xp_per_hour: int = 10

    # --- logging ---
    # JSON lines in production so a log shipper can parse them; human-readable
    # locally. `None` follows the environment.
    log_json: bool | None = None
    log_level: str = "INFO"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    @property
    def docs_enabled(self) -> bool:
        if self.enable_docs is not None:
            return self.enable_docs
        return not self.is_production

    @property
    def authored_only(self) -> bool:
        return self.publish_authored_only

    @property
    def json_logs(self) -> bool:
        return self.log_json if self.log_json is not None else self.is_production

    @model_validator(mode="after")
    def _production_guard(self) -> "Settings":
        """Refuse to start a production server that is insecure by default.

        Every check here is for a setting whose *development* default is
        actively dangerous once the process is reachable from the internet.
        Failing to construct is deliberate: a warning at boot is invisible in a
        container that restarts, and each of these is exploitable rather than
        untidy.
        """
        if not self.is_production:
            return self

        problems: list[str] = []

        if self.secret_key == PLACEHOLDER_SECRET:
            problems.append(
                "SECRET_KEY is still the placeholder from .env.example, so any "
                "reader of the repository can forge tokens for any account. "
                'Generate one with: python -c "import secrets; '
                'print(secrets.token_urlsafe(48))"'
            )
        elif len(self.secret_key) < MIN_SECRET_LENGTH:
            problems.append(
                f"SECRET_KEY is {len(self.secret_key)} characters; "
                f"{MIN_SECRET_LENGTH} is the minimum."
            )

        if self.debug:
            problems.append(
                "DEBUG is on, which returns tracebacks to clients. Set DEBUG=false."
            )

        if any(origin.strip() == "*" for origin in self.cors_origins):
            problems.append(
                "CORS_ORIGINS contains '*', which cannot be combined with "
                "credentialed requests and would expose the API to any site."
            )

        insecure = [
            origin
            for origin in self.cors_origins
            if origin.startswith("http://")
            and not origin.startswith(("http://localhost", "http://127.0.0.1"))
        ]
        if insecure:
            problems.append(
                f"CORS_ORIGINS contains plaintext origins: {insecure}. "
                "Cookies marked Secure are not sent to them."
            )

        if problems:
            raise ValueError(
                "Refusing to start in production:\n"
                + "\n".join(f"  - {problem}" for problem in problems)
            )

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
