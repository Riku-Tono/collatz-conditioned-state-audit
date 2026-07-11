from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IN_DIR = ROOT / "outputs" / "minus4_split_dissection"
EXPANSION = IN_DIR / "twin_minus4_expansion.csv"
RANKED = IN_DIR / "twin_minus4_reconvergence_ranked.csv"
OUT = ROOT / "outputs" / "local_state_automaton"
OUT.mkdir(parents=True, exist_ok=True)

STEPS = [-5, -4, -3, -2, -1, 0]
SUFFIX_STEPS = [-3, -2, -1, 0]
STATE_COLS = [
    "band",
    "remaining_K_before",
    "remaining_K_after",
    "transition_k",
    "exit_distance",
    "front",
    "chain_status",
    "residue_pair_mod16",
    "residue_pair_mod32",
]
SIDES = ["miss", "control"]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def short_front(front: str) -> str:
    return {
        "lower_edge_front": "lower",
        "near_exit_front": "near",
        "deeper_front": "deep",
    }.get(front, front)


def state_tuple(row: dict[str, str], side: str) -> tuple[str, ...]:
    vals = tuple(row.get(f"{side}_{col}", "") for col in STATE_COLS)
    if not any(vals):
        return ("MISSING", "", "", "", "", "", "", "", "")
    return vals


def state_label(t: tuple[str, ...]) -> str:
    if t[0] == "MISSING":
        return "MISSING"
    band, before, after, k, d, front, chain, r16, r32 = t
    return f"{band} | {before}->{after} | k{k} | d{d} | {short_front(front)} | {chain} | r16 {r16}"


def load_pair_rows() -> tuple[dict[str, dict[str, str]], dict[tuple[str, int], dict[str, str]]]:
    ranked = {r["pair_id"]: r for r in read_csv(RANKED)}
    expanded = {}
    for row in read_csv(EXPANSION):
        expanded[(row["pair_id"], int(row["relative_event"]))] = row
    return ranked, expanded


def build_state_dictionary(expanded: dict[tuple[str, int], dict[str, str]]) -> tuple[dict[tuple[str, ...], str], list[dict[str, object]]]:
    states = {("MISSING", "", "", "", "", "", "", "", "")}
    for row in expanded.values():
        for side in SIDES:
            states.add(state_tuple(row, side))

    ordered = [("MISSING", "", "", "", "", "", "", "", "")]
    ordered.extend(sorted(s for s in states if s[0] != "MISSING"))

    state_to_id = {state: f"S{i:03d}" for i, state in enumerate(ordered)}
    rows = []
    for state, sid in state_to_id.items():
        rows.append(
            {
                "state_id": sid,
                "human_label": state_label(state),
                "band": state[0],
                "remaining_K_before": state[1],
                "remaining_K_after": state[2],
                "transition_k": state[3],
                "exit_distance": state[4],
                "front": state[5],
                "chain_status": state[6],
                "residue_pair_mod16": state[7],
                "residue_pair_mod32": state[8],
            }
        )
    return state_to_id, rows


def side_state(
    pair_id: str,
    step: int,
    side: str,
    expanded: dict[tuple[str, int], dict[str, str]],
    state_to_id: dict[tuple[str, ...], str],
) -> str:
    row = expanded.get((pair_id, step))
    if row is None:
        return "S000"
    return state_to_id[state_tuple(row, side)]


def word(pair_id: str, side: str, steps: list[int], expanded: dict[tuple[str, int], dict[str, str]], state_to_id: dict[tuple[str, ...], str]) -> list[str]:
    return [side_state(pair_id, step, side, expanded, state_to_id) for step in steps]


