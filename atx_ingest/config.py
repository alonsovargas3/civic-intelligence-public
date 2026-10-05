"""Settings + the declarative source registry loaded from config/sources.yaml."""
import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES = REPO_ROOT / "config" / "sources.yaml"


@dataclass
class Source:
    dataset_id: str            # Socrata 4x4 id, e.g. "xwdj-i9he"
    name: str                  # human label
    table: str                 # lands in raw_<table>
    cursor_field: str = ":updated_at"   # freshness cursor; override per dataset
    primary_key: str = ":id"            # upsert key (Socrata system row id)
    backfill_since: str | None = None   # ISO ts to start a first pull from
    enabled: bool = True
    page_size: int = 1000
    min_interval_seconds: int = 0       # 0 = poll every pass; >0 throttles this
                                        # source (e.g. crime, a full-republish set)
    kind: str = "socrata"               # "socrata" | "legistar" — selects the client


@dataclass
class Settings:
    database_url: str
    socrata_domain: str
    app_token: str | None
    sources: list[Source]
    legistar_base: str = "https://webapi.legistar.com/v1"
    legistar_client: str = "austintexas"


def load_settings(sources_path: Path | None = None) -> Settings:
    raw = yaml.safe_load((sources_path or DEFAULT_SOURCES).read_text())
    sources = [Source(**s) for s in raw.get("sources", [])]
    return Settings(
        database_url=os.environ.get(
            "DATABASE_URL", "postgresql://atx:atx@localhost:5432/atx_civic"
        ),
        socrata_domain=os.environ.get("SOCRATA_DOMAIN", "data.austintexas.gov"),
        app_token=os.environ.get("SOCRATA_APP_TOKEN") or None,
        sources=sources,
        legistar_base=os.environ.get("LEGISTAR_BASE", "https://webapi.legistar.com/v1"),
        legistar_client=os.environ.get("LEGISTAR_CLIENT", "austintexas"),
    )
