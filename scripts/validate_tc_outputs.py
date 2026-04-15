import argparse
import csv
import json
import re
from pathlib import Path
from typing import Optional


def load_inventory(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "features" in data:
        return {item["feature_id"]: item for item in data["features"]}
    return data


def load_csv_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def normalize_rule_value(value: str) -> str:
    if not value:
        return ""
    return value.strip().split(" ", 1)[0]


def extract_tc_number(tc_id: str) -> Optional[int]:
    if not tc_id.startswith("TC-"):
        return None
    try:
        return int(tc_id.split("-", 1)[1])
    except ValueError:
        return None


def normalize_free_text(value: str) -> str:
    if not value:
        return ""
    normalized = value.strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"[\"'`]", "", normalized)
    return normalized


def tokenize_text(value: str) -> set[str]:
    stopwords = {
        "확인", "검증", "동작", "노출", "적용", "배치", "상태", "기준", "영역",
        "화면", "상품", "이미지", "아이콘", "텍스트", "클릭", "입력", "선택",
        "사용", "등록", "수정", "최신", "최대", "초과", "개", "만", "만료",
    }
    normalized = normalize_free_text(value)
    tokens = set(re.findall(r"[0-9a-zA-Z가-힣]+", normalized))
    return {token for token in tokens if len(token) > 1 and token not in stopwords}


def jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def validate_project(project_dir: Path) -> int:
    inventory_path = project_dir / "tc_inventory.json"
    output_dir = project_dir / "tc_output"
    errors: list[str] = []
    warnings: list[str] = []

    if not inventory_path.exists():
        print(f"ERROR inventory missing: {inventory_path}")
        return 1
    if not output_dir.exists():
        print(f"ERROR tc_output missing: {output_dir}")
        return 1

    inventory = load_inventory(inventory_path)
    csv_map = {path.name: path for path in output_dir.glob("TC_*.csv")}
    all_tc_ids: list[tuple[str, str, int]] = []
    duplicate_guard: set[str] = set()
    semantic_rows: list[dict[str, object]] = []
    processed_csv_files: set[str] = set()

    for feature_id, feature in inventory.items():
        tc_status = feature.get("tc_status")
        tc_file = feature.get("tc_file")
        rules = feature.get("rules", [])

        if tc_status == "generated" and not tc_file:
            errors.append(f"{feature_id}: tc_status=generated but tc_file missing")
            continue

        if not tc_file:
            continue

        csv_path = csv_map.get(tc_file)
        if not csv_path:
            errors.append(f"{feature_id}: referenced csv missing: {tc_file}")
            continue
        processed_csv_files.add(tc_file)

        rows = load_csv_rows(csv_path)
        if not rows:
            errors.append(f"{feature_id}: csv has no data rows: {tc_file}")
            continue

        seen_rules = set()
        assumed_count = 0
        for idx, row in enumerate(rows, start=2):
            tc_id = (row.get("TC ID") or "").strip()
            missing_fields = [
                name for name in ["TC ID", "ASSUMED", "기능", "Rule", "테스트 목적", "사전 조건", "테스트 단계", "기대 결과", "우선순위", "분류", "관련 기획서 페이지"]
                if not (row.get(name) or "").strip()
            ]
            if missing_fields:
                errors.append(f"{tc_file}:{idx} missing required fields: {', '.join(missing_fields)}")

            tc_number = extract_tc_number(tc_id)
            if tc_number is None:
                errors.append(f"{tc_file}:{idx} invalid TC ID format: {tc_id!r}")
            else:
                all_tc_ids.append((tc_file, tc_id, tc_number))
                if tc_id in duplicate_guard:
                    errors.append(f"{tc_file}:{idx} duplicated TC ID: {tc_id}")
                duplicate_guard.add(tc_id)

            assumed = (row.get("ASSUMED") or "").strip().upper()
            if assumed == "Y":
                assumed_count += 1
            elif assumed != "N":
                errors.append(f"{tc_file}:{idx} invalid ASSUMED value: {assumed!r}")

            priority = (row.get("우선순위") or "").strip()
            if priority not in {"High", "Medium", "Low"}:
                errors.append(f"{tc_file}:{idx} invalid priority: {priority!r}")

            category = (row.get("분류") or "").strip()
            if category not in {"Positive", "Negative", "Boundary"}:
                errors.append(f"{tc_file}:{idx} invalid category: {category!r}")

            result = (row.get("결과") or "").strip()
            if result and result not in {"Pass", "Fail", "N/A"}:
                errors.append(f"{tc_file}:{idx} invalid 결과 value: {result!r}")

            rule_value = normalize_rule_value(row.get("Rule", ""))
            if rule_value:
                seen_rules.add(rule_value)

            semantic_rows.append(
                {
                    "tc_file": tc_file,
                    "row_no": idx,
                    "tc_id": tc_id or f"{tc_file}:{idx}",
                    "feature": row.get("기능", "").strip(),
                    "condition_text": normalize_free_text(row.get("사전 조건", "")),
                    "step_text": normalize_free_text(row.get("테스트 단계", "")),
                    "condition_tokens": tokenize_text(row.get("사전 조건", "")),
                    "purpose_tokens": tokenize_text(row.get("테스트 목적", "")),
                    "expected_tokens": tokenize_text(row.get("기대 결과", "")),
                }
            )

        if assumed_count:
            warnings.append(f"{feature_id}: ASSUMED=Y rows {assumed_count}개")

        for rule in rules:
            rule_id = rule.get("rule_id")
            if rule_id and rule_id not in seen_rules:
                errors.append(f"{feature_id}: uncovered rule {rule_id}")

            boundary_conditions = rule.get("boundary_conditions") or []
            if boundary_conditions:
                matched_rows = [row for row in rows if normalize_rule_value(row.get("Rule", "")) == rule_id]
                rule_text = " ".join((row.get("Rule") or "") + " " + (row.get("테스트 목적") or "") for row in matched_rows)
                for marker in ("BV-MIN", "BV-EXACT", "BV-MAX"):
                    if marker not in rule_text:
                        errors.append(f"{feature_id}: boundary case missing for {rule_id} -> {marker}")

    for tc_file, csv_path in csv_map.items():
        if tc_file in processed_csv_files:
            continue
        warnings.append(f"inventory does not reference csv: {tc_file}")
        rows = load_csv_rows(csv_path)
        for idx, row in enumerate(rows, start=2):
            tc_id = (row.get("TC ID") or "").strip()
            semantic_rows.append(
                {
                    "tc_file": tc_file,
                    "row_no": idx,
                    "tc_id": tc_id or f"{tc_file}:{idx}",
                    "feature": row.get("기능", "").strip(),
                    "condition_text": normalize_free_text(row.get("사전 조건", "")),
                    "step_text": normalize_free_text(row.get("테스트 단계", "")),
                    "condition_tokens": tokenize_text(row.get("사전 조건", "")),
                    "purpose_tokens": tokenize_text(row.get("테스트 목적", "")),
                    "expected_tokens": tokenize_text(row.get("기대 결과", "")),
                }
            )

    sorted_tc_numbers = sorted(all_tc_ids, key=lambda item: item[2])
    for prev, current in zip(sorted_tc_numbers, sorted_tc_numbers[1:]):
        if current[2] != prev[2] + 1:
            warnings.append(f"TC ID sequence gap: {prev[1]} -> {current[1]}")

    seen_duplicate_pairs: set[tuple[str, str]] = set()
    for idx, left in enumerate(semantic_rows):
        for right in semantic_rows[idx + 1:]:
            if left["tc_file"] == right["tc_file"] and left["feature"] == right["feature"]:
                continue

            step_same = bool(left["step_text"]) and left["step_text"] == right["step_text"]
            condition_score = jaccard_similarity(left["condition_tokens"], right["condition_tokens"])
            expected_score = jaccard_similarity(left["expected_tokens"], right["expected_tokens"])
            purpose_score = jaccard_similarity(left["purpose_tokens"], right["purpose_tokens"])

            is_duplicate_candidate = (
                step_same and condition_score >= 0.7 and (expected_score >= 0.5 or purpose_score >= 0.5)
            ) or (
                condition_score >= 0.6 and expected_score >= 0.5 and purpose_score >= 0.5
            )

            if is_duplicate_candidate:
                pair = tuple(sorted((str(left["tc_id"]), str(right["tc_id"]))))
                if pair in seen_duplicate_pairs:
                    continue
                seen_duplicate_pairs.add(pair)
                warnings.append(
                    "semantic duplicate candidate: "
                    f"{left['tc_id']} ({left['tc_file']}:{left['row_no']}) <-> "
                    f"{right['tc_id']} ({right['tc_file']}:{right['row_no']})"
                )

    progress_path = project_dir / "tc_progress.json"
    if progress_path.exists():
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
        summary = progress.get("session_summary", {})
        generated = summary.get("total_tc_generated")
        if isinstance(generated, int) and generated != len(all_tc_ids):
            errors.append(
                f"tc_progress total_tc_generated mismatch: summary={generated}, actual={len(all_tc_ids)}"
            )

    for message in warnings:
        print(f"WARN  {message}")
    for message in errors:
        print(f"ERROR {message}")

    if errors:
        print(f"\nFAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1

    print(f"OK: validation passed with {len(warnings)} warning(s)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate TC inventory and CSV outputs")
    parser.add_argument("--project", required=True, help="Project directory containing tc_inventory.json and tc_output/")
    args = parser.parse_args()
    return validate_project(Path(args.project))


if __name__ == "__main__":
    raise SystemExit(main())
