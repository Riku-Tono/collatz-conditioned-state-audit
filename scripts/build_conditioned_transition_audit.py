from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


HERE = Path(r"C:\Users\yauki\Documents\Codex\2026-07-06\b004-b001-b001-b004-b004-10")
PREV = Path(r"C:\Users\yauki\Documents\Codex\2026-07-06\2026-07-06-codex-codex-1\outputs")
OUT = HERE / "outputs" / "conditioned_transition_audit"

STATE_DICT = PREV / "local_state_automaton" / "local_state_dictionary.csv"
WORDS = PREV / "local_state_automaton" / "local_state_words_by_pair.csv"
BASIN_MATERIAL = PREV / "basin_material_cards" / "basin_material_table.csv"

POSITIONS = ["-5", "-4", "-3", "-2", "-1", "0"]
POSITION_PAIRS = [f"{a}->{b}" for a, b in zip(POSITIONS, POSITIONS[1:])]
ALLOWED_BASINS = {"B001", "B002", "B003", "B004"}
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


def branching_class(dominant_share: float) -> str:
    if dominant_share >= 0.95:
        return "function_like"
    if dominant_share >= 0.75:
        return "weak_branching"
    return "strong_branching"


def state_coords(row: dict[str, str]) -> dict[str, str]:
    return {
        "state_id": row["state_id"],
        "band": row["band"],
        "R_before": row["remaining_K_before"],
        "R_after": row["remaining_K_after"],
        "R_face": f"{row['remaining_K_before']}->{row['remaining_K_after']}" if row["remaining_K_before"] else "",
        "transition_k": row["transition_k"],
        "exit_distance": row["exit_distance"],
        "front": row["front"],
        "chain_status": row["chain_status"],
        "residue16": row["residue_pair_mod16"],
        "residue32": row["residue_pair_mod32"],
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
    return "|".join(f"{feature}:{source.get(feature, '')}->{target.get(feature, '')}" for feature in FEATURES)


def basin_lookup(material_rows: list[dict[str, str]]) -> dict[str, str]:
    return {row["common_suffix_word"]: row["basin_id"] for row in material_rows}


def condition_key(obs: dict[str, str], level: str) -> tuple[str, ...]:
    if level == "F_x":
        return ("ALL",)
    if level == "F_p_x":
        return (obs["position_pair"],)
    if level == "F_p_side_x":
        return (obs["position_pair"], obs["side"])
    if level == "F_p_side_basin_x":
        return (obs["position_pair"], obs["side"], obs["basin_id"])
    raise ValueError(level)


def condition_label(key: tuple[str, ...], level: str) -> tuple[str, str, str]:
    if level == "F_x":
        return "", "", ""
    if level == "F_p_x":
        return key[0], "", ""
    if level == "F_p_side_x":
        return key[0], key[1], ""
    if level == "F_p_side_basin_x":
        return key[0], key[1], key[2]
    raise ValueError(level)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    states = {row["state_id"]: state_coords(row) for row in read_csv(STATE_DICT)}
    suffix_to_basin = basin_lookup(read_csv(BASIN_MATERIAL))
    word_rows = read_csv(WORDS)

    observations: list[dict[str, str]] = []
    for row in word_rows:
        basin_id = suffix_to_basin.get(row["terminal_suffix_basin_word"], "")
        if basin_id not in ALLOWED_BASINS:
            continue
        for side in ["miss", "control"]:
            for source_pos, target_pos in zip(POSITIONS, POSITIONS[1:]):
                source = row[f"{side}_state_{source_pos}"]
                target = row[f"{side}_state_{target_pos}"]
                if source == "S000" or target == "S000":
                    continue
                observations.append(
                    {
                        "basin_id": basin_id,
                        "side": side,
                        "pair_id": row["pair_id"],
                        "trajectory_id": row[f"{side}_trajectory_id"],
                        "position_pair": f"{source_pos}->{target_pos}",
                        "source_state_id": source,
                        "target_state_id": target,
                    }
                )

    levels = ["F_x", "F_p_x", "F_p_side_x", "F_p_side_basin_x"]

    detail_rows: list[dict[str, object]] = []
    source_rows: list[dict[str, object]] = []
    level_summary_rows: list[dict[str, object]] = []
    source_resolution_rows: list[dict[str, object]] = []

    level_source_class: dict[str, dict[tuple[str, tuple[str, ...]], str]] = {level: {} for level in levels}

    for level in levels:
        grouped: dict[tuple[tuple[str, ...], str, str], Counter[str]] = defaultdict(Counter)
        examples: dict[tuple[tuple[str, ...], str, str], list[str]] = defaultdict(list)
        for obs in observations:
            key = condition_key(obs, level)
            gkey = (key, obs["source_state_id"], obs["target_state_id"])
            grouped[gkey][obs["side"]] += 1
            if len(examples[gkey]) < 8:
                examples[gkey].append(f"{obs['side']}:{obs['trajectory_id']}")

        by_source: dict[tuple[tuple[str, ...], str], list[dict[str, object]]] = defaultdict(list)
        for (cond_key, source, target), side_counts in grouped.items():
            source_coords = states[source]
            target_coords = states[target]
            changed = changed_features(source_coords, target_coords)
            count = side_counts["miss"] + side_counts["control"]
            position_pair, side_label, basin_id = condition_label(cond_key, level)
            detail = {
                "level": level,
                "position_pair": position_pair,
                "side_condition": side_label,
                "basin_id": basin_id,
                "source_state_id": source,
                "target_state_id": target,
                "count": count,
                "miss_count": side_counts["miss"],
                "control_count": side_counts["control"],
                "source_band": source_coords["band"],
                "target_band": target_coords["band"],
                "source_R_face": source_coords["R_face"],
                "target_R_face": target_coords["R_face"],
                "source_front": source_coords["front"],
                "target_front": target_coords["front"],
                "source_chain_status": source_coords["chain_status"],
                "target_chain_status": target_coords["chain_status"],
                "source_transition_k": source_coords["transition_k"],
                "target_transition_k": target_coords["transition_k"],
                "source_residue32": source_coords["residue32"],
                "target_residue32": target_coords["residue32"],
                "bundle_string": bundle_string(changed),
                "delta_pattern": delta_pattern(source_coords, target_coords),
                "example_trajectory_ids": "|".join(examples[(cond_key, source, target)]),
            }
            detail_rows.append(detail)
            by_source[(cond_key, source)].append(detail)

        class_counts = Counter()
        for (cond_key, source), rows in by_source.items():
            total = sum(int(row["count"]) for row in rows)
            dominant = max(rows, key=lambda row: int(row["count"]))
            share = int(dominant["count"]) / total if total else 0.0
            klass = branching_class(share)
            level_source_class[level][(source, cond_key)] = klass
            class_counts[klass] += 1
            position_pair, side_label, basin_id = condition_label(cond_key, level)
            source_rows.append(
                {
                    "level": level,
                    "position_pair": position_pair,
                    "side_condition": side_label,
                    "basin_id": basin_id,
                    "source_state_id": source,
                    "out_degree": len(rows),
                    "total_out_count": total,
                    "dominant_target_state_id": dominant["target_state_id"],
                    "dominant_target_share": round(share, 6),
                    "transition_entropy": round(entropy([int(row["count"]) for row in rows]), 6),
                    "branching_class": klass,
                    "target_state_ids": "|".join(sorted({str(row["target_state_id"]) for row in rows})),
                    "bundle_strings": "|".join(sorted({str(row["bundle_string"]) for row in rows})),
                }
            )

        total_sources = sum(class_counts.values())
        level_summary_rows.append(
            {
                "level": level,
                "condition_count": len({key for key, _source in by_source}),
                "source_row_count": total_sources,
                "function_like_count": class_counts["function_like"],
                "weak_branching_count": class_counts["weak_branching"],
                "strong_branching_count": class_counts["strong_branching"],
                "function_like_share": round(class_counts["function_like"] / total_sources, 6) if total_sources else 0,
            }
        )

    # Compare source_state_id branching collapse from F(x) to conditioned views.
    f_x_by_source = {source: row for row in source_rows if row["level"] == "F_x" for source in [row["source_state_id"]]}
    for source, fx_row in sorted(f_x_by_source.items()):
        if fx_row["branching_class"] == "function_like":
            continue
        for level in ["F_p_x", "F_p_side_x", "F_p_side_basin_x"]:
            rows = [row for row in source_rows if row["level"] == level and row["source_state_id"] == source]
            class_counts = Counter(str(row["branching_class"]) for row in rows)
            source_resolution_rows.append(
                {
                    "source_state_id": source,
                    "from_level": "F_x",
                    "from_out_degree": fx_row["out_degree"],
                    "from_branching_class": fx_row["branching_class"],
                    "conditioned_level": level,
                    "conditioned_source_rows": len(rows),
                    "conditioned_function_like_rows": class_counts["function_like"],
                    "conditioned_weak_branching_rows": class_counts["weak_branching"],
                    "conditioned_strong_branching_rows": class_counts["strong_branching"],
                    "fully_resolved_at_level": int(len(rows) > 0 and class_counts["weak_branching"] == 0 and class_counts["strong_branching"] == 0),
                }
            )

    detail_fields = [
        "level",
        "position_pair",
        "side_condition",
        "basin_id",
        "source_state_id",
        "target_state_id",
        "count",
        "miss_count",
        "control_count",
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
        "example_trajectory_ids",
    ]
    write_csv(OUT / "conditioned_transition_detail.csv", detail_rows, detail_fields)

    source_fields = [
        "level",
        "position_pair",
        "side_condition",
        "basin_id",
        "source_state_id",
        "out_degree",
        "total_out_count",
        "dominant_target_state_id",
        "dominant_target_share",
        "transition_entropy",
        "branching_class",
        "target_state_ids",
        "bundle_strings",
    ]
    write_csv(OUT / "conditioned_branching_by_source.csv", source_rows, source_fields)

    summary_fields = [
        "level",
        "condition_count",
        "source_row_count",
        "function_like_count",
        "weak_branching_count",
        "strong_branching_count",
        "function_like_share",
    ]
    write_csv(OUT / "conditioned_level_summary.csv", level_summary_rows, summary_fields)

    resolution_fields = [
        "source_state_id",
        "from_level",
        "from_out_degree",
        "from_branching_class",
        "conditioned_level",
        "conditioned_source_rows",
        "conditioned_function_like_rows",
        "conditioned_weak_branching_rows",
        "conditioned_strong_branching_rows",
        "fully_resolved_at_level",
    ]
    write_csv(OUT / "branching_resolution_by_condition.csv", source_resolution_rows, resolution_fields)

    # Focus tables for -4->-3.
    minus4_sources = [
        row
        for row in source_rows
        if row["position_pair"] == "-4->-3" or row["level"] == "F_x"
    ]
    write_csv(OUT / "minus4_conditioned_branching.csv", [row for row in source_rows if row["position_pair"] == "-4->-3"], source_fields)

    minus4_side_split = [
        row
        for row in detail_rows
        if row["position_pair"] == "-4->-3" and row["level"] in {"F_p_x", "F_p_side_x", "F_p_side_basin_x"}
    ]
    write_csv(OUT / "minus4_side_basin_detail.csv", minus4_side_split, detail_fields)

    summary = {row["level"]: row for row in level_summary_rows}
    fx_branching_sources = [row for row in source_rows if row["level"] == "F_x" and row["branching_class"] != "function_like"]
    resolved_at_p = [row for row in source_resolution_rows if row["conditioned_level"] == "F_p_x" and int(row["fully_resolved_at_level"]) == 1]
    resolved_at_side = [row for row in source_resolution_rows if row["conditioned_level"] == "F_p_side_x" and int(row["fully_resolved_at_level"]) == 1]
    resolved_at_basin = [row for row in source_resolution_rows if row["conditioned_level"] == "F_p_side_basin_x" and int(row["fully_resolved_at_level"]) == 1]
    stubborn = [
        row for row in source_resolution_rows
        if row["conditioned_level"] == "F_p_side_basin_x" and int(row["fully_resolved_at_level"]) == 0
    ]

    readme = [
        "# Conditioned Transition Audit: position -> side -> basin",
        "",
        "This audit checks whether visible branching is still present after conditioning the finite transition map.",
        "",
        "## Maps",
        "",
        "- `F(x) = { y | x -> y is observed }`",
        "- `F_p(x) = { y | x -> y is observed at position pair p }`",
        "- `F_{p,side}(x) = { y | x -> y is observed at position pair p and side }`",
        "- `F_{p,side,basin}(x) = { y | x -> y is observed at position pair p, side, and basin }`",
        "",
        "## Level Summary",
        "",
        "| level | source rows | function_like | weak | strong | function_like_share |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for level in levels:
        row = summary[level]
        readme.append(
            f"| {level} | {row['source_row_count']} | {row['function_like_count']} | {row['weak_branching_count']} | {row['strong_branching_count']} | {row['function_like_share']} |"
        )
    readme += [
        "",
        "## Main Reading",
        "",
        f"- `F(x)` has {len(fx_branching_sources)} non-function-like source states.",
        f"- At `F_p(x)`, {len(resolved_at_p)} of those source states become fully resolved across their position-conditioned rows.",
        f"- At `F_{{p,side}}(x)`, {len(resolved_at_side)} become fully resolved.",
        f"- At `F_{{p,side,basin}}(x)`, {len(resolved_at_basin)} become fully resolved.",
        f"- Remaining unresolved after all three conditions: {len(stubborn)} source states.",
        "",
        "## Minus Four To Minus Three",
        "",
        "The `-4->-3` slice is function-like at the basin-conditioned source-row level. Source IDs alone can still map to different targets across basins, so position is important but not the only condition.",
        "",
        "## Caution",
        "",
        "- This is a finite observed table audit only.",
        "- miss/control is a bookkeeping split only.",
        "- frequent bundle labels are not treated as stable state variables here.",
        "- If branching remains after position, side, and basin are all conditioned, that row is a candidate for a missing coordinate audit.",
    ]
    (OUT / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")

    run_summary = {
        "output_rows": {
            "conditioned_transition_detail.csv": len(detail_rows),
            "conditioned_branching_by_source.csv": len(source_rows),
            "conditioned_level_summary.csv": len(level_summary_rows),
            "branching_resolution_by_condition.csv": len(source_resolution_rows),
            "minus4_conditioned_branching.csv": len([row for row in source_rows if row["position_pair"] == "-4->-3"]),
            "minus4_side_basin_detail.csv": len(minus4_side_split),
        },
        "level_summary": level_summary_rows,
        "fx_non_function_like_sources": len(fx_branching_sources),
        "resolved_at_F_p_x": len(resolved_at_p),
        "resolved_at_F_p_side_x": len(resolved_at_side),
        "resolved_at_F_p_side_basin_x": len(resolved_at_basin),
        "stubborn_after_all_conditions": stubborn,
    }
    (OUT / "run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
    print(json.dumps(run_summary, indent=2))


if __name__ == "__main__":
    main()
