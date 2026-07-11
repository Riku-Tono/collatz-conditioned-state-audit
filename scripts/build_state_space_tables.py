from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median


HERE = Path(r"C:\Users\yauki\Documents\Codex\2026-07-06\b004-b001-b001-b004-b004-10")
PREV = Path(r"C:\Users\yauki\Documents\Codex\2026-07-06\2026-07-06-codex-codex-1\outputs")
OUT = HERE / "outputs"

STATE_DICT = PREV / "local_state_automaton" / "local_state_dictionary.csv"
WORDS = PREV / "local_state_automaton" / "local_state_words_by_pair.csv"
COLLAPSE_EDGES = PREV / "local_state_automaton" / "collapse_edges_minus4_to_minus3.csv"

POSITIONS = ["-5", "-4", "-3", "-2", "-1", "0"]
SIDES = ["miss", "control"]
FEATURES = [
    "band",
    "R_before",
    "R_after",
    "transition_k",
    "exit_distance",
    "front",
    "chain_status",
    "residue16",
    "residue32",
]
NUMERIC_FEATURES = {"R_before", "R_after", "transition_k", "exit_distance"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def safe_value(value: str) -> str:
    if value == "":
        return "NA"
    return value.replace(" ", "_")


def to_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def entropy(counts: list[int]) -> float:
    total = sum(counts)
    if total == 0:
        return 0.0
    value = 0.0
    for count in counts:
        if count:
            p = count / total
            value -= p * math.log2(p)
    return value


def coords_from_dictionary(row: dict[str, str]) -> dict[str, str]:
    return {
        "dictionary_state_id": row["state_id"],
        "band": row["band"],
        "remaining_K_bin": row["band"],
        "R_before": row["remaining_K_before"],
        "R_after": row["remaining_K_after"],
        "boundary_front": row["front"],
        "front": row["front"],
        "chain_status": row["chain_status"],
        "local_event_class": local_event_class(row),
        "transition_k": row["transition_k"],
        "transition_k_class": transition_k_class(row["transition_k"]),
        "exit_distance": row["exit_distance"],
        "residue16": row["residue_pair_mod16"],
        "residue32": row["residue_pair_mod32"],
        "representative_label": row["human_label"],
    }


def local_event_class(row: dict[str, str]) -> str:
    if row["state_id"] == "S000" or row["band"] == "MISSING":
        return "missing"
    return f"{safe_value(row['front'])}|{safe_value(row['chain_status'])}"


def transition_k_class(value: str) -> str:
    if value == "":
        return "missing"
    ivalue = to_int(value)
    if ivalue is None:
        return f"k={value}"
    if ivalue <= 2:
        return "k_low_1_2"
    if ivalue <= 5:
        return "k_mid_3_5"
    return "k_high_6_plus"


def composite_state_id(coords: dict[str, str]) -> str:
    if coords["band"] in {"", "MISSING"}:
        return "state=missing"
    return "|".join(
        [
            f"band={safe_value(coords['band'])}",
            f"R={safe_value(coords['R_before'])}->{safe_value(coords['R_after'])}",
            f"front={safe_value(coords['boundary_front'])}",
            f"chain={safe_value(coords['chain_status'])}",
            f"k={safe_value(coords['transition_k'])}",
            f"res32={safe_value(coords['residue32'])}",
        ]
    )


def delta_value(source: dict[str, str], target: dict[str, str], feature: str) -> str:
    source_key = "boundary_front" if feature == "front" else feature
    target_key = "boundary_front" if feature == "front" else feature
    s = source[source_key]
    t = target[target_key]
    if feature in NUMERIC_FEATURES:
        si = to_int(s)
        ti = to_int(t)
        if si is None or ti is None:
            return ""
        return str(ti - si)
    if s == t:
        return "same"
    return f"{s}->{t}"


def changed_features(source: dict[str, str], target: dict[str, str]) -> list[str]:
    changed = []
    for feature in FEATURES:
        source_key = "boundary_front" if feature == "front" else feature
        target_key = "boundary_front" if feature == "front" else feature
        if source[source_key] != target[target_key]:
            changed.append(feature)
    return changed


def bundle_string(changed: list[str]) -> str:
    if not changed:
        return "none"
    if len(changed) == len(FEATURES):
        return "all_features"
    if len(changed) == len(FEATURES) - 1:
        missing = [feature for feature in FEATURES if feature not in changed][0]
        return f"all_except_{missing}"
    return "+".join(changed)


def face(coords: dict[str, str]) -> str:
    if coords["band"] in {"", "MISSING"}:
        return "missing"
    return "|".join(
        [
            coords["band"],
            f"R:{coords['R_before']}->{coords['R_after']}",
            f"k:{coords['transition_k']}",
            f"d:{coords['exit_distance']}",
            coords["boundary_front"],
            coords["chain_status"],
            f"r16:{coords['residue16']}",
            f"r32:{coords['residue32']}",
        ]
    )


def state_sequence(row: dict[str, str], side: str) -> list[str]:
    return [row[f"{side}_state_{position}"] for position in POSITIONS]


def trajectory_id(row: dict[str, str], side: str) -> str:
    return row[f"{side}_trajectory_id"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    dictionary_rows = read_csv(STATE_DICT)
    word_rows = read_csv(WORDS)
    collapse_rows = read_csv(COLLAPSE_EDGES)

    dict_coords = {row["state_id"]: coords_from_dictionary(row) for row in dictionary_rows}
    state_id_map = {sid: composite_state_id(coords) for sid, coords in dict_coords.items()}

    state_counts: Counter[str] = Counter()
    side_counts: dict[str, Counter[str]] = defaultdict(Counter)
    representative_dictionary_ids: dict[str, set[str]] = defaultdict(set)

    transition_counter: Counter[tuple[str, str]] = Counter()
    transition_side_counter: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    transition_examples: dict[tuple[str, str], list[str]] = defaultdict(list)
    transition_numeric_samples: dict[tuple[str, str], dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))

    for row in word_rows:
        for side in SIDES:
            seq = state_sequence(row, side)
            tid = trajectory_id(row, side)
            for sid in seq:
                state_id = state_id_map[sid]
                state_counts[state_id] += 1
                side_counts[state_id][side] += 1
                representative_dictionary_ids[state_id].add(sid)
            for source_sid, target_sid in zip(seq, seq[1:]):
                if source_sid == "S000" or target_sid == "S000":
                    continue
                source_state_id = state_id_map[source_sid]
                target_state_id = state_id_map[target_sid]
                key = (source_state_id, target_state_id)
                transition_counter[key] += 1
                transition_side_counter[key][side] += 1
                if len(transition_examples[key]) < 12:
                    transition_examples[key].append(f"{side}:{tid}")
                source_coords = dict_coords[source_sid]
                for feature, coord_key in [
                    ("R_before", "R_before"),
                    ("R_after", "R_after"),
                    ("transition_k", "transition_k"),
                    ("exit_distance", "exit_distance"),
                ]:
                    value = to_int(source_coords[coord_key])
                    if value is not None:
                        transition_numeric_samples[key][feature].append(value)

    state_rows = []
    for composite_id, count in sorted(state_counts.items(), key=lambda item: (-item[1], item[0])):
        dictionary_ids = sorted(representative_dictionary_ids[composite_id])
        primary_dict_id = dictionary_ids[0]
        coords = dict_coords[primary_dict_id]
        state_rows.append(
            {
                "state_id": composite_id,
                "band": coords["band"],
                "remaining_K_bin": coords["remaining_K_bin"],
                "boundary_front": coords["boundary_front"],
                "chain_status": coords["chain_status"],
                "local_event_class": coords["local_event_class"],
                "transition_k_class": coords["transition_k_class"],
                "residue16": coords["residue16"],
                "residue32": coords["residue32"],
                "count": count,
                "miss_count": side_counts[composite_id]["miss"],
                "control_count": side_counts[composite_id]["control"],
                "other_count": 0,
                "representative_label": coords["representative_label"],
                "source_dictionary_state_ids": "|".join(dictionary_ids),
            }
        )

    state_fields = [
        "state_id",
        "band",
        "remaining_K_bin",
        "boundary_front",
        "chain_status",
        "local_event_class",
        "transition_k_class",
        "residue16",
        "residue32",
        "count",
        "miss_count",
        "control_count",
        "other_count",
        "representative_label",
        "source_dictionary_state_ids",
    ]
    write_csv(OUT / "state_table.csv", state_rows, state_fields)

    outgoing_total: Counter[str] = Counter()
    for (source_state_id, _target_state_id), count in transition_counter.items():
        outgoing_total[source_state_id] += count

    transition_rows = []
    for idx, ((source_state_id, target_state_id), count) in enumerate(
        sorted(transition_counter.items(), key=lambda item: (-item[1], item[0][0], item[0][1])),
        start=1,
    ):
        source_dict_id = next(iter(representative_dictionary_ids[source_state_id]))
        target_dict_id = next(iter(representative_dictionary_ids[target_state_id]))
        source_coords = dict_coords[source_dict_id]
        target_coords = dict_coords[target_dict_id]
        sides = transition_side_counter[(source_state_id, target_state_id)]
        label_mix = "mixed" if sides["miss"] and sides["control"] else ("miss_only" if sides["miss"] else "control_only")
        samples = transition_numeric_samples[(source_state_id, target_state_id)]
        transition_rows.append(
            {
                "transition_id": f"T{idx:04d}",
                "source_state_id": source_state_id,
                "target_state_id": target_state_id,
                "count": count,
                "probability_from_source": round(count / outgoing_total[source_state_id], 6) if outgoing_total[source_state_id] else 0,
                "source_band": source_coords["band"],
                "target_band": target_coords["band"],
                "median_R_before": median(samples["R_before"]) if samples["R_before"] else "",
                "median_R_after": median(samples["R_after"]) if samples["R_after"] else "",
                "median_transition_k": median(samples["transition_k"]) if samples["transition_k"] else "",
                "median_exit_distance": median(samples["exit_distance"]) if samples["exit_distance"] else "",
                "miss_count": sides["miss"],
                "control_count": sides["control"],
                "label_mix": label_mix,
                "example_trajectory_ids": "|".join(transition_examples[(source_state_id, target_state_id)]),
            }
        )

    transition_fields = [
        "transition_id",
        "source_state_id",
        "target_state_id",
        "count",
        "probability_from_source",
        "source_band",
        "target_band",
        "median_R_before",
        "median_R_after",
        "median_transition_k",
        "median_exit_distance",
        "miss_count",
        "control_count",
        "label_mix",
        "example_trajectory_ids",
    ]
    write_csv(OUT / "transition_table.csv", transition_rows, transition_fields)

    transitions_by_source: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in transition_rows:
        transitions_by_source[str(row["source_state_id"])].append(row)

    branching_rows = []
    for source_state_id, rows in sorted(transitions_by_source.items()):
        total = sum(int(row["count"]) for row in rows)
        dominant = max(rows, key=lambda row: int(row["count"]))
        dominant_share = int(dominant["count"]) / total if total else 0
        miss_total = sum(int(row["miss_count"]) for row in rows)
        control_total = sum(int(row["control_count"]) for row in rows)
        if dominant_share >= 0.95:
            branching_class = "deterministic_like"
        elif dominant_share >= 0.75:
            branching_class = "weak_branching"
        else:
            branching_class = "branching"
        branching_rows.append(
            {
                "source_state_id": source_state_id,
                "out_degree": len(rows),
                "total_out_count": total,
                "dominant_target_state_id": dominant["target_state_id"],
                "dominant_target_share": round(dominant_share, 6),
                "transition_entropy": round(entropy([int(row["count"]) for row in rows]), 6),
                "miss_share": round(miss_total / total, 6) if total else 0,
                "control_share": round(control_total / total, 6) if total else 0,
                "branching_class": branching_class,
            }
        )

    branching_fields = [
        "source_state_id",
        "out_degree",
        "total_out_count",
        "dominant_target_state_id",
        "dominant_target_share",
        "transition_entropy",
        "miss_share",
        "control_share",
        "branching_class",
    ]
    write_csv(OUT / "branching_table.csv", branching_rows, branching_fields)

    coords_by_composite: dict[str, dict[str, str]] = {}
    for composite_id, dictionary_ids in representative_dictionary_ids.items():
        coords_by_composite[composite_id] = dict_coords[sorted(dictionary_ids)[0]]

    transition_id_lookup = {(row["source_state_id"], row["target_state_id"]): row["transition_id"] for row in transition_rows}
    bundle_rows = []
    for (source_state_id, target_state_id), count in sorted(transition_counter.items(), key=lambda item: transition_id_lookup[item[0]]):
        source_coords = coords_by_composite[source_state_id]
        target_coords = coords_by_composite[target_state_id]
        changed = changed_features(source_coords, target_coords)
        deltas = {feature: delta_value(source_coords, target_coords, feature) for feature in FEATURES}
        bundle_rows.append(
            {
                "transition_id": transition_id_lookup[(source_state_id, target_state_id)],
                "source_state_id": source_state_id,
                "target_state_id": target_state_id,
                "band_changed": int("band" in changed),
                "remaining_K_before_changed": int("R_before" in changed),
                "remaining_K_after_changed": int("R_after" in changed),
                "transition_k_changed": int("transition_k" in changed),
                "exit_distance_changed": int("exit_distance" in changed),
                "front_changed": int("front" in changed),
                "residue16_changed": int("residue16" in changed),
                "residue32_changed": int("residue32" in changed),
                "chain_status_changed": int("chain_status" in changed),
                "changed_feature_count": len(changed),
                "bundle_string": bundle_string(changed),
                "count": count,
                "delta_pattern": "|".join(f"{feature}:{deltas[feature]}" for feature in FEATURES),
                "source_face": face(source_coords),
                "target_face": face(target_coords),
            }
        )

    bundle_fields = [
        "transition_id",
        "source_state_id",
        "target_state_id",
        "band_changed",
        "remaining_K_before_changed",
        "remaining_K_after_changed",
        "transition_k_changed",
        "exit_distance_changed",
        "front_changed",
        "residue16_changed",
        "residue32_changed",
        "chain_status_changed",
        "changed_feature_count",
        "bundle_string",
        "count",
        "delta_pattern",
        "source_face",
        "target_face",
    ]
    write_csv(OUT / "bundle_check.csv", bundle_rows, bundle_fields)

    bundles_by_string: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in bundle_rows:
        bundles_by_string[str(row["bundle_string"])].append(row)

    bundle_frequency_rows = []
    for bundle, rows in sorted(bundles_by_string.items(), key=lambda item: (-sum(int(row["count"]) for row in item[1]), item[0])):
        row_count = len(rows)
        observation_count = sum(int(row["count"]) for row in rows)
        delta_count = len({row["delta_pattern"] for row in rows})
        source_count = len({row["source_state_id"] for row in rows})
        target_count = len({row["target_state_id"] for row in rows})
        source_face_count = len({row["source_face"] for row in rows})
        if row_count <= 2:
            stability = "sparse"
        elif observation_count >= 10 and delta_count <= 2:
            stability = "stable_candidate"
        elif observation_count >= 10 and delta_count > 2:
            stability = "frequent_but_diverse"
        else:
            stability = "sparse"
        bundle_frequency_rows.append(
            {
                "bundle_string": bundle,
                "row_count": row_count,
                "observation_count": observation_count,
                "unique_source_state_count": source_count,
                "unique_target_state_count": target_count,
                "unique_delta_pattern_count": delta_count,
                "unique_source_face_count": source_face_count,
                "stability_label": stability,
            }
        )

    bundle_frequency_fields = [
        "bundle_string",
        "row_count",
        "observation_count",
        "unique_source_state_count",
        "unique_target_state_count",
        "unique_delta_pattern_count",
        "unique_source_face_count",
        "stability_label",
    ]
    write_csv(OUT / "bundle_frequency.csv", bundle_frequency_rows, bundle_frequency_fields)

    strongest_branching = sorted(branching_rows, key=lambda row: (-float(row["transition_entropy"]), -int(row["out_degree"])))[:5]
    strongest_merges = Counter(str(row["target_state_id"]) for row in transition_rows)
    top_merges = strongest_merges.most_common(5)
    frequent_bundles = [row for row in bundle_frequency_rows if row["stability_label"] == "frequent_but_diverse"]
    stable_bundles = [row for row in bundle_frequency_rows if row["stability_label"] == "stable_candidate"]

    state_equation = [
        "# State Equation Candidate",
        "",
        "This note is restricted to the finite observed tables listed in README.md.",
        "",
        "## State Variable Candidate",
        "",
        "`X_t = (band_t, R_before_t, R_after_t, boundary_front_t, chain_status_t, residue32_t, transition_k_t)`",
        "",
        "The exported `state_table.csv` uses a composite `state_id` built from band, remaining-K face, boundary-front, chain status, transition k, and residue32.",
        "",
        "## Observation Variables",
        "",
        "- side label: miss/control, used as a bookkeeping label only",
        "- trajectory id and pair id",
        "- position in the local word window",
        "- residue16 as a finer residue coordinate",
        "- exit_distance as a local boundary coordinate",
        "",
        "## Input Or Perturbation-Like Variables",
        "",
        "The finite table can be read as a stochastic transition map:",
        "",
        "`P(X_{t+1} = y | X_t = x)`",
        "",
        "or as",
        "",
        "`X_{t+1} = F(X_t, epsilon_t)`",
        "",
        "`epsilon_t` stands for unresolved branching in the finite table, not a claim about unobserved dynamics.",
        "",
        "## Nearly Preserved Quantities",
        "",
        "Candidate near-preserved quantities should be read from high dominant target share and low transition entropy in `branching_table.csv`. Several states are deterministic_like within this finite sample.",
        "",
        "## Strong Branching States",
        "",
    ]
    for row in strongest_branching:
        state_equation.append(
            f"- {row['source_state_id']}: out_degree={row['out_degree']}, entropy={row['transition_entropy']}, dominant_share={row['dominant_target_share']}"
        )
    state_equation += [
        "",
        "## Strong Merge Targets",
        "",
    ]
    for target, count in top_merges:
        state_equation.append(f"- {target}: reached by {count} distinct transition rows")
    state_equation += [
        "",
        "## Bundle As State Variable Or Observation Label",
        "",
        "`B(x -> y) = { feature_i : feature_i(x) != feature_i(y) }`",
        "",
        "For now, bundle strings are best treated as observed labels attached to transitions. Frequent bundle strings should not replace state/transition rows unless their delta patterns are also compact.",
        "",
        "## Parts That Can Be Written Now",
        "",
        "- a finite stochastic transition table",
        "- source-level branching summary",
        "- transition-attached bundle labels",
        "- finite-sample merge target inventory",
        "",
        "## Parts To Keep Open",
        "",
        "- whether any bundle is compact enough to become a state variable",
        "- whether miss/control separation remains after conditioning on state",
        "- whether residue16 adds necessary resolution beyond residue32",
        "- whether exit_distance should be in X_t or treated as an observed boundary coordinate",
        "",
        "## Bundle Stability Snapshot",
        "",
        f"- stable_candidate bundles: {len(stable_bundles)}",
        f"- frequent_but_diverse bundles: {len(frequent_bundles)}",
        "- frequent and stable are kept separate in the exported table.",
        "",
    ]
    (OUT / "state_equation_candidate.md").write_text("\n".join(state_equation), encoding="utf-8")

    readme = [
        "# Finite State-Space Tables",
        "",
        "## Inputs",
        "",
        "The following machine-readable finite-sample files were inferred and used:",
        "",
        f"- `{STATE_DICT}`",
        f"- `{WORDS}`",
        f"- `{COLLAPSE_EDGES}` ({len(collapse_rows)} rows; used as a source artifact and consistency reference)",
        "",
        "The broader Collatz README/HTML files named in the request were treated as background context, not as row-level sources for these CSV tables.",
        "",
        "## State Definition",
        "",
        "A state is a composite finite observation point built from band, remaining-K before/after face, boundary-front, chain status, transition k, and residue32.",
        "",
        "The exported `state_id` format is:",
        "",
        "`band=<band>|R=<R_before>-><R_after>|front=<front>|chain=<chain_status>|k=<transition_k>|res32=<residue32>`",
        "",
        "## Transition Construction",
        "",
        "Each row in `local_state_words_by_pair.csv` contains miss/control state words over positions -5,-4,-3,-2,-1,0. Consecutive pairs in those words were counted as observed transitions.",
        "",
        "`S000/MISSING` is kept in `state_table.csv` as an observed placeholder, but transitions involving it are omitted from `transition_table.csv`, `branching_table.csv`, and bundle tables.",
        "",
        "`probability_from_source` is count divided by the total outgoing count for the source state.",
        "",
        "## Bundle Definition",
        "",
        "`B(x -> y) = { feature_i : feature_i(x) != feature_i(y) }`",
        "",
        "Bundle strings are transition labels. They are not treated as final state variables unless compactness is visible in `bundle_frequency.csv`.",
        "",
        "## Observed",
        "",
        f"- states: {len(state_rows)}",
        f"- distinct transitions: {len(transition_rows)}",
        f"- source states with outgoing transitions: {len(branching_rows)}",
        f"- bundle strings: {len(bundle_frequency_rows)}",
        f"- deterministic_like sources: {sum(1 for row in branching_rows if row['branching_class'] == 'deterministic_like')}",
        f"- branching sources: {sum(1 for row in branching_rows if row['branching_class'] == 'branching')}",
        "",
        "## Not Observed",
        "",
        "- no extension beyond the finite CSV sample",
        "- no single-feature explanation is assumed",
        "- miss/control labels are not interpreted as directional drivers",
        "- frequent bundle strings are separated from stable_candidate bundle strings",
        "",
        "## Next Items To Inspect",
        "",
        "- high-entropy rows in `branching_table.csv`",
        "- merge-heavy targets in `transition_table.csv`",
        "- frequent_but_diverse rows in `bundle_frequency.csv`",
        "- whether residue16 or exit_distance changes the branching profile when added/removed",
        "",
        "## Output Files",
        "",
        "- state_table.csv",
        "- transition_table.csv",
        "- branching_table.csv",
        "- bundle_check.csv",
        "- bundle_frequency.csv",
        "- state_equation_candidate.md",
        "- README.md",
    ]
    (OUT / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")

    log = {
        "state_table_rows": len(state_rows),
        "transition_table_rows": len(transition_rows),
        "branching_table_rows": len(branching_rows),
        "bundle_check_rows": len(bundle_rows),
        "bundle_frequency_rows": len(bundle_frequency_rows),
        "state_table_columns": state_fields,
        "transition_table_columns": transition_fields,
        "branching_table_columns": branching_fields,
        "bundle_check_columns": bundle_fields,
        "bundle_frequency_columns": bundle_frequency_fields,
        "top_bundle_frequency": bundle_frequency_rows[:5],
    }
    (OUT / "state_space_table_run_summary.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
