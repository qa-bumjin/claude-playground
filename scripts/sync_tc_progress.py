import argparse
import csv
import json
from pathlib import Path


def load_inventory(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "features" in data:
        return data
    raise ValueError("tc_inventory.json must contain a top-level 'features' array")


def count_csv_rows(path: Path) -> int:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return max(sum(1 for _ in csv.DictReader(f)), 0)


def sync_progress(project_dir: Path) -> int:
    inventory_path = project_dir / "tc_inventory.json"
    output_dir = project_dir / "tc_output"
    progress_path = project_dir / "tc_progress.json"

    if not inventory_path.exists():
        print(f"ERROR inventory missing: {inventory_path}")
        return 1
    if not output_dir.exists():
        print(f"ERROR tc_output missing: {output_dir}")
        return 1

    inventory = load_inventory(inventory_path)
    features = inventory["features"]
    generated_files: list[str] = []
    completed = 0
    in_progress = 0
    pending = 0
    total_tc_generated = 0
    last_updated_feature = None

    for feature in features:
        tc_status = feature.get("tc_status", "pending")
        tc_file = feature.get("tc_file")
        if tc_status == "generated":
            completed += 1
        elif tc_status in {"in_progress", "needs_review"}:
            in_progress += 1
        else:
            pending += 1

        if tc_file:
            csv_path = output_dir / tc_file
            if csv_path.exists():
                generated_files.append(f"tc_output/{tc_file}")
                row_count = count_csv_rows(csv_path)
                feature["tc_count"] = row_count
                total_tc_generated += row_count
                last_updated_feature = feature.get("feature_id", last_updated_feature)

    progress = {
        "document": inventory.get("document"),
        "session_summary": {
            "total_features": len(features),
            "completed_features": completed,
            "in_progress_features": in_progress,
            "pending_features": pending,
            "total_tc_generated": total_tc_generated,
        },
        "generated_files": generated_files,
        "last_updated_feature": last_updated_feature,
        "notes": [
            "집계 기준 파일",
            "실제 완료 여부는 tc_inventory.json의 tc_status를 우선 확인",
        ],
    }

    inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    progress_path.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK synced progress: {progress_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync tc_progress.json from tc_inventory.json and CSV outputs")
    parser.add_argument("--project", required=True, help="Project directory containing tc_inventory.json and tc_output/")
    args = parser.parse_args()
    return sync_progress(Path(args.project))


if __name__ == "__main__":
    raise SystemExit(main())
