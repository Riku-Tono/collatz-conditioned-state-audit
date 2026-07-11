# Finite State-Space Tables and Position-Specific Audit (B001-B004)

## Status

This is a finite-observation working note. It records what was built and seen inside
the observed local-state-word tables for B001-B004. It is not a theory paper. There is
no proof, no general result, and no claim beyond the finite CSV sample. The miss/control
split is used only as a bookkeeping label, never as a direction of cause. Frequent
bundle labels are kept separate from stable ones, and bundle labels are not promoted to
state variables here.

## Purpose

Two passes are consolidated:

1. A finite state-space table built from observed local state words, with transitions,
   branching, and change-feature bundles attached.
2. A position-specific audit that re-ran the transition view with the position pair kept
   as an explicit condition, focused on the `-4 -> -3` step.

## Input Artifacts

The row-level sources were the finite local-state-automaton files
(`local_state_dictionary.csv`, `local_state_words_by_pair.csv`, and
`collapse_edges_minus4_to_minus3.csv`), plus the basin material table for continuity.
Broader Collatz notes were treated as background, not as row sources. Derived tables
produced and consolidated here: `state_table.csv`, `transition_table.csv`,
`branching_table.csv`, `bundle_check.csv`, `bundle_frequency.csv`,
`state_equation_candidate.md`; and for the audit, `position_transition_table.csv`,
`minus4_to_minus3_transition_table.csv`, `position_branching_table.csv`,
`minus4_to_minus3_branching_table.csv`, `position_bundle_frequency.csv`,
`minus4_to_minus3_bundle_frequency.csv`, `minus4_to_minus3_64_127_to_32_63.csv`; and for
the conditioned resolution audit, `conditioned_level_summary.csv` and
`conditioned_branching_by_source.csv`.

## 1. State Definition (observation cards)

A state is a composite observation card built from the observed coordinates:

`state_id = band | R_before -> R_after | front | chain_status | transition_k | residue32`

Each card is a finite observation point, nothing more. The exported table holds 33 such
states (one, `S000/MISSING`, is an observed placeholder and is dropped from the
transition and bundle tables).

## 2. Transition Construction

Consecutive state changes inside each local word (over positions -5, -4, -3, -2, -1, 0)
were counted as observed transitions. `probability_from_source` is the outgoing count
divided by the total outgoing count for that source state. The all-position table holds
37 distinct transitions from 30 source states.

## 3. Bundle Definition

`B(x -> y) = { feature_i : feature_i(x) != feature_i(y) }`

A bundle string is a changed-feature set attached to a transition. It is a transition
label, not a state coordinate. Seven bundle strings appear in the finite state table.

## 4. All-Position View: Branching Appeared

Read across all positions at once, most source states were function-like but some split.
The all-position `branching_table.csv` labels 24 sources deterministic_like, 2
weak_branching, and 4 branching. The visible splits concentrate in the `64-127` band,
for example the source at `R=67->62` (out_degree 3, dominant share 0.5), `R=67->63`
(out_degree 2, dominant share 0.5), `R=70->63` (out_degree 2, dominant share 0.5),
`R=67->60` (dominant share ~0.67), and `R=64->63` (dominant share ~0.77). At this point
the transition view looked partly like a branching map: same card, more than one observed
next card.

## 5. Position-Specific Audit: F_p(x)

The audit re-ran the transition view with the position pair kept explicit:

- All-position finite transition: `F(x) = { y | x -> y is observed }`
- Position-conditioned: `F_p(x) = { y | x -> y is observed at position pair p }`
- Focused slice: `F_{-4->-3}(x) = { y | x -> y is observed from -4 to -3 }`
- Position-conditioned bundle: `B_p(x,y) = changed features of x -> y at position pair p`

Each of the five position pairs carries 100 observations.

## 6. Result at -4 -> -3

The function_like result holds at the basin-conditioned level, not for bare source ids.
Inside the `-4 -> -3` slice, every basin-conditioned source row is function_like: for
each `(position_pair, basin_id, source_state_id)` triple the observed target is unique in
this finite table (dominant share 1.0, entropy 0), across all 22 rows. The
observation-weighted side split of the slice is control_only 24, miss_only 36, mixed 40.

But this is conditioned on `basin_id`. If `basin_id` is removed and only
`source_state_id` is used, several source states still map to more than one target across
B001-B004, because each basin has its own `-4 -> -3` target (B001 -> S012, B002/B003 ->
S013, B004 -> S014). Observed examples:

- S021 -> S012 | S013 | S014
- S017 -> S012 | S013
- S023 -> S012 | S014
- S029 -> S012 | S014
- S019 -> S013 | S014

So conditioning on the `-4 -> -3` position separated transitions that the all-position
table had merged, but it did not remove all branching. Some remains once basin context is
dropped. The fuller conditioned audit in Section 8 traces which combination of conditions
completes the resolution over the whole table, and shows that position by itself does not.

## 7. The -4 -> -3 Slice Is Entirely 64-127 -> 32-63

In this B001-B004 sample, all 22 rows of the `-4 -> -3` slice have source band `64-127`
and target band `32-63`. The row-level side split there is mixed 1, miss_only 18,
control_only 3. The single mixed row is the B001 `S017 -> S012` entrance (40
observations, 14 miss / 26 control). So the `-4 -> -3` step, in this finite sample,
coincides with the `64-127 -> 32-63` entrance face.

## 8. Conditioned Resolution: position -> side -> basin

A separate conditioned audit steps through the conditions one at a time, to see which
one actually completes the resolution of the visible branching:

