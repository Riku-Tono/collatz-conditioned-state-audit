from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SOURCE_DIR = ROOT / "source"
STATE_SPACE_DIR = ROOT / "state-space"
POSITION_AUDIT_DIR = ROOT / "position-audit"
OUT = ROOT / "conditioned-audit"

STATE_DICT = PREV / "local_state_automaton" / "local_state_dictionary.csv"
WORDS = PREV / "local_state_automaton" / "local_state_words_by_pair.csv"
COLLAPSE_EDGES = PREV / "local_state_automaton" / "collapse_edges_minus4_to_minus3.csv"
BASIN_MATERIAL = PREV / "basin_material_cards" / "basin_material_table.csv"
STATE_TABLE = HERE / "outputs" / "state_table.csv"
TRANSITION_TABLE = HERE / "outputs" / "transition_table.csv"
BRANCHING_TABLE = HERE / "outputs" / "branching_table.csv"
BUNDLE_CHECK = HERE / "outputs" / "bundle_check.csv"
BUNDLE_FREQUENCY = HERE / "outputs" / "bundle_frequency.csv"

POSITIONS = ["-5", "-4", "-3", "-2", "-1", "0"]
POSITION_PAIRS = list(zip(POSITIONS, POSITIONS[1:]))
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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def entropy(counts: list[int]) -> float:
    total = sum(counts)
    if total == 0:
        return 0.0
    out = 0.0
    for count in counts:
        if count:
            p = count / total
            out -= p * math.log2(p)
    return out


def state_coords(row: dict[str, str]) -> dict[str, str]:
    return {
        "state_id": row["state_id"],
        "band": row["band"],
        "R_before": row["remaining_K_before"],
        "R_after": row["remaining_K_after"],
        "R_face": f"{row['remaining_K_before']}->{row['remaining_K_after']}" if row["remaining_K_before"] else "",
        "front": row["front"],
        "chain_status": row["chain_status"],
        "transition_k": row["transition_k"],
        "exit_distance": row["exit_distance"],
        "residue16": row["residue_pair_mod16"],
        "residue32": row["residue_pair_mod32"],
        "face": "|".join(
            [
                row["band"],
                f"R:{row['remaining_K_before']}->{row['remaining_K_after']}",
                f"k:{row['transition_k']}",
                f"d:{row['exit_distance']}",
                row["front"],
                row["chain_status"],
                f"r32:{row['residue_pair_mod32']}",
            ]
        ),
    }


def changed_features(source: dict[str, str], target: dict[str, str]) -> list[str]:
    return [feature for feature in FEATURES if source.get(feature, "") != target.get(feature, "")]


def bundle_string(changed: list[str]) -> str:
    if not changed:
        return "none"
    if len(changed) == len(FEATURES):
        return "all_features"
    if len(changed) == len(FEATURES) - 1:
        missing = [feature for feature in FEATURES if feature not in changed][0]
        return f"all_except_{missing}"
    return "+".join(changed)


def delta_pattern(source: dict[str, str], target: dict[str, str]) -> str:
    parts = []
    for feature in FEATURES:
        s = source.get(feature, "")
        t = target.get(feature, "")
        parts.append(f"{feature}:{s}->{t}")
    return "|".join(parts)


def mixed_label(miss_count: int, control_count: int) -> str:
    if miss_count and control_count:
        return "mixed"
    if miss_count:
        return "miss_only"
    if control_count:
        return "control_only"
    return "none"


def branching_class(dominant_share: float) -> str:
    if dominant_share >= 0.95:
        return "function_like"
    if dominant_share >= 0.75:
        return "weak_branching"
    return "strong_branching"


def stability_label(row_count: int, observation_count: int, delta_count: int) -> str:
    if row_count <= 2:
        return "sparse"
    if observation_count >= 10 and delta_count <= 2:
        return "stable_candidate"
    if observation_count >= 10 and delta_count > 2:
        return "frequent_but_diverse"
    return "sparse"


