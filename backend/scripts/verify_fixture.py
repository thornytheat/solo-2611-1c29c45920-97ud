"""离线自检：不连数据库，直接对 fixture 跑算法 1+2，核对验收数值。

用法（宿主机或容器内）：
    cd backend && python -m scripts.verify_fixture
"""
from __future__ import annotations

import sys
from collections import defaultdict

from scripts import demo_config as cfg
from scripts.fixture import build_fixture
from src.services import funnel_engine, path_engine, segment_service


class Row:
    __slots__ = ("user_key", "event_name", "event_ts", "seq", "channel", "device")

    def __init__(self, data: dict):
        self.user_key = data["user_key"]
        self.event_name = data["event_name"]
        self.event_ts = data["event_ts"]
        self.seq = data["seq"]
        self.channel = data["channel"]
        self.device = data["device"]


def main() -> int:
    users, rows = build_fixture()
    print(f"users={len(users)} rows={len(rows)}")
    if len(users) != cfg.EXPECTED["users"] or len(rows) != cfg.EXPECTED["events"]:
        print("FAIL fixture size")
        return 1

    funnel = cfg.FUNNELS[0]
    vocabulary = {step["event"] for step in funnel["steps"]} | set(funnel["noise_events"])
    grouped: dict[str, list] = defaultdict(list)
    for row in rows:
        if row["event_name"] in vocabulary:
            grouped[row["user_key"]].append(Row(row))

    result = funnel_engine.run_funnel(grouped, funnel["steps"], 7, vocabulary, 6)
    steps = result["steps"]
    duration = result["duration"]
    print("steps:", [(step["label"], step["users"], step["rate_from_prev"]) for step in steps])
    print("p50 days:", duration["p50_days"], "samples:", duration["samples"])
    print("discard:", result["discard"])

    cohort = path_engine.analyze_cohort(result["outcomes"], steps, 1)
    print("cohort:", cohort["cohort_users"], "distinct paths:", cohort["distinct_paths"])
    for path in cohort["paths"]:
        print(f"  #{path['rank']} {path['share_pct']}%  {path['path']}")
    for choke in cohort["choke_points"]:
        print(f"  choke {choke['label']} {choke['count']} {choke['share_pct']}%")

    segments = segment_service.build_segments(
        result["segment_reached"], steps, 1,
        ["organic", "feed", "social", "referral"], ["ios", "android"],
    )
    print("overall drop rate:", segments["overall_drop_rate"], "max gap:", segments["max_gap_pp"])
    for row in segments["rows"]:
        print(f"  {row['channel_label']}·{row['device_label']} {row['users']} drop {row['drop_rate']}% gap {row['gap_pp']}pp")

    merged = path_engine.report_paths(result["outcomes"], steps, top_k=8)
    print("report paths:", len(merged))

    for spec in cfg.FUNNELS[1:]:
        vocab = {step["event"] for step in spec["steps"]} | set(spec["noise_events"])
        grouped_b: dict[str, list] = defaultdict(list)
        for row in rows:
            if row["event_name"] in vocab:
                grouped_b[row["user_key"]].append(Row(row))
        other = funnel_engine.run_funnel(grouped_b, spec["steps"], spec["window_days"], vocab, 6)
        print(
            spec["code"],
            [(step["label"], step["users"]) for step in other["steps"]],
            "expired:", other["discard"]["expired"],
        )

    checks = {
        "entry": steps[0]["users"] == cfg.EXPECTED["funnel_entry"],
        "trial": steps[1]["users"] == cfg.EXPECTED["trial_users"],
        "pay": steps[2]["users"] == cfg.EXPECTED["pay_users"],
        "p50": duration["p50_days"] == cfg.EXPECTED["step_p50_days"],
        "top_path": cohort["paths"][0]["share_pct"] == cfg.EXPECTED["top_path_share_pct"],
        "choke": cohort["choke_points"][0]["share_pct"] == cfg.EXPECTED["choke_share_pct"],
        "gap": segments["max_gap_pp"] == cfg.EXPECTED["max_gap_pp"],
        "paths": len(merged) == cfg.EXPECTED["report_paths"],
    }
    print(checks)
    if not all(checks.values()):
        print("FAIL", [key for key, value in checks.items() if not value])
        return 1
    print("OK fixture matches acceptance numbers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