- `F(x) = { y | x -> y is observed }`
- `F_p(x) = { y | x -> y is observed at position pair p }`
- `F_{p,side}(x) = { y | x -> y is observed at position pair p and side }`
- `F_{p,side,basin}(x) = { y | x -> y is observed at position pair p, side, and basin }`

Level summary (source rows are the conditioned source rows at each level):

| level | source rows | function_like | weak | strong | function_like share |
| --- | ---: | ---: | ---: | ---: | ---: |
| F(x) | 30 | 24 | 2 | 4 | 0.800000 |
| F_p(x) | 30 | 24 | 2 | 4 | 0.800000 |
| F_{p,side}(x) | 38 | 31 | 2 | 5 | 0.815789 |
| F_{p,side,basin}(x) | 56 | 56 | 0 | 0 | 1.000000 |

At `F(x)`, six source states are not function_like: S011 and S017 (weak_branching), and
S019, S021, S023, S029 (strong_branching). Following those six down the ladder:

- At `F_p(x)`, 0 of the six become fully resolved. The source-row counts are identical to
  `F(x)`: 24 function_like, 2 weak, 4 strong.
- At `F_{p,side}(x)`, 0 of the six become fully resolved. Adding side creates more
  conditioned rows but still leaves weak and strong branching (31 / 2 / 5).
- At `F_{p,side,basin}(x)`, all six become fully resolved. All 56 conditioned source rows
  are function_like.
- Remaining unresolved after all three conditions: 0.

So the apparent branching in `F(x)` is not fully resolved by adding position alone, and
not fully resolved by adding side after position either. In this finite B001-B004 table,
it is resolved only when `(position_pair, side, basin_id)` are all conditioned. Phrased
carefully: position is important, but not sufficient; side is also not sufficient; in
this finite table, basin/suffix context is the condition that completes the observed
resolution of the branching. The branching therefore looks, in this sample, like a
mixture of basin/suffix contexts rather than a split that persists after all currently
tracked conditions.

This is a finite-map observation, not a formula and not a general result. Side and basin
are conditioning labels here; the audit does not claim that side or basin causes or
explains the branching, only that conditioning on them removes it in this table. `-4 -> -3`
is a focused audit slice, not a privileged final answer, and basin/suffix context is
treated as a finite-table context label, not a promoted state variable.

## 9. Bundle Labels at -4 -> -3

The `-4 -> -3` bundle frequencies keep the frequent/stable distinction visible:

- `band+R_before+R_after+transition_k+residue16+residue32`: rows 3, observations 52,
  delta patterns 2 — the exported table tags this as a *stable_candidate*. That is a
  tentative candidate label (few delta patterns), not a confirmed stable unit; it is not
  being declared stable here.
- `all_except_chain_status`: rows 9, observations 18, delta patterns 8 —
  frequent_but_diverse.
- `all_features`: rows 9, observations 18, delta patterns 9 — frequent_but_diverse.
- `band+R_before+R_after`: rows 1, observations 12, delta pattern 1 — sparse.

`all_except_front` did not appear in the `-4 -> -3` slice. Bundles remain transition
labels; none is promoted to a state coordinate.

## 10. What Looks Function-Like vs What Still Branches

Within this finite table, under the current threshold, full resolution appears only at the
end of the conditioning ladder. Branching is still present at `F(x)` (six non-function-like
sources), unchanged at `F_p(x)` (position alone resolves none of the six), and still
present at `F_{p,side}(x)` (position plus side resolves none of the six). Only at
`F_{p,side,basin}(x)` are all 56 conditioned source rows function_like. The persistent
splits sit mostly in the `64-127` band and in the cross-basin sources (S011, S017, S019,
S021, S023, S029), and they close once basin/suffix context is added — position removes one
layer of mixing, side another sliver, but basin/suffix context is what completes the
resolution here. The open question is which structural coordinate that basin/suffix context
stands for, and whether the pattern survives a larger sample.

## 11. Unresolved

- Whether `R_after` and `transition_k` are state coordinates or edge attributes of a
  transition. They currently sit inside the observation card but read partly as
  step-level quantities.
- Whether `front` is state-like or transition-like.
- Whether `residue16` adds resolution beyond `residue32`, or is redundant here.
- Whether the bundle labels are only coarse transition labels, or whether any is compact
  enough (few delta patterns) to eventually stand as a coordinate. Not decided.
- Whether the `(position_pair, side, basin_id)` resolution holds outside B001-B004. The
  full-resolution result rests on this finite table only (56 conditioned source rows).
- What basin/suffix context represents structurally. It is the condition that completes
  the observed resolution here, but the audit does not say what it stands for.
- Whether a coordinate can later replace `basin_id`. For now `basin_id` is kept as a
  finite-table context label and is not promoted to a mathematical state variable; if a
  measurable coordinate reproduces the same resolution, it could stand in later.
- Whether `R_after` and `transition_k` are state coordinates or edge attributes, whether
  `front` is state-like or transition-like, and whether `residue16` adds resolution
  beyond `residue32` — all still open (Sections above).
- Whether side-skewed rows stay side-skewed once more coordinates are added, and whether
  the miss/control split persists after conditioning on state. miss/control stays a
  bookkeeping split, not a driver.
- Source, target, and delta rows are kept visible beside the conditioned summaries; the
  ladder counts are search handles, not replacements for the row-level evidence.

## 12. Suggested Next Inspection

Keep arrow/state/delta rows beside the bundle labels; do not collapse to bundle strings.
The most useful next checks are: test whether the `(position_pair, side, basin_id)`
resolution holds outside B001-B004; inspect what basin/suffix context represents
structurally and whether a measurable coordinate could stand in for `basin_id`; and try
adding or removing `residue16` and `exit_distance` to see whether the branching profile
changes before basin is conditioned. This stays a finite map of the observed tables, not a
general formula.
