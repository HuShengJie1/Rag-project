from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


def main() -> None:
    results_path = Path("outputs/parsing/parsing_results.csv")
    if not results_path.exists():
        print("parsing_results.csv not found")
        return

    rows = []
    with results_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    summary = defaultdict(lambda: {"total": 0, "success": 0, "avg_time": 0.0})
    for r in rows:
        name = r.get("parser_name", "unknown")
        summary[name]["total"] += 1
        if str(r.get("success")).lower() == "true":
            summary[name]["success"] += 1
        try:
            summary[name]["avg_time"] += float(r.get("elapsed_time", 0))
        except Exception:
            pass

    for v in summary.values():
        if v["total"] > 0:
            v["avg_time"] = round(v["avg_time"] / v["total"], 4)

    out = {"by_parser": summary, "total_rows": len(rows)}
    Path("outputs/parsing/summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
