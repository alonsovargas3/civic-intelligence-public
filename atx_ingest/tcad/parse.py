"""Fixed-width parsing for TCAD export files, driven by a layout dictionary.

Layout `start`/`end` are 1-indexed inclusive byte positions (as printed in TCAD's Export
Layout doc), so a field maps to Python slice [start-1 : end]. Values are right-trimmed of
spaces; `type: "int"` fields parse to int (blank -> None); everything else stays str.
"""
import logging

log = logging.getLogger("atx.tcad.parse")


def parse_fixed_width(line: str, layout: dict) -> dict:
    rec = {}
    for f in layout["fields"]:
        raw = line[f["start"] - 1 : f["end"]]
        val = raw.rstrip()
        if f.get("type") == "int":
            val = val.strip()
            rec[f["name"]] = int(val) if val else None
        else:
            rec[f["name"]] = val
    return rec


def iter_records(path: str, layout: dict):
    """Yield one parsed dict per non-empty line of a fixed-width file.

    If the layout declares a `record_length`, warn (once) when any line's length
    doesn't match — a truncated download or wrong layout would otherwise parse
    silently with misaligned field values. Parsing still proceeds (we yield the
    row) so a single odd line doesn't abort a multi-million-row load.
    """
    enc = layout.get("encoding", "latin-1")
    expected = layout.get("record_length")
    warned = False
    with open(path, encoding=enc) as fh:
        for line in fh:
            line = line.rstrip("\n").rstrip("\r")
            if not line:
                continue
            if expected and not warned and len(line) != expected:
                log.warning(
                    "%s: record length %d != expected %d (truncated file or wrong "
                    "layout?); field offsets may be misaligned",
                    path, len(line), expected,
                )
                warned = True
            yield parse_fixed_width(line, layout)
