"""
rigor_toolkit.prereg — deterministic pre-registration commitments.

Locks a hypothesis specification to a hash before evaluation begins, so a
later disclosure can be verified byte-for-byte against exactly what existed
at commit time. This is the discipline the whole attestation protocol rests
on: parameters and decision rules fixed BEFORE the run, provably.

What this module is honest about, in the manifest itself:

  * A commitment proves a spec EXISTED at time T. It does not run or verify
    the model's code, and it cannot see specs the identity tested and
    discarded off-ledger. Those are different mechanisms (streamed signed
    predictions; the family-size / multiple-comparison correction in
    rigor_toolkit.multi_test). A hash is necessary, never sufficient.

  * timestamp_utc is SELF-REPORTED by the local clock. It carries no
    third-party weight until commitment_id is anchored to an external
    immutable timestamp (OpenTimestamps/Bitcoin, or a public append-only
    log). The tool emits the anchor target; it does not pretend the local
    file is trustworthy on its own.

Determinism is the entire value proposition, so canonicalization is exact
and frozen: identical specs yield identical hashes across machines, OSes,
Python builds and terminal encodings. The frozen form is pinned by a
golden-hash self-test — it must NEVER change, because a changed canonical
form silently invalidates every commitment ever made.

  * strings NFC-normalized (macOS NFD vs Linux NFC would otherwise hash
    apart)
  * output pure ASCII (ensure_ascii), so no BOM/encoding ambiguity
  * keys sorted, separators tight (no incidental whitespace)
  * NaN / Infinity rejected (not valid JSON, not portable)
  * int and float are distinct by design (20 and 20.0 are different
    commitments — a user who wrote 20.0 meant a float parameter)

stdlib only.
"""

import argparse
import hashlib
import json
import sys
import unicodedata
from datetime import datetime, timezone
from typing import Any, Optional

__all__ = [
    "BOUNDARY",
    "canonicalize",
    "spec_hash",
    "build_manifest",
    "verify_spec",
    "verify_manifest",
]

MANIFEST_VERSION = 1

BOUNDARY = (
    "This commitment proves a hypothesis specification existed at time T. "
    "It does not execute or verify model code, nor does it guarantee "
    "off-ledger pre-selection did not occur."
)

BOUNDARY_NOTES = [
    "timestamp_utc is self-reported by the committing host's clock. It "
    "carries no third-party weight until commitment_id is anchored to an "
    "external immutable timestamp (e.g. OpenTimestamps/Bitcoin or a public "
    "append-only log). Anchor commitment_id — not this file, which is "
    "locally rewritable.",
    "A single commitment says nothing about how many OTHER specs the same "
    "identity committed. Correcting for that family is a separate step "
    "(rigor_toolkit.multi_test); a lone hash cannot detect seed-shopping "
    "across sibling commitments.",
    "For a BLINDED commitment, publish only spec_hash / commitment_id at "
    "commit time and withhold this manifest (which contains canonical_spec) "
    "until disclosure.",
]


# ── canonicalization (frozen — see golden-hash self-test) ─────────────────

def _key_to_str(k: Any) -> str:
    """Deterministic dict-key stringification. JSON keys are strings; we
    fix the conversion for the common scalar keys and reject the rest so
    the canonical form is never ambiguous."""
    if isinstance(k, str):
        return unicodedata.normalize("NFC", k)
    if isinstance(k, bool):                 # before int: bool is an int
        return "true" if k else "false"
    if k is None:
        return "null"
    if isinstance(k, int):
        return str(k)
    raise TypeError(
        f"unsupported dict key type {type(k).__name__!r}; keys must be "
        "str, int, bool or None for a deterministic commitment")


