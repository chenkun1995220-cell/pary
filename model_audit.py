import argparse
import csv
import os
import statistics
import tempfile
from datetime import date
from pathlib import Path


PROPOSAL_FIELDS = [
    "proposal_type", "parameter", "candidate_value", "status",
    "training_start", "training_end", "validation_start", "validation_end",
    "training_samples", "validation_samples", "markets",
]


def _number(value):
    try: return float(value)
    except (TypeError, ValueError): return None


def _metrics(rows):
    hits = [str(row.get("direction_hit", "")).lower() == "true" for row in rows]
    def average(field):
        values = [_number(row.get(field)) for row in rows]
        values = [value for value in values if value is not None]
        return statistics.fmean(values) if values else None
    return {
        "samples": len(rows),
        "direction_hit_rate": sum(hits) / len(hits) if hits else None,
        "average_return": average("actual_return"),
        "average_excess_return": average("excess_return"),
        "average_target_error": average("target_error_pct"),
        "average_adverse_excursion": average("max_adverse_excursion"),
    }


def audit_model(evaluations):
    mature = [row for row in evaluations if row.get("evaluation_status") == "evaluated"]
    mature.sort(key=lambda row: (row.get("generated_date", ""), row.get("ticker", "")))
    result = {"mature_samples": len(mature), "metrics": _metrics(mature), "proposals": []}
    if len(mature) < 30:
        return {**result, "audit_status": "sample_accumulating"}
    validation_count = int(len(mature) * 0.30)
    if validation_count < 15:
        return {**result, "audit_status": "validation_sample_insufficient"}
    training, validation = mature[:-validation_count], mature[-validation_count:]
    markets = sorted({row.get("market", "") for row in validation if row.get("market")})
    if len(markets) < 2:
        return {**result, "audit_status": "market_diversity_insufficient"}
    common = {
        "status": "analysis_candidate",
        "training_start": training[0].get("generated_date", ""),
        "training_end": training[-1].get("generated_date", ""),
        "validation_start": validation[0].get("generated_date", ""),
        "validation_end": validation[-1].get("generated_date", ""),
        "training_samples": len(training),
        "validation_samples": len(validation),
        "markets": ",".join(markets),
    }
    candidates = [
        ("direction_threshold", "direction_threshold", "0.03"),
        ("direction_threshold", "direction_threshold", "0.08"),
        ("target_cap", "target_price_cap", "1.40"),
        ("target_cap", "target_price_cap", "1.50"),
        ("safety_margin", "uniform_safety_margin", "0.25"),
    ]
    proposals = [
        {**common, "proposal_type": kind, "parameter": parameter, "candidate_value": value}
        for kind, parameter, value in candidates
    ]
    return {**result, "audit_status": "shadow_analysis_ready", "proposals": proposals,
            "training_metrics": _metrics(training), "validation_metrics": _metrics(validation)}


def _read(path):
    path = Path(path)
    if not path.exists(): return []
    with path.open(encoding="utf-8-sig", newline="") as handle: return list(csv.DictReader(handle))


def _atomic_csv(path, rows):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8-sig", newline="", delete=False, dir=path.parent) as handle:
        name = handle.name; writer = csv.DictWriter(handle, fieldnames=PROPOSAL_FIELDS, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)
    Path(name).replace(path)


def _atomic_text(path, text):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8-sig") as handle: handle.write(text)
    Path(name).replace(path)


def run_model_audit(evaluations_path, tracking_path, output_root, as_of_date=None):
    as_of_date = as_of_date or date.today().isoformat()
    evaluations = _read(evaluations_path); tracking = _read(tracking_path)
    result = audit_model(evaluations)
    output = Path(output_root)
    _atomic_csv(output / "shadow_model_proposals.csv", result["proposals"])
    lines = [f"# {as_of_date} 模型审计报告", "", f"- 成熟评价样本：{result['mature_samples']}",
             f"- 跟踪中样本：{sum(row.get('evaluation_status') == 'tracking' for row in tracking)}",
             f"- 审计状态：{result['audit_status']}"]
    if result["audit_status"] == "sample_accumulating":
        lines.append("- 结论：样本积累中，不生成参数升级建议。")
    else:
        lines.append(f"- 影子分析建议数量：{len(result['proposals'])}，尚未获得验证集改善证据，不得升级正式模型。")
    _atomic_text(output / "model_audit.md", "\n".join(lines) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description="Audit forecast model")
    parser.add_argument("--evaluations", required=True)
    parser.add_argument("--tracking", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--as-of-date")
    args = parser.parse_args()
    result = run_model_audit(args.evaluations, args.tracking, args.output_root, args.as_of_date)
    print(f"Audit status: {result['audit_status']}")
    print(f"Mature samples: {result['mature_samples']}")


if __name__ == "__main__": main()
