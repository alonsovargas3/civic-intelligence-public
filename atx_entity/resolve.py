"""Pure connected-components entity resolver (no DB, no network).

resolve(records) links owner records by exact normalized name OR shared mailing
address (hub addresses suppressed), then assigns each connected component an entity.
"""
import hashlib
from collections import defaultdict
from dataclasses import dataclass, field

from .normalize import addr_key, is_junk_addr, name_kind

DEFAULT_HUB_THRESHOLD = 25


@dataclass
class Entity:
    entity_id: str
    canonical_name: str
    kind: str
    confidence: str          # strong | review
    n_parcels: int
    n_owner_records: int
    name_variants: list
    addr_keys: list


@dataclass
class ParcelLink:
    account_id: str
    entity_id: str
    link_type: str           # name | address | singleton


@dataclass
class Link:
    entity_id: str
    kind: str                # name | address
    value: str
    suppressed: bool
    n_records: int


@dataclass
class ResolveResult:
    entities: dict = field(default_factory=dict)        # entity_id -> Entity
    parcel_links: dict = field(default_factory=dict)    # account_id -> ParcelLink
    links: list = field(default_factory=list)           # list[Link]


class _UF:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:    # path compression
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def resolve(records: list, hub_threshold: int = DEFAULT_HUB_THRESHOLD) -> ResolveResult:
    """Resolve owner records into entities via union-find. Pure / deterministic.

    Each record is a dict with: account_id, owner_name_raw, owner_name_norm, mail_addr.
    Returns a ResolveResult (entities, parcel_links, links-evidence).
    """
    uf = _UF()
    for r in records:
        uf.find(r["account_id"])     # ensure every account is a node

    # --- name edges: group accounts by exact non-blank normalized name ---
    by_name = defaultdict(list)
    for r in records:
        nm = r.get("owner_name_norm") or ""
        if nm:
            by_name[nm].append(r["account_id"])
    name_linked = set()              # account_ids that got at least one name edge
    for nm, accts in by_name.items():
        if len(accts) > 1:
            for a in accts[1:]:
                uf.union(accts[0], a)
            name_linked.update(accts)

    # --- address edges: group by addr_key, suppress hubs/junk ---
    by_addr = defaultdict(list)      # addr_key -> list[account_id]
    addr_names = defaultdict(set)    # addr_key -> distinct names (for hub detection)
    for r in records:
        line1 = (r.get("mail_addr") or {}).get("line1") or ""
        if is_junk_addr(line1):
            continue
        k = addr_key(r.get("mail_addr") or {})
        if not k:
            continue
        by_addr[k].append(r["account_id"])
        addr_names[k].add(r.get("owner_name_norm") or "")

    suppressed_hubs = {}             # addr_key -> n_records (recorded, not used)
    addr_linked = set()
    for k, accts in by_addr.items():
        if len(accts) <= 1:
            continue
        if len(addr_names[k]) > hub_threshold:
            suppressed_hubs[k] = len(accts)      # hub: do NOT union
            continue
        for a in accts[1:]:
            uf.union(accts[0], a)
        addr_linked.update(accts)

    # --- build components ---
    comp = defaultdict(list)         # root -> [records]
    rec_by_acct = {r["account_id"]: r for r in records}
    for acct in rec_by_acct:
        comp[uf.find(acct)].append(rec_by_acct[acct])

    result = ResolveResult()
    for members in comp.values():
        accts = sorted(r["account_id"] for r in members)
        entity_id = hashlib.sha256("|".join(accts).encode()).hexdigest()[:16]

        names = [r["owner_name_raw"] for r in members]
        freq = defaultdict(int)
        for r in members:
            freq[r["owner_name_raw"]] += 1
        canonical = max(freq, key=lambda n: (freq[n], len(n), n))
        kind = name_kind(canonical)

        has_name_edge = any(a in name_linked for a in accts)
        if len(accts) == 1:
            confidence = "strong"
        elif has_name_edge:
            confidence = "strong"
        else:
            confidence = "review"

        akeys = sorted({addr_key(r.get("mail_addr") or {})
                        for r in members if addr_key(r.get("mail_addr") or {})})
        result.entities[entity_id] = Entity(
            entity_id=entity_id, canonical_name=canonical, kind=kind,
            confidence=confidence, n_parcels=len(accts), n_owner_records=len(members),
            name_variants=sorted(set(names)), addr_keys=akeys,
        )
        for a in accts:
            if len(accts) == 1:
                lt = "singleton"
            elif a in name_linked:
                lt = "name"
            else:
                lt = "address"
            result.parcel_links[a] = ParcelLink(a, entity_id, lt)

    # --- link evidence (name groups + address groups incl. suppressed hubs) ---
    for nm, accts in by_name.items():
        if len(accts) > 1:
            eid = result.parcel_links[accts[0]].entity_id
            result.links.append(Link(eid, "name", nm, False, len(accts)))
    for k, accts in by_addr.items():
        if len(accts) > 1:
            eid = result.parcel_links[accts[0]].entity_id
            result.links.append(Link(eid, "address", k, k in suppressed_hubs, len(accts)))

    return result