def _canon(obj: Any) -> Any:
    """Recursively normalize a JSON-shaped value into canonical Python:
    NFC strings, validated finite numbers, string keys, tuples as lists."""
    if isinstance(obj, str):
        return unicodedata.normalize("NFC", obj)
    if isinstance(obj, bool):               # before int
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        if obj != obj or obj in (float("inf"), float("-inf")):
            raise ValueError(
                "non-finite float (NaN/Infinity) in spec; not JSON-portable")
        return obj
    if obj is None:
        return None
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            ks = _key_to_str(k)
            if ks in out:
                raise ValueError(
                    f"duplicate key after normalization: {ks!r}")
            out[ks] = _canon(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [_canon(v) for v in obj]
    raise TypeError(
        f"unsupported type in spec: {type(obj).__name__!r}; a spec must be "
        "JSON-shaped (dict/list/str/int/float/bool/None)")


def canonicalize(spec: Any) -> str:
    """Canonical JSON string for `spec`. Pure function of the value: the
    same spec always produces the same string, on any machine."""
    normalized = _canon(spec)
    return json.dumps(normalized, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False)


def spec_hash(spec: Any) -> str:
    """SHA-256 (hex) of the canonical spec — the hypothesis fingerprint."""
    return hashlib.sha256(canonicalize(spec).encode("ascii")).hexdigest()


# ── manifest ──────────────────────────────────────────────────────────────

def build_manifest(spec: Any,
                   identity_key: Optional[str] = None,
                   timestamp: Optional[str] = None) -> dict:
    """The commitment payload.

    spec_hash       fingerprint of the hypothesis (covers the spec only)
    canonical_spec  the exact canonical string the hash is taken over
    timestamp_utc   ISO 8601 UTC; SELF-REPORTED (see boundary_notes)
    identity_key    optional identity/public-key string, or None
    commitment_id   SHA-256 binding spec_hash + timestamp + identity — THIS
                    is the value to anchor externally; altering any bound
                    field changes it
    boundary        the honesty boundary, stamped verbatim
    """
    canon = canonicalize(spec)
    sh = hashlib.sha256(canon.encode("ascii")).hexdigest()
    ts = timestamp if timestamp is not None else \
        datetime.now(timezone.utc).isoformat()
    # commitment_id binds the fields that must not be silently altered
    core = {"spec_hash": sh, "timestamp_utc": ts,
            "identity_key": identity_key}
    commitment_id = hashlib.sha256(
        canonicalize(core).encode("ascii")).hexdigest()
    return {
        "rigor_prereg_version": MANIFEST_VERSION,
        "spec_hash": sh,
        "canonical_spec": canon,
        "timestamp_utc": ts,
        "identity_key": identity_key,
        "commitment_id": commitment_id,
        "boundary": BOUNDARY,
        "boundary_notes": list(BOUNDARY_NOTES),
        "anchor_target": commitment_id,
        "anchor_instructions": (
            "Submit anchor_target to an external immutable timestamp "
            "(OpenTimestamps: `ots stamp`, or post to a public append-only "
            "log). The external proof, not this file, is what dates the "
            "commitment."),
    }


def verify_spec(spec: Any, expected_hash: str) -> bool:
    """True iff `spec` canonicalizes to `expected_hash`."""
    return spec_hash(spec) == expected_hash.strip().lower()


def verify_manifest(manifest: dict, spec: Any = None) -> dict:
    """Check a manifest's internal consistency, and optionally that a
    disclosed `spec` matches it. Returns a report dict with per-check bools
    and an overall `ok`. Never raises on a mismatch — a failed check is
    data, not an exception."""
    checks = {}
    canon = manifest.get("canonical_spec")
    claimed = (manifest.get("spec_hash") or "").lower()

    # 1. the manifest's own canonical_spec must hash to its spec_hash
    if canon is not None:
        recomputed = hashlib.sha256(canon.encode("ascii")).hexdigest()
        checks["spec_hash_matches_canonical_spec"] = (recomputed == claimed)
    else:
        checks["spec_hash_matches_canonical_spec"] = None   # blinded

    # 2. commitment_id must bind the current spec_hash/timestamp/identity
    core = {"spec_hash": manifest.get("spec_hash"),
            "timestamp_utc": manifest.get("timestamp_utc"),
            "identity_key": manifest.get("identity_key")}
    recomputed_cid = hashlib.sha256(
        canonicalize(core).encode("ascii")).hexdigest()
    checks["commitment_id_binds_fields"] = (
        recomputed_cid == (manifest.get("commitment_id") or "").lower())

    # 3. a re-canonicalization of canonical_spec must be a fixed point
    if canon is not None:
        try:
            checks["canonical_spec_is_fixed_point"] = (
                canonicalize(json.loads(canon)) == canon)
        except Exception:
            checks["canonical_spec_is_fixed_point"] = False

    # 4. optional: a disclosed spec matches the committed hash
    if spec is not None:
        checks["disclosed_spec_matches"] = verify_spec(spec, claimed)

    ok = all(v for v in checks.values() if v is not None)
    return {"ok": ok, "checks": checks}


# ── CLI ────────────────────────────────────────────────────────────────────

def _load_spec(path: Optional[str]) -> Any:
    raw = sys.stdin.read() if path in (None, "-") else \
        open(path, encoding="utf-8").read()
    return json.loads(raw)


def _cmd_commit(args) -> int:
    spec = _load_spec(args.spec)
    manifest = build_manifest(spec, identity_key=args.identity,
                              timestamp=args.timestamp)
    if args.blind:
        manifest = dict(manifest)
        manifest.pop("canonical_spec", None)
        manifest["blinded"] = True
    text = json.dumps(manifest, indent=2, ensure_ascii=False)
    if args.out in (None, "-"):
        print(text)
    else:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text + "\n")
        print(f"spec_hash     {manifest['spec_hash']}")
        print(f"commitment_id {manifest['commitment_id']}")
        print(f"wrote {args.out}")
        print(f"\n{BOUNDARY}")
        print("\nAnchor commitment_id externally — the local file is not a "
              "trusted timestamp.")
    return 0


