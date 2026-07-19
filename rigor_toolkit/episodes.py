"""
rigor_toolkit.episodes — overlap-collapse dedup.

Two collapse rules, both extracted from working, published tests:

collapse_within_series (the within-stream rule): same-label predictions
whose start falls inside the current episode's window collapse into one
episode. Merging is only ever attempted against the MOST RECENT episode
of the same series — an opposite-label prediction always opens a new
episode, even inside the window. This is byte-for-byte the rule used by
the Wikipedia and Kalshi cross-domain tests.

collapse_across_groups (the correlated-streams rule): after the within-
series pass, same-label episodes on DIFFERENT series that share a group
id (e.g. two strikes of the same event) and have overlapping windows
collapse into one — two same-direction bets on one underlying are one
bet, not two. Merging is attempted against EVERY earlier episode of the
group (first match wins). Episodes with group=None never merge here.
Extracted from the Kalshi test's cross-strike layer.

anchor="start" (default): the window is [episode start, start + horizon]
    — the stricter rule both published tests used.
anchor="last": the window extends as predictions merge (measured from
    the most recently merged prediction) — the chained join evidence.py
    uses for live signal-days (EPISODE_JOIN_GAP_DAYS). Provided so that
    consumer can adopt this package without changing its semantics.

Inputs must be time-ordered within each series; episodes are emitted in
first-seen order (collapse_across_groups stable-sorts by time first,
matching the original implementation).

`horizon` must be addable to whatever `time()` returns: an int/float for
bar indices, a timedelta for datetimes.
"""

from .core import Episode


def collapse_within_series(predictions, horizon, *, time=None,
                           anchor="start"):
    if time is None:
        time = lambda p: p.ts
    if anchor not in ("start", "last"):
        raise ValueError("anchor must be 'start' or 'last'")
    episodes, last_by_series = [], {}
    for p in predictions:
        ep = last_by_series.get(p.series)
        if ep is not None and ep.label == p.label \
                and time(p) <= ep.meta_anchor + horizon:
            ep.n_merged += 1
            if anchor == "last":
                ep.meta_anchor = time(p)
            continue
        ep = Episode(prediction=p)
        ep.meta_anchor = time(p)
        episodes.append(ep)
        last_by_series[p.series] = ep
    for ep in episodes:
        del ep.meta_anchor
    return episodes


def collapse_across_groups(episodes, horizon, *, time=None,
                           anchor="start"):
    if time is None:
        time = lambda e: e.prediction.ts
    if anchor not in ("start", "last"):
        raise ValueError("anchor must be 'start' or 'last'")
    out, by_group = [], {}
    for e in sorted(episodes, key=time):          # stable
        g = e.prediction.group
        if g is not None:
            merged = False
            for prev in by_group.setdefault(g, []):
                if prev.label == e.label \
                        and time(e) <= prev.meta_anchor + horizon:
                    prev.n_merged += e.n_merged + 1
                    if anchor == "last":
                        prev.meta_anchor = time(e)
                    merged = True
                    break
            if merged:
                continue
            e.meta_anchor = time(e)
            by_group[g].append(e)
        out.append(e)
    for e in out:
        if hasattr(e, "meta_anchor"):
            del e.meta_anchor
    return out
