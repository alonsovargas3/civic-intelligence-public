"""Acquire TCAD export files: download (browser headers), checksum, locate PROP.TXT.

TCAD serves the export zips at https://traviscad.org/wp-content/largefiles/<name>.zip but
requires a browser User-Agent and a Referer header (the bare directory index 403s). Files are
large (the 2025 certified export is ~465 MB), so download streams to disk.
"""
import hashlib
import logging
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import requests

log = logging.getLogger("atx.tcad.acquire")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://traviscad.org/publicinformation/",
}

# Hosts we expect TCAD exports to come from. download_export refuses other hosts
# unless explicitly overridden, so a stray/typo'd URL can't be fetched + extracted.
_ALLOWED_HOSTS = ("traviscad.org",)


def check_host(url: str, allow_any_host: bool = False) -> None:
    """Raise ValueError unless `url`'s host is an allowed TCAD host.

    A host matches if it equals an allowed host or is a subdomain of one (so
    www.traviscad.org is fine, but traviscad.org.evil.com is not).
    """
    if allow_any_host:
        return
    host = (urlparse(url).hostname or "").lower()
    for allowed in _ALLOWED_HOSTS:
        if host == allowed or host.endswith("." + allowed):
            return
    raise ValueError(
        f"refusing to download from unexpected host {host!r}; "
        f"allowed: {_ALLOWED_HOSTS}. Pass allow_any_host=True to override."
    )


def staging_paths(workdir: str, year=None, stage: str | None = None):
    """Return (zip_path, extract_dir) for a download.

    When year+stage are given, staging is namespaced per roll
    (workdir/<year>_<stage>/...) so re-acquiring a different roll never overwrites
    a prior one. Without them, falls back to the legacy shared paths.
    """
    base = Path(workdir)
    if year is not None and stage:
        base = base / f"{year}_{stage}"
    return str(base / "export.zip"), str(base / "extracted")


def sha256_file(path: str, chunk: int = 1 << 20) -> str:
    """Streaming SHA-256 of a file (used as the load idempotency key)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def download_export(url: str, dest: str, timeout: int = 600,
                    allow_any_host: bool = False) -> str:
    """Stream a TCAD export zip to dest. Returns dest. Raises on HTTP >= 400.

    Refuses hosts outside the TCAD allowlist unless allow_any_host=True.
    """
    check_host(url, allow_any_host=allow_any_host)
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, headers=_HEADERS, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                if chunk:
                    f.write(chunk)
    log.info("downloaded %s -> %s (%d bytes)", url, dest, dest_path.stat().st_size)
    return str(dest_path)


def unzip(zip_path: str, dest_dir: str) -> str:
    """Safely extract a zip to dest_dir, returning dest_dir.

    Guards against zip-slip: any member whose resolved path escapes dest_dir
    (via '../' or an absolute path) raises ValueError before anything is written.
    """
    dest = Path(dest_dir).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        for member in z.namelist():
            target = (dest / member).resolve()
            if target != dest and dest not in target.parents:
                raise ValueError(
                    f"refusing zip member {member!r}: escapes extraction dir {dest}"
                )
        z.extractall(dest)
    return dest_dir


def find_prop_file(unzipped_dir: str) -> str:
    """Locate the Property file (PROP.TXT / APPRAISAL_INFO.TXT) in an extracted export.

    Texas EARS exports name it APPRAISAL_INFO.TXT or PROP.TXT depending on vintage; match
    case-insensitively on either, preferring the largest match (the real data file).
    """
    candidates = []
    for p in Path(unzipped_dir).rglob("*"):
        if not p.is_file():
            continue
        n = p.name.upper()
        if n in ("PROP.TXT", "APPRAISAL_INFO.TXT"):
            candidates.append(p)
    if not candidates:
        raise FileNotFoundError(
            f"no PROP.TXT / APPRAISAL_INFO.TXT under {unzipped_dir}"
        )
    return str(max(candidates, key=lambda p: p.stat().st_size))


def acquire_prop_file(url: str, workdir: str, year=None, stage: str | None = None,
                      allow_any_host: bool = False) -> str:
    """Download a TCAD export zip, extract it, and return the PROP file path.

    Chains download_export -> unzip -> find_prop_file. When year+stage are given the
    staging is namespaced per roll (workdir/<year>_<stage>/...) so re-acquiring a
    different roll never overwrites a prior one. The module-level names are looked up
    at call time so tests can monkeypatch each step.
    """
    zip_dest, extract_dir = staging_paths(workdir, year, stage)
    zip_path = download_export(url, zip_dest, allow_any_host=allow_any_host)
    extracted = unzip(zip_path, extract_dir)
    return find_prop_file(extracted)