def _cmd_verify(args) -> int:
    spec = _load_spec(args.spec) if args.spec else None
    if args.manifest:
        manifest = json.loads(open(args.manifest, encoding="utf-8").read())
        report = verify_manifest(manifest, spec=spec)
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 1
    if args.hash and spec is not None:
        ok = verify_spec(spec, args.hash)
        print(f"spec_hash {spec_hash(spec)}")
        print("MATCH" if ok else "MISMATCH")
        return 0 if ok else 1
    print("verify needs --manifest, or --spec with --hash", file=sys.stderr)
    return 2


def _cmd_canon(args) -> int:
    spec = _load_spec(args.spec)
    print(canonicalize(spec))
    return 0


def _cmd_selftest(args) -> int:
    for _ in selftest(verbose=True):
        pass
    print(f"\nall {len(selftest())} prereg self-tests passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="rigor-prereg",
        description="Deterministic pre-registration commitments. A hash "
                    "proves a spec existed at time T; it does not run code "
                    "or rule out off-ledger pre-selection.")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("commit", help="hash a spec and emit a manifest")
    c.add_argument("spec", nargs="?", default="-",
                   help="path to a JSON spec file, or - for stdin")
    c.add_argument("--identity", default=None,
                   help="identity / public-key string (optional)")
    c.add_argument("--out", default="prereg_manifest.json",
                   help="manifest output path, or - for stdout")
    c.add_argument("--timestamp", default=None,
                   help="override timestamp_utc (ISO 8601); default now UTC")
    c.add_argument("--blind", action="store_true",
                   help="omit canonical_spec (publish hash/id only)")
    c.set_defaults(func=_cmd_commit)

    v = sub.add_parser("verify", help="verify a manifest and/or a spec")
    v.add_argument("--manifest", default=None, help="manifest JSON to check")
    v.add_argument("--spec", default=None,
                   help="disclosed spec file to match against the hash")
    v.add_argument("--hash", default=None,
                   help="expected spec_hash (with --spec)")
    v.set_defaults(func=_cmd_verify)

    k = sub.add_parser("canon", help="print the canonical spec string")
    k.add_argument("spec", nargs="?", default="-")
    k.set_defaults(func=_cmd_canon)

    s = sub.add_parser("selftest", help="run canonicalization self-tests")
    s.set_defaults(func=_cmd_selftest)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


# ── golden-hash self-test: the canonical form is FROZEN ───────────────────

# The hash of GOLDEN_SPEC must never change. If a refactor changes it, the
# canonical form has drifted and every prior commitment is now unverifiable
# — treat a failure here as a breaking, versioned event, never a fixup.
GOLDEN_SPEC = {
    "hypothesis": "phase-space recurrence predicts next-bar direction",
    "params": {"k": 20, "alpha": 0.05, "hold": 10},
    "assets": ["BTC", "SOL"],
    "baselines": ["persistence", "always-majority"],
}
GOLDEN_HASH = "fe72779603c38c5919ef1f9ca99c811cab70bda9729502e054874927894455d6"


