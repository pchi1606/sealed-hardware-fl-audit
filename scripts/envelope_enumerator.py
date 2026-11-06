#!/usr/bin/env python3
# Deposit copy (added 2026-11-05, fix round 11, PX-M3): the section-5
# envelope enumerator. Run from the artifact root:
#   python3 scripts/envelope_enumerator.py AUDIT_MATRIX.md
# Parts 1-3 recompute every printed section-5 cell, the 144-cell
# stacking closure, the amendment axis, and the blind re-scoring's
# contemplated alternatives; Part 4 computes the wider named-alternative
# stacks (both scorer directions) that the printed envelope excludes
# by its stated strict-direction axis.
"""S3 round 10: re-derivation of the section-5 variant family. Parts 1-2
are the round-9 script verbatim (round-8 checks + amendment axis);
Part 3 (new in round 10) derives the blind re-scoring's contemplated
alternatives (R9-NEW-1): the up-flips A3 T->P, A4 T->P, B2 P->V,
G4 T->P that the adjudications in the artifact's
records/DIFF-AND-ADJUDICATIONS.md considered and rejected.

Original round-9 docstring follows.

S3 round 9: re-derivation of the section-5 variant family, extended
with the amendment axis (R8-NEW-1 verification).

Part 1 re-runs the round-8 checks verbatim (all printed current-state
cells + the 144-cell stacking closure over the published matrix).
Part 2 enumerates the amendment axis: the three reverted bases
(A1-only reverted; C3-only pre-split; both reverted = the printed
pre-amendment snapshot) crossed with every stack of the construction/
scorer variants that remains meaningful on each base, and counts the
V=2 cells (the family the round-8 skeptic called "the single sub-3
cell" a misnomer for).

Run: python3 rederive-s5-r9.py <path-to-AUDIT_MATRIX.md>
"""
import itertools
import re
import sys
from collections import Counter

path = sys.argv[1]
rows = {}
for line in open(path):
    m = re.match(r"\| ([A-G]\d+b?) \| ([^|]+) \| ([VPT])\*? \|", line)
    if m:
        rows[m.group(1)] = m.group(3)

assert len(rows) == 27, f"expected 27 as-executed rows, got {len(rows)}: {sorted(rows)}"

ORDER = {"T": 0, "P": 1, "V": 2}


def tally(d):
    c = Counter(d.values())
    return (c["V"], c["P"], c["T"], len(d))


def merge_rule(scores):
    if len(set(scores)) == 1:
        return scores[0]
    if any(s in ("V", "P") for s in scores):
        return "P"
    return "T"


def merge_wl(scores):
    return min(scores, key=lambda s: ORDER[s])


def merged(d, members, new_id, score):
    out = {k: v for k, v in d.items() if k not in members}
    out[new_id] = score
    return out


as_executed = dict(rows)
full = dict(rows)
full["A2b"] = "T"
full["C3c"] = "T"
condensed = {k: v for k, v in full.items() if k not in ("A4", "F2")}

C3 = ["C3", "C3b", "C3c"]
C4 = ["C4", "C4b"]

checks = []