def classify_collapse(miss_word: list[str], control_word: list[str]) -> str:
    idx = {step: i for i, step in enumerate(STEPS)}
    if miss_word[idx[-4]] != control_word[idx[-4]] and miss_word[idx[-3]] == control_word[idx[-3]] and miss_word[idx[-2]] == control_word[idx[-2]] and miss_word[idx[-1]] == control_word[idx[-1]] and miss_word[idx[0]] == control_word[idx[0]]:
        return "A_one_step_collapse"
    if miss_word[idx[-4]] == control_word[idx[-4]] and all(miss_word[idx[s]] == control_word[idx[s]] for s in SUFFIX_STEPS):
        return "B_already_merged"
    if miss_word[idx[-4]] != control_word[idx[-4]] and miss_word[idx[-3]] != control_word[idx[-3]]:
        for start in [-2, -1, 0]:
            if all(miss_word[idx[s]] == control_word[idx[s]] for s in range(start, 1)):
                return "C_delayed_merge"
    return "D_no_merge_in_window"


def build_state_words(
    ranked: dict[str, dict[str, str]],
    expanded: dict[tuple[str, int], dict[str, str]],
    state_to_id: dict[tuple[str, ...], str],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    word_rows = []
    class_rows = []
    for pair_id, meta in ranked.items():
        miss_word = word(pair_id, "miss", STEPS, expanded, state_to_id)
        control_word = word(pair_id, "control", STEPS, expanded, state_to_id)
        suffix_word = word(pair_id, "miss", SUFFIX_STEPS, expanded, state_to_id)
        cls = classify_collapse(miss_word, control_word)
        base = {
            "pair_id": pair_id,
            "miss_sample_id": meta["miss_sample_id"],
            "miss_trajectory_id": meta["miss_trajectory_id"],
            "control_sample_id": meta["control_sample_id"],
            "control_trajectory_id": meta["control_trajectory_id"],
            "source_reconvergence_state": meta.get("reconvergence_state", ""),
            "source_minus4_split_type": meta.get("minus4_split_type", ""),
        }
        word_rows.append(
            {
                **base,
                "miss_state_word_-5_0": " ".join(miss_word),
                "control_state_word_-5_0": " ".join(control_word),
                "miss_state_-5": miss_word[0],
                "miss_state_-4": miss_word[1],
                "miss_state_-3": miss_word[2],
                "miss_state_-2": miss_word[3],
                "miss_state_-1": miss_word[4],
                "miss_state_0": miss_word[5],
                "control_state_-5": control_word[0],
                "control_state_-4": control_word[1],
                "control_state_-3": control_word[2],
                "control_state_-2": control_word[3],
                "control_state_-1": control_word[4],
                "control_state_0": control_word[5],
                "terminal_suffix_basin_word": " ".join(suffix_word),
                "collapse_class": cls,
            }
        )
        class_rows.append(
            {
                **base,
                "collapse_class": cls,
                "minus4_states_same": int(miss_word[1] == control_word[1]),
                "minus3_states_same": int(miss_word[2] == control_word[2]),
                "suffix_-3_0_same": int(all(miss_word[i] == control_word[i] for i in [2, 3, 4, 5])),
                "miss_minus4_state": miss_word[1],
                "control_minus4_state": control_word[1],
                "terminal_suffix_basin_word": " ".join(suffix_word),
                "comment": collapse_comment(cls),
            }
        )
    return word_rows, class_rows


def collapse_comment(cls: str) -> str:
    return {
        "A_one_step_collapse": "-4で別状態、-3から同じsuffix basinへ合流",
        "B_already_merged": "-4時点ですでに同じ入口顔",
        "C_delayed_merge": "-4では別、-3でも別、窓内の後段で合流",
        "D_no_merge_in_window": "-5..0内では合流しきらない",
    }[cls]


def build_edges(word_rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    edge_stats: dict[tuple[str, str], dict[str, object]] = {}
    target_sources: dict[str, list[tuple[str, str, str]]] = defaultdict(list)

    for row in word_rows:
        for side in SIDES:
            source = str(row[f"{side}_state_-4"])
            target = str(row[f"{side}_state_-3"])
            key = (source, target)
            stats = edge_stats.setdefault(
                key,
                {
                    "from_state": source,
                    "to_state": target,
                    "side_observations": 0,
                    "pair_ids": set(),
                    "miss_count": 0,
                    "control_count": 0,
                    "example_pairs": [],
                },
            )
            stats["side_observations"] += 1
            stats["pair_ids"].add(row["pair_id"])
            stats[f"{side}_count"] += 1
            if len(stats["example_pairs"]) < 5:
                stats["example_pairs"].append(f"{side}:{row['pair_id']}")
            target_sources[target].append((source, side, str(row["pair_id"])))

    edge_rows = []
    for stats in edge_stats.values():
        edge_rows.append(
            {
                "from_state": stats["from_state"],
                "to_state": stats["to_state"],
                "side_observations": stats["side_observations"],
                "pair_count": len(stats["pair_ids"]),
                "miss_count": stats["miss_count"],
                "control_count": stats["control_count"],
                "side_mix": side_mix_label(stats["miss_count"], stats["control_count"]),
                "example_pairs": "|".join(stats["example_pairs"]),
            }
        )
    edge_rows.sort(key=lambda r: (-int(r["side_observations"]), r["from_state"], r["to_state"]))

    target_rows = []
    for target, entries in target_sources.items():
        sources = Counter(src for src, _side, _pid in entries)
        miss_sources = {src for src, side, _pid in entries if side == "miss"}
        control_sources = {src for src, side, _pid in entries if side == "control"}
        pair_ids = {pid for _src, _side, pid in entries}
        target_rows.append(
            {
                "to_state": target,
                "source_state_count": len(sources),
                "side_observations": len(entries),
                "pair_count": len(pair_ids),
                "miss_source_state_count": len(miss_sources),
                "control_source_state_count": len(control_sources),
                "miss_control_mixing": int(bool(miss_sources) and bool(control_sources)),
                "source_entropy": entropy(list(sources.values())),
                "top_sources": top_counts(sources),
            }
        )
    target_rows.sort(key=lambda r: (-int(r["source_state_count"]), -float(r["source_entropy"]), r["to_state"]))
    return edge_rows, target_rows


def side_mix_label(miss_count: int, control_count: int) -> str:
    if miss_count and control_count:
        return "mixed"
    if miss_count:
        return "miss_only"
    if control_count:
        return "control_only"
    return "none"


def entropy(counts: list[int]) -> float:
    total = sum(counts)
    if total == 0:
        return 0.0
    h = 0.0
    for c in counts:
        p = c / total
        h -= p * math.log2(p)
    return round(h, 6)


def top_counts(counter: Counter[str], n: int = 8) -> str:
    return "|".join(f"{key}:{count}" for key, count in counter.most_common(n))


def build_basins(word_rows: list[dict[str, object]], class_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    cls_by_pair = {r["pair_id"]: r["collapse_class"] for r in class_rows}
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in word_rows:
        groups[str(row["terminal_suffix_basin_word"])].append(row)

    rows = []
    for i, (basin_word, items) in enumerate(sorted(groups.items()), start=1):
        source_obs = []
        miss_sources = []
        control_sources = []
        pair_ids = []
        class_counts = Counter()
        for row in items:
            pair_ids.append(str(row["pair_id"]))
            class_counts[str(cls_by_pair[row["pair_id"]])] += 1
            for side in SIDES:
                sid = str(row[f"{side}_state_-4"])
                source_obs.append(sid)
                if side == "miss":
                    miss_sources.append(sid)
                else:
                    control_sources.append(sid)
        source_counts = Counter(source_obs)
        miss_counts = Counter(miss_sources)
        control_counts = Counter(control_sources)
        basin_id = f"B{i:03d}"
        rows.append(
            {
                "basin_id": basin_id,
                "terminal_suffix_basin_word": basin_word,
                "pair_count": len(set(pair_ids)),
                "source_state_count": len(source_counts),
                "miss_source_state_count": len(miss_counts),
                "control_source_state_count": len(control_counts),
                "source_observation_count": len(source_obs),
                "source_entropy": entropy(list(source_counts.values())),
                "miss_control_mixing": int(bool(miss_counts) and bool(control_counts)),
                "miss_source_entropy": entropy(list(miss_counts.values())),
                "control_source_entropy": entropy(list(control_counts.values())),
                "entrance_asymmetry": len(miss_counts) - len(control_counts),
                "collapse_class_counts": top_counts(class_counts),
                "source_states": "|".join(source_counts),
                "miss_source_states": "|".join(miss_counts),
                "control_source_states": "|".join(control_counts),
                "representative_pair_ids": "|".join(pair_ids[:10]),
            }
        )
    return rows


def rank_basins(basins: list[dict[str, object]]) -> list[dict[str, object]]:
    ranked = []
    for row in basins:
        source_count = int(row["source_state_count"])
        pair_count = int(row["pair_count"])
        miss_sources = int(row["miss_source_state_count"])
        control_sources = int(row["control_source_state_count"])
        h = float(row["source_entropy"])
        score = source_count * 20 + pair_count * 4 + h * 10
        if int(row["miss_control_mixing"]):
            score += 25
        if miss_sources > control_sources:
            score += (miss_sources - control_sources) * 8
        if control_sources <= 2 and miss_sources >= 3:
            score += 20
        comment = basin_comment(source_count, miss_sources, control_sources, pair_count)
        ranked.append({**row, "interesting_score": round(score, 3), "comment": comment})
    return sorted(ranked, key=lambda r: (-float(r["interesting_score"]), r["basin_id"]))


def basin_comment(source_count: int, miss_sources: int, control_sources: int, pair_count: int) -> str:
    if control_sources <= 2 and miss_sources >= 3:
        return "control entrance compressed to 2 faces, miss entrance dispersed"
    if source_count >= 5:
        return f"many-to-one collapse: {source_count} source states into one suffix basin"
    if miss_sources and control_sources and miss_sources != control_sources:
        return "same terminal suffix, asymmetric entrance diversity"
    if pair_count >= 5:
        return "candidate local-state sink"
    return "small basin; keep as witness"


def write_cards(ranked_basins: list[dict[str, object]], dictionary_rows: list[dict[str, object]]) -> None:
    label = {r["state_id"]: r["human_label"] for r in dictionary_rows}
    lines = ["# Basin cards", ""]
    for row in ranked_basins[:20]:
        suffix_ids = str(row["terminal_suffix_basin_word"]).split()
        source_ids = str(row["source_states"]).split("|") if row["source_states"] else []
        miss_ids = str(row["miss_source_states"]).split("|") if row["miss_source_states"] else []
        control_ids = str(row["control_source_states"]).split("|") if row["control_source_states"] else []
        lines.extend(
            [
                f"## {row['basin_id']}",
                "",
                f"- score: `{row['interesting_score']}`",
                f"- pairs: `{row['pair_count']}`",
                f"- source states: `{row['source_state_count']}`",
                f"- miss/control sources: `{row['miss_source_state_count']}` / `{row['control_source_state_count']}`",
                f"- comment: {row['comment']}",
                f"- representative pairs: `{row['representative_pair_ids']}`",
                "",
                "Terminal suffix `-3..0`:",
                "",
            ]
        )
        for step, sid in zip(SUFFIX_STEPS, suffix_ids):
            lines.append(f"- `{step}` {sid}: {label.get(sid, '')}")
        lines.extend(["", "Source states at `-4`:", ""])
        for sid in source_ids:
            side_tags = []
            if sid in miss_ids:
                side_tags.append("miss")
            if sid in control_ids:
                side_tags.append("control")
            lines.append(f"- {sid} ({'/'.join(side_tags)}): {label.get(sid, '')}")
        lines.append("")
    (OUT / "basin_cards.md").write_text("\n".join(lines), encoding="utf-8")


def write_report(
    dictionary_rows: list[dict[str, object]],
    class_rows: list[dict[str, object]],
    edge_rows: list[dict[str, object]],
    target_rows: list[dict[str, object]],
    basins: list[dict[str, object]],
    ranked_basins: list[dict[str, object]],
) -> None:
    class_counts = Counter(str(r["collapse_class"]) for r in class_rows)
    basin_top = ranked_basins[:10]
    control_source_counts = Counter()
    miss_source_counts = Counter()
    for row in class_rows:
        control_source_counts[str(row["control_minus4_state"])] += 1
        miss_source_counts[str(row["miss_minus4_state"])] += 1

    lines = [
        "# Local-State Automaton: terminal suffix twins as many-to-one state collapse",
        "",
        "探索メモ。今回は feature difference ではなく、local state を1文字として見た。",
        "つまり `R/k/exit_distance/front/residue` の束を S-state に圧縮し、どの入口状態が同じ terminal suffix basin に流れ込むかを見る。",
        "",
        "## Why",
        "",
        "`-4` のズレは単独特徴量ではなく束で動いていた。だから列ごとの原因探しではなく、状態遷移として眺める。",
        "",
        "## Quick smell",
        "",
        f"- local states: `{len(dictionary_rows)}` including `S000=MISSING`",
        f"- pair rows: `{len(class_rows)}`",
        f"- collapse classes: `{dict(class_counts)}`",
        f"- collapse edges -4->-3: `{len(edge_rows)}`",
        f"- collapse targets at -3: `{len(target_rows)}`",
        f"- terminal suffix basins: `{len(basins)}`",
        f"- top control -4 states: `{top_counts(control_source_counts, 5)}`",
        f"- top miss -4 states: `{top_counts(miss_source_counts, 5)}`",
        "",
        "## Major basins",
        "",
        "| rank | basin | score | pairs | source states | miss/control source states | entropy | comment |",
        "|---:|---|---:|---:|---:|---|---:|---|",
    ]
    for i, row in enumerate(basin_top, start=1):
        lines.append(
            f"| {i} | {row['basin_id']} | {row['interesting_score']} | {row['pair_count']} | {row['source_state_count']} | {row['miss_source_state_count']}/{row['control_source_state_count']} | {row['source_entropy']} | {row['comment']} |"
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "ここで見たいのは、同じ suffix が偶然似ているだけか、それとも複数の入口状態を吸い込む local-state sink になっているか。",
            "control 側の入口 state が少なく、miss 側が散る basin は、terminal suffix twin を生成する装置っぽく見える。",
            "逆に source state が少ない basin は、単なる同一ルートの反復に近い。",
            "",
            "## Files",
            "",
            "- `local_state_dictionary.csv`",
            "- `local_state_words_by_pair.csv`",
            "- `local_state_collapse_classes.csv`",
            "- `collapse_edges_minus4_to_minus3.csv`",
            "- `collapse_targets_summary.csv`",
            "- `terminal_suffix_basins.csv`",
            "- `interesting_basins_ranked.csv`",
            "- `basin_cards.md`",
            "- `run_summary.json`",
        ]
    )
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ranked, expanded = load_pair_rows()
    state_to_id, dictionary_rows = build_state_dictionary(expanded)
    word_rows, class_rows = build_state_words(ranked, expanded, state_to_id)
    edge_rows, target_rows = build_edges(word_rows)
    basins = build_basins(word_rows, class_rows)
    ranked_basins = rank_basins(basins)

    write_csv(OUT / "local_state_dictionary.csv", dictionary_rows)
    write_csv(OUT / "local_state_words_by_pair.csv", word_rows)
    write_csv(OUT / "local_state_collapse_classes.csv", class_rows)
    write_csv(OUT / "collapse_edges_minus4_to_minus3.csv", edge_rows)
    write_csv(OUT / "collapse_targets_summary.csv", target_rows)
    write_csv(OUT / "terminal_suffix_basins.csv", basins)
    write_csv(OUT / "interesting_basins_ranked.csv", ranked_basins)
    write_cards(ranked_basins, dictionary_rows)
    write_report(dictionary_rows, class_rows, edge_rows, target_rows, basins, ranked_basins)

    summary = {
        "local_states": len(dictionary_rows),
        "pairs": len(class_rows),
        "collapse_classes": dict(Counter(str(r["collapse_class"]) for r in class_rows)),
        "collapse_edges_minus4_to_minus3": len(edge_rows),
        "collapse_targets": len(target_rows),
        "terminal_suffix_basins": len(basins),
        "top_basin": ranked_basins[0] if ranked_basins else None,
        "sources": {"expansion": str(EXPANSION), "ranked": str(RANKED)},
    }
    (OUT / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