def basin_lookup(material_rows: list[dict[str, str]]) -> dict[str, str]:
    return {row["common_suffix_word"]: row["basin_id"] for row in material_rows}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    dict_rows = read_csv(STATE_DICT)
    word_rows = read_csv(WORDS)
    collapse_rows = read_csv(COLLAPSE_EDGES)
    material_rows = read_csv(BASIN_MATERIAL)
    # Existence checks for requested prior outputs.
    prior_inputs = [STATE_TABLE, TRANSITION_TABLE, BRANCHING_TABLE, BUNDLE_CHECK, BUNDLE_FREQUENCY]
    prior_counts = {str(path): (len(read_csv(path)) if path.exists() and path.suffix == ".csv" else None) for path in prior_inputs}

    states = {row["state_id"]: state_coords(row) for row in dict_rows}
    suffix_to_basin = basin_lookup(material_rows)
    allowed_basins = {"B001", "B002", "B003", "B004"}

    observations: list[dict[str, object]] = []
    for row in word_rows:
        basin_id = suffix_to_basin.get(row["terminal_suffix_basin_word"], "")
        if basin_id not in allowed_basins:
            continue
        for side in ["miss", "control"]:
            for source_pos, target_pos in POSITION_PAIRS:
                source = row[f"{side}_state_{source_pos}"]
                target = row[f"{side}_state_{target_pos}"]
                observations.append(
                    {
                        "basin_id": basin_id,
                        "pair_id": row["pair_id"],
                        "side": side,
                        "trajectory_id": row[f"{side}_trajectory_id"],
                        "position_pair": f"{source_pos}->{target_pos}",
                        "source_position": source_pos,
                        "target_position": target_pos,
                        "source_state_id": source,
                        "target_state_id": target,
                    }
                )

    grouped: dict[tuple[str, str, str, str, str], Counter[str]] = defaultdict(Counter)
    example_ids: dict[tuple[str, str, str, str, str], list[str]] = defaultdict(list)
    for obs in observations:
        key = (
            str(obs["position_pair"]),
            str(obs["basin_id"]),
            str(obs["source_state_id"]),
            str(obs["target_state_id"]),
            str(obs["source_position"]),
        )
        side = str(obs["side"])
        grouped[key][side] += 1
        if len(example_ids[key]) < 10:
            example_ids[key].append(f"{side}:{obs['trajectory_id']}")

    source_denominators: Counter[tuple[str, str, str]] = Counter()
    for (position_pair, basin_id, source_state_id, _target_state_id, _source_position), side_counts in grouped.items():
        source_denominators[(position_pair, basin_id, source_state_id)] += side_counts["miss"] + side_counts["control"]

    transition_rows = []
    for (position_pair, basin_id, source_state_id, target_state_id, source_position), side_counts in sorted(grouped.items()):
        source_pos, target_pos = position_pair.split("->")
        source = states[source_state_id]
        target = states[target_state_id]
        changed = changed_features(source, target)
        miss_count = side_counts["miss"]
        control_count = side_counts["control"]
        count = miss_count + control_count
        transition_rows.append(
            {
                "position_pair": position_pair,
                "source_position": source_pos,
                "target_position": target_pos,
                "source_state_id": source_state_id,
                "target_state_id": target_state_id,
                "count": count,
                "probability_from_source_within_position": round(count / source_denominators[(position_pair, basin_id, source_state_id)], 6),
                "basin_id": basin_id,
                "side": mixed_label(miss_count, control_count),
                "miss_count": miss_count,
                "control_count": control_count,
                "mixed_label": mixed_label(miss_count, control_count),
                "source_band": source["band"],
                "target_band": target["band"],
                "source_R_face": source["R_face"],
                "target_R_face": target["R_face"],
                "source_front": source["front"],
                "target_front": target["front"],
                "source_chain_status": source["chain_status"],
                "target_chain_status": target["chain_status"],
                "source_transition_k": source["transition_k"],
                "target_transition_k": target["transition_k"],
                "source_residue32": source["residue32"],
                "target_residue32": target["residue32"],
                "bundle_string": bundle_string(changed),
                "delta_pattern": delta_pattern(source, target),
                "source_face": source["face"],
                "target_face": target["face"],
                "example_trajectory_ids": "|".join(example_ids[(position_pair, basin_id, source_state_id, target_state_id, source_position)]),
            }
        )

    transition_fields = [
        "position_pair",
        "source_position",
        "target_position",
        "source_state_id",
        "target_state_id",
        "count",
        "probability_from_source_within_position",
        "basin_id",
        "side",
        "miss_count",
        "control_count",
        "mixed_label",
        "source_band",
        "target_band",
        "source_R_face",
        "target_R_face",
        "source_front",
        "target_front",
        "source_chain_status",
        "target_chain_status",
        "source_transition_k",
        "target_transition_k",
        "source_residue32",
        "target_residue32",
        "bundle_string",
        "delta_pattern",
        "source_face",
        "target_face",
        "example_trajectory_ids",
    ]
    write_csv(OUT / "position_transition_table.csv", transition_rows, transition_fields)

    minus4_rows = [row for row in transition_rows if row["position_pair"] == "-4->-3"]
    minus4_fields = [
        "source_state_id",
        "target_state_id",
        "count",
        "probability_from_source",
        "basin_id",
        "side",
        "miss_count",
        "control_count",
        "mixed_label",
        "source_band",
        "target_band",
        "source_R_face",
        "target_R_face",
        "source_front",
        "target_front",
        "source_chain_status",
        "target_chain_status",
        "source_transition_k",
        "target_transition_k",
        "source_residue32",
        "target_residue32",
        "bundle_string",
        "delta_pattern",
        "source_face",
        "target_face",
        "example_trajectory_ids",
    ]
    minus4_out = []
    for row in minus4_rows:
        row2 = dict(row)
        row2["probability_from_source"] = row2.pop("probability_from_source_within_position")
        minus4_out.append(row2)
    write_csv(OUT / "minus4_to_minus3_transition_table.csv", minus4_out, minus4_fields)

    def make_branching(rows: list[dict[str, object]], include_position: bool) -> list[dict[str, object]]:
        by_source: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            key = (str(row.get("position_pair", "-4->-3" if not include_position else "")), str(row["basin_id"]), str(row["source_state_id"]))
            by_source[key].append(row)
        out = []
        for (position_pair, basin_id, source_state_id), group in sorted(by_source.items()):
            total = sum(int(row["count"]) for row in group)
            dominant = max(group, key=lambda row: int(row["count"]))
            share = int(dominant["count"]) / total if total else 0.0
            miss = sum(int(row["miss_count"]) for row in group)
            control = sum(int(row["control_count"]) for row in group)
            item = {
                "position_pair": position_pair,
                "basin_id": basin_id,
                "source_state_id": source_state_id,
                "out_degree": len(group),
                "total_out_count": total,
                "dominant_target_state_id": dominant["target_state_id"],
                "dominant_target_share": round(share, 6),
                "transition_entropy": round(entropy([int(row["count"]) for row in group]), 6),
                "branching_class": branching_class(share),
                "miss_count": miss,
                "control_count": control,
                "mixed_label": mixed_label(miss, control),
            }
            out.append(item)
        return out

    branching_rows = make_branching(transition_rows, include_position=True)
    branching_fields = [
        "position_pair",
        "basin_id",
        "source_state_id",
        "out_degree",
        "total_out_count",
        "dominant_target_state_id",
        "dominant_target_share",
        "transition_entropy",
        "branching_class",
        "miss_count",
        "control_count",
        "mixed_label",
    ]
    write_csv(OUT / "position_branching_table.csv", branching_rows, branching_fields)

    minus4_branching_rows = make_branching(minus4_out, include_position=False)
    write_csv(OUT / "minus4_to_minus3_branching_table.csv", minus4_branching_rows, branching_fields)

    def bundle_frequency(rows: list[dict[str, object]], include_position: bool) -> list[dict[str, object]]:
        by_key: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            pos = str(row["position_pair"]) if include_position else "-4->-3"
            by_key[(pos, str(row["bundle_string"]))].append(row)
        out = []
        for (position_pair, bundle), group in sorted(by_key.items()):
            row_count = len(group)
            observation_count = sum(int(row["count"]) for row in group)
            source_count = len({row["source_state_id"] for row in group})
            target_count = len({row["target_state_id"] for row in group})
            delta_count = len({row["delta_pattern"] for row in group})
            source_face_count = len({row["source_face"] for row in group})
            out.append(
                {
                    "position_pair": position_pair,
                    "bundle_string": bundle,
                    "row_count": row_count,
                    "observation_count": observation_count,
                    "unique_source_state_count": source_count,
                    "unique_target_state_count": target_count,
                    "unique_delta_pattern_count": delta_count,
                    "unique_source_face_count": source_face_count,
                    "stability_label": stability_label(row_count, observation_count, delta_count),
                }
            )
        return out

    bundle_freq_rows = bundle_frequency(transition_rows, include_position=True)
    bundle_freq_fields = [
        "position_pair",
        "bundle_string",
        "row_count",
        "observation_count",
        "unique_source_state_count",
        "unique_target_state_count",
        "unique_delta_pattern_count",
        "unique_source_face_count",
        "stability_label",
    ]
    write_csv(OUT / "position_bundle_frequency.csv", bundle_freq_rows, bundle_freq_fields)
    minus4_bundle_freq_rows = bundle_frequency(minus4_out, include_position=False)
    write_csv(OUT / "minus4_to_minus3_bundle_frequency.csv", minus4_bundle_freq_rows, bundle_freq_fields)

    band_slice = [
        row
        for row in minus4_out
        if row["source_band"] == "64-127" and row["target_band"] == "32-63"
    ]
    band_slice_fields = [
        "basin_id",
        "side",
        "source_state_id",
        "target_state_id",
        "count",
        "miss_count",
        "control_count",
        "mixed_label",
        "source_R_face",
        "target_R_face",
        "source_front",
        "target_front",
        "source_chain_status",
        "target_chain_status",
        "source_transition_k",
        "target_transition_k",
        "source_residue32",
        "target_residue32",
        "bundle_string",
        "delta_pattern",
        "example_trajectory_ids",
    ]
    write_csv(OUT / "minus4_to_minus3_64_127_to_32_63.csv", band_slice, band_slice_fields)

    pos_counts = Counter()
    for row in transition_rows:
        pos_counts[str(row["position_pair"])] += int(row["count"])
    minus4_split = Counter()
    for row in minus4_out:
        minus4_split[str(row["mixed_label"])] += int(row["count"])
    minus4_branching_counts = Counter(str(row["branching_class"]) for row in minus4_branching_rows)
    position_branching_counts = Counter((str(row["position_pair"]), str(row["branching_class"])) for row in branching_rows)
    minus4_bundle_top = sorted(minus4_bundle_freq_rows, key=lambda row: (-int(row["observation_count"]), row["bundle_string"]))[:10]

    summary_lines = [
        "# Position-Specific Transition Audit",
        "",
        "This is a finite local audit of B001-B004. It keeps position pair as an explicit condition.",
        "",
        "## Inputs",
        "",
        f"- `{WORDS}`",
        f"- `{STATE_DICT}`",
        f"- `{COLLAPSE_EDGES}`",
        f"- `{BASIN_MATERIAL}`",
        "- prior state-space outputs in this workspace were checked for continuity",
        "",
        "## Transition Counts By Position",
        "",
    ]
    for pos in [f"{a}->{b}" for a, b in POSITION_PAIRS]:
        summary_lines.append(f"- {pos}: {pos_counts[pos]} observations")
    summary_lines += [
        "",
        "## Minus Four To Minus Three",
        "",
        f"- transition rows: {len(minus4_out)}",
        f"- observations: {sum(int(row['count']) for row in minus4_out)}",
        f"- observation-weighted split: {dict(sorted(minus4_split.items()))}",
        f"- branching classes: {dict(sorted(minus4_branching_counts.items()))}",
        "",
        "## Branching By Position",
        "",
    ]
    for (position_pair, klass), count in sorted(position_branching_counts.items()):
        summary_lines.append(f"- {position_pair} / {klass}: {count} source rows")
    summary_lines += [
        "",
        "## Top Bundles At Minus Four To Minus Three",
        "",
    ]
    for row in minus4_bundle_top:
        summary_lines.append(
            f"- {row['bundle_string']}: rows={row['row_count']}, observations={row['observation_count']}, delta_patterns={row['unique_delta_pattern_count']}, label={row['stability_label']}"
        )
    summary_lines += [
        "",
        "## 64-127 To 32-63 At Minus Four To Minus Three",
        "",
        f"- rows: {len(band_slice)}",
        f"- observations: {sum(int(row['count']) for row in band_slice)}",
        f"- row split: {dict(Counter(str(row['mixed_label']) for row in band_slice))}",
        "",
        "## Reading",
        "",
        "`F_p(x)` separates transitions that were merged in the all-position table. If a source still branches inside `-4->-3`, then that split is not only a position-mixing artifact.",
        "",
        "The `64-127 -> 32-63` slice remains a useful finite audit target, especially for source faces that are side-skewed or have more than one target.",
        "",
        "## Unresolved",
        "",
        "- whether side-skewed rows remain side-skewed after adding more coordinates",
        "- whether `front` should be treated as a state coordinate or a transition label",
        "- whether position alone is enough to reduce the visible branching",
    ]
    (OUT / "position_specific_summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    readme_lines = [
        "# Position-Specific Audit",
        "",
        "This folder audits the finite B001-B004 local state words with position pair preserved.",
        "",
        "## Definitions",
        "",
        "All-position finite transition:",
        "",
        "`F(x) = { y | x -> y is observed }`",
        "",
        "Position-conditioned transition:",
        "",
        "`F_p(x) = { y | x -> y is observed at position pair p }`",
        "",
        "Main inspected position:",
        "",
        "`F_{-4->-3}(x) = { y | x -> y is observed from -4 to -3 }`",
        "",
        "Position-conditioned bundle label:",
        "",
        "`B_p(x,y) = { feature_i | feature_i(x) != feature_i(y), observed at position pair p }`",
        "",
        "## Interpretation Rules",
        "",
        "- If branching visible in `F(x)` becomes near one-target in `F_p(x)`, position is an important condition variable.",
        "- If branching remains in `F_{-4->-3}(x)`, that split is not resolved by position alone.",
        "- bundle strings are kept as transition labels, not promoted to state variables here.",
        "- miss/control is used only as a finite label split.",
        "- `-4->-3` is treated as a focused audit slice, not as a privileged final answer.",
        "",
        "## Inputs Used",
        "",
        f"- `{WORDS}`",
        f"- `{STATE_DICT}`",
        f"- `{COLLAPSE_EDGES}`",
        f"- `{BASIN_MATERIAL}`",
        f"- prior output row checks: `{json.dumps(prior_counts)}`",
        "",
        "## Outputs",
        "",
        "- position_transition_table.csv",
        "- minus4_to_minus3_transition_table.csv",
        "- position_branching_table.csv",
        "- minus4_to_minus3_branching_table.csv",
        "- position_bundle_frequency.csv",
        "- minus4_to_minus3_bundle_frequency.csv",
        "- minus4_to_minus3_64_127_to_32_63.csv",
        "- position_specific_summary.md",
        "- README.md",
    ]
    (OUT / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")

    run_summary = {
        "input_files": [str(WORDS), str(STATE_DICT), str(COLLAPSE_EDGES), str(BASIN_MATERIAL)],
        "output_rows": {
            "position_transition_table.csv": len(transition_rows),
            "minus4_to_minus3_transition_table.csv": len(minus4_out),
            "position_branching_table.csv": len(branching_rows),
            "minus4_to_minus3_branching_table.csv": len(minus4_branching_rows),
            "position_bundle_frequency.csv": len(bundle_freq_rows),
            "minus4_to_minus3_bundle_frequency.csv": len(minus4_bundle_freq_rows),
            "minus4_to_minus3_64_127_to_32_63.csv": len(band_slice),
        },
        "position_observation_counts": dict(sorted(pos_counts.items())),
        "minus4_observation_count": sum(int(row["count"]) for row in minus4_out),
        "minus4_branching_class_distribution": dict(sorted(minus4_branching_counts.items())),
        "minus4_top_bundles": minus4_bundle_top,
        "minus4_64_127_to_32_63_rows": len(band_slice),
        "minus4_64_127_to_32_63_observations": sum(int(row["count"]) for row in band_slice),
    }
    (OUT / "run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
    print(json.dumps(run_summary, indent=2))


if __name__ == "__main__":
    main()