def check(name, got, want):
    ok = got == want
    checks.append((name, got, want, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got {got}, printed {want}")


# ---------- Part 1: round-8 checks, verbatim ----------
check("as-executed base (artifact)", tally(as_executed), (4, 10, 13, 27))
check("full base", tally(full), (4, 10, 15, 29))
check("condensed base", tally(condensed), (4, 10, 13, 27))
va = {k: v for k, v in condensed.items() if k not in ("C4", "F1", "G4")}
check("vendor-assertion subset", tally(va), (2, 10, 12, 24))
check("C3 merge (rule)", tally(merged(condensed, C3, "C3m", merge_rule([condensed[r] for r in C3]))), (4, 10, 11, 25))
check("C4 merge (rule)", tally(merged(condensed, C4, "C4m", merge_rule([condensed[r] for r in C4]))), (3, 11, 12, 26))
g2 = dict(condensed); g2["G2"] = "V"
check("G2 as disclosure", tally(g2), (5, 10, 12, 27))
st = dict(condensed); st["C1"] = "T"; st["C2"] = "T"
check("strict C1/C2", tally(st), (4, 8, 15, 27))
check("WL C3 merge", tally(merged(condensed, C3, "C3m", merge_wl([condensed[r] for r in C3]))), (4, 9, 12, 25))
check("WL C4 merge", tally(merged(condensed, C4, "C4m", merge_wl([condensed[r] for r in C4]))), (3, 10, 13, 26))
both_wl = merged(merged(condensed, C3, "C3m", "T"), C4, "C4m", "T")
check("WL both", tally(both_wl), (3, 9, 12, 24))
drop_c = {k: v for k, v in condensed.items() if k != "G4"}
check("drop non-assertion (condensed)", tally(drop_c), (4, 10, 12, 26))
drop_f = {k: v for k, v in full.items() if k not in ("G4", "F2")}
check("drop non-assertion (full)", tally(drop_f), (4, 10, 13, 27))
b2s = dict(st); b2s["B2"] = "T"
check("B2 flip x strict", tally(b2s), (4, 7, 16, 27))
pre = merged(condensed, C3, "C3m", "T"); pre["A1"] = "P"
check("pre-amendment base (snapshot)", tally(pre), (3, 10, 12, 25))
pre_g2 = dict(pre); pre_g2["G2"] = "V"
check("pre-amendment x G2", tally(pre_g2), (4, 10, 11, 25))
pre_st = dict(pre); pre_st["C1"] = "T"; pre_st["C2"] = "T"
check("pre-amendment x strict", tally(pre_st), (3, 8, 14, 25))
pre_c4 = merged(pre, C4, "C4m", merge_rule([pre[r] for r in C4]))
check("pre-amendment x C4 merge (printed sub-3 cell)", tally(pre_c4), (2, 11, 11, 24))

# Table 9 (kappa exercise) constitution counts are NOT derived from
# AUDIT_MATRIX.md: they are read off the printed 3x3 table itself.
# Published-side marginals: V [2,0,0] = 2; P [0,11,2] = 13; T [0,0,8] = 8
# -> 2/13/8 over 23 as scored. Both disagreements (enumeration, per-round
# row) were published-P vs second-T and both were adopted, moving two
# rows P->T -> 2/11/10 over 23 post-adoption. (Verified by eye against
# the printed table in the manuscript, round 9.)


# ---------- closure over the published matrix (round 8) ----------
def apply_stack(d, c3_mode, c4_mode, g2f, strictf, b2f, dropf):
    d = dict(d)
    if c3_mode == "rule":
        d = merged(d, C3, "C3m", merge_rule([d[r] for r in C3]))
    elif c3_mode == "wl":
        d = merged(d, C3, "C3m", merge_wl([d[r] for r in C3]))
    if c4_mode == "rule":
        d = merged(d, C4, "C4m", merge_rule([d[r] for r in C4]))
    elif c4_mode == "wl":
        d = merged(d, C4, "C4m", merge_wl([d[r] for r in C4]))
    if g2f:
        d["G2"] = "V"
    if strictf:
        d["C1"] = "T"; d["C2"] = "T"
    if b2f:
        d["B2"] = "T"
    if dropf:
        d = {k: v for k, v in d.items() if k != "G4"}
    return d


cells = {}
for combo in itertools.product(("none", "rule", "wl"), ("none", "rule", "wl"),
                               (0, 1), (0, 1), (0, 1), (0, 1)):
    cells[combo] = tally(apply_stack(condensed, *combo))
vs = [t[0] for t in cells.values()]
ps = [t[1] for t in cells.values()]
print(f"\nPublished-matrix closure: {len(cells)} cells; V {min(vs)}-{max(vs)}, P {min(ps)}-{max(ps)}")
check("published closure V range", (min(vs), max(vs)), (3, 5))
check("published closure P range", (min(ps), max(ps)), (6, 11))

# ---------- Part 2: the amendment axis ----------
a1_only = dict(condensed); a1_only["A1"] = "P"
c3_only = merged(condensed, C3, "C3m", "T")
check("A1-only reverted base", tally(a1_only), (3, 11, 13, 27))
check("C3-only pre-split base", tally(c3_only), (4, 9, 12, 25))
check("A1-only x C4 rule merge (skeptic's 2/12/12)", tally(apply_stack(a1_only, "none", "rule", 0, 0, 0, 0)), (2, 12, 12, 26))

amend_cells = []  # (base_name, combo, tally)
for base_name, base, c3_modes in (
    ("A1-only", a1_only, ("none", "rule", "wl")),
    ("C3-only", c3_only, ("none",)),
    ("both-reverted", pre, ("none",)),
):
    for combo in itertools.product(c3_modes, ("none", "rule", "wl"),
                                   (0, 1), (0, 1), (0, 1), (0, 1)):
        amend_cells.append((base_name, combo, tally(apply_stack(base, *combo))))

v2 = [c for c in amend_cells if c[2][0] == 2]
print(f"\nAmendment-axis crosses: {len(amend_cells)} cells; V=2 cells: {len(v2)}")
for base_name, combo, t in sorted(v2):
    print(f"  {base_name}: c3={combo[0]}, c4={combo[1]}, g2={combo[2]}, strict={combo[3]}, "
          f"b2={combo[4]}, dropG4={combo[5]} -> {t}")
v2_tallies = sorted(set(c[2] for c in v2))
print("Distinct V=2 tallies:", v2_tallies)
all_amend_vs = [c[2][0] for c in amend_cells]
print(f"Amendment-axis V range overall: {min(all_amend_vs)}-{max(all_amend_vs)}")
# Convention-free facts the round-9 text rests on (the round-8 skeptic's
# "16-cell family" used a narrower crossing convention; under this full
# crossing the family has 64 cells -- the count is convention-dependent,
# so the manuscript prints no count, only the structural fact):
check("every V=2 cell sits in a reverted base", all(c[0] != "published" for c in v2), True)
check("skeptic-named tallies all occur (2/11/11, 2/10/12, 2/12/12)",
      all(t in v2_tallies for t in [(2, 11, 11, 24), (2, 10, 12, 24), (2, 12, 12, 26)]), True)
check("no V<3 cell without a reverted score (published closure min V = 3)",
      min(vs), 3)

# ---------- Part 3: contemplated alternatives (round 10, R9-NEW-1) ----------
# The blind re-scoring agreed with every published score; its four
# borderline adjudications contemplated up-flips and rejected them
# (artifact records/DIFF-AND-ADJUDICATIONS.md). A4 is a full-matrix
# row; in the condensed matrix it merges into A3's row, so its
# condensed effect equals A3's.
a3p = dict(condensed); a3p["A3"] = "P"
check("contemplated A3->P (condensed)", tally(a3p), (4, 11, 12, 27))
check("contemplated A3->P x C4 merge", tally(merged(a3p, C4, "C4m", merge_rule([a3p[r] for r in C4]))), (3, 12, 11, 26))
a4p_full = dict(full); a4p_full["A4"] = "P"
check("contemplated A4->P (full)", tally(a4p_full), (4, 11, 14, 29))
a4p_cond = {k: v for k, v in a4p_full.items() if k not in ("A4", "F2")}
a4p_cond["A3"] = merge_rule([full["A3"], a4p_full["A4"]])
check("contemplated A4->P (condensed, via merge)", tally(a4p_cond), (4, 11, 12, 27))
g4p = dict(condensed); g4p["G4"] = "P"
check("contemplated G4->P (condensed)", tally(g4p), (4, 11, 12, 27))
check("contemplated G4->P x C4 merge", tally(merged(g4p, C4, "C4m", merge_rule([g4p[r] for r in C4]))), (3, 12, 11, 26))
b2v = dict(condensed); b2v["B2"] = "V"
check("contemplated B2->V (condensed)", tally(b2v), (5, 9, 13, 27))
check("contemplated B2->V x C4 merge", tally(merged(b2v, C4, "C4m", merge_rule([b2v[r] for r in C4]))), (4, 10, 12, 26))


# ---------- Part 4: wider-domain named-alternative stacks (round 11, PX-M1) ----------
# The Perplexity round-10 seat (PROVISIONAL, Class C coverage) offered two
# stacks over ALL named competent alternatives (both scorer directions) as
# communication/domain points. Verify or refute its arithmetic:
# (a) B2->V crossed with the G2-as-disclosure construction variant;
# (b) A3->P and G4->P crossed with the checkable (rule) C4 merge.
b2v_g2 = dict(b2v); b2v_g2["G2"] = "V"
check("PX wider B2->V x G2-as-disclosure", tally(b2v_g2), (6, 9, 12, 27))
a3g4 = dict(condensed); a3g4["A3"] = "P"; a3g4["G4"] = "P"
check("PX wider A3->P + G4->P x C4 merge", tally(merged(a3g4, C4, "C4m", merge_rule([a3g4[r] for r in C4]))), (3, 13, 10, 26))

n_fail = sum(1 for c in checks if not c[3])
print(f"\n{len(checks) - n_fail}/{len(checks)} checks PASS")
sys.exit(1 if n_fail else 0)