def selftest(verbose: bool = False) -> list:
    """Assert canonicalization determinism and the frozen golden hash."""
    passed = []

    def ok(msg):
        passed.append(msg)
        if verbose:
            print(f"  [ok] {msg}")

    # 1. Key-order invariance: insertion order must not matter.
    a = {"b": 1, "a": 2, "c": {"y": 1, "x": 2}}
    b = {"c": {"x": 2, "y": 1}, "a": 2, "b": 1}
    assert spec_hash(a) == spec_hash(b), "key order changed the hash"
    ok("key-order invariance (nested)")

    # 2. Whitespace invariance: pretty vs minified JSON of one spec.
    pretty = '{\n  "a": 1,\n  "b": [1, 2, 3]\n}'
    minif = '{"b":[1,2,3],"a":1}'
    assert spec_hash(json.loads(pretty)) == spec_hash(json.loads(minif))
    ok("input-whitespace invariance")

    # 3. Idempotence: canonicalize is a fixed point through a JSON round-trip.
    nested = {"z": [3, {"q": [1, 2]}, "t"], "a": {"m": 1, "k": 2}}
    canon = canonicalize(nested)
    assert canonicalize(json.loads(canon)) == canon, "not a fixed point"
    ok("canonicalize is a JSON round-trip fixed point")

    # 4. NFC: decomposed vs precomposed unicode hash identically.
    decomposed = {"name": "café"}     # e + combining acute
    precomposed = {"name": "café"}     # é
    assert spec_hash(decomposed) == spec_hash(precomposed), "NFC failed"
    ok("unicode NFC normalization (café NFD == NFC)")

    # 5. List order IS significant (lists are ordered data).
    assert spec_hash([1, 2, 3]) != spec_hash([3, 2, 1])
    ok("list order is significant")

    # 6. int vs float are distinct commitments (by design).
    assert spec_hash({"k": 20}) != spec_hash({"k": 20.0})
    ok("int 20 and float 20.0 are distinct")

    # 7. tuple canonicalizes as list.
    assert spec_hash({"v": (1, 2)}) == spec_hash({"v": [1, 2]})
    ok("tuple canonicalizes identically to list")

    # 8. Float determinism is honest: 0.1+0.2 != 0.3 (different floats).
    assert spec_hash({"x": 0.1 + 0.2}) != spec_hash({"x": 0.3})
    assert spec_hash({"x": 0.3}) == spec_hash({"x": 0.3})
    ok("float determinism: 0.1+0.2 distinct from 0.3, 0.3 stable")

    # 9. NaN / Infinity are rejected.
    for bad in (float("nan"), float("inf"), float("-inf")):
        try:
            canonicalize({"x": bad})
            raise AssertionError("non-finite float not rejected")
        except ValueError:
            pass
    ok("NaN / Infinity rejected")

    # 10. Unsupported types rejected.
    try:
        canonicalize({"s": {1, 2, 3}})
        raise AssertionError("set not rejected")
    except TypeError:
        pass
    ok("unsupported type (set) rejected")

    # 11. Deterministic key stringification and no collisions.
    assert spec_hash({1: "a"}) == spec_hash({"1": "a"})   # int key -> "1"
    try:
        canonicalize({1: "a", "1": "b"})
        raise AssertionError("post-normalization key collision not caught")
    except ValueError:
        pass
    ok("dict keys stringified deterministically; collisions caught")

    # 12. Manifest binds fields and self-verifies; tampering is detected.
    man = build_manifest(GOLDEN_SPEC, identity_key="pubkey_A",
                         timestamp="2026-07-20T00:00:00+00:00")
    rep = verify_manifest(man, spec=GOLDEN_SPEC)
    assert rep["ok"], rep
    tampered = dict(man)
    tampered["timestamp_utc"] = "2020-01-01T00:00:00+00:00"
    assert not verify_manifest(tampered)["ok"], "timestamp tamper undetected"
    ok("manifest self-verifies; commitment_id detects field tampering")

    # 13. Same spec + different timestamp -> same spec_hash, different id.
    m1 = build_manifest(GOLDEN_SPEC, timestamp="2026-01-01T00:00:00+00:00")
    m2 = build_manifest(GOLDEN_SPEC, timestamp="2026-02-01T00:00:00+00:00")
    assert m1["spec_hash"] == m2["spec_hash"]
    assert m1["commitment_id"] != m2["commitment_id"]
    ok("spec_hash time-invariant; commitment_id time-bound")

    # 14. THE FROZEN CANONICAL FORM. Must never change.
    assert spec_hash(GOLDEN_SPEC) == GOLDEN_HASH, (
        "GOLDEN HASH CHANGED — the canonical form drifted and every prior "
        "commitment is now unverifiable. This is a breaking change, not a "
        f"fixup. got {spec_hash(GOLDEN_SPEC)}")
    ok("golden hash frozen (canonical form unchanged)")

    return passed


if __name__ == "__main__":
    sys.exit(main())
