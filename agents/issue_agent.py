"""
이슈 리포트 에이전트
이슈 설명 텍스트 → Notion 데이터베이스 등록용 속성값 생성

참조 우선순위:
  1. tc_inventory.json에 관련 기능이 있으면 → 해당 기능의 rule/흐름을 컨텍스트로 사용
  2. 없으면 → 일반 모바일 앱 UX 관행 기준으로 생성 (기존 동작)
"""
import json
from pathlib import Path

import anthropic

client = anthropic.Anthropic()

# 시스템 프롬프트 로드 (프롬프트 캐싱 대상)
_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "issue.md"
SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")

# tc_inventory.json 기본 경로
_INVENTORY_PATH = Path(__file__).parent.parent / "input" / "tc_inventory.json"

# Notion 등록 속성 스키마
_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "제목":     {"type": "string"},
                    "위험도":   {
                        "type": "string",
                        "enum": ["Blocker", "Critical", "Major", "Minor", "Trivial"],
                    },
                    "재현 절차": {"type": "string"},
                    "재현 결과": {"type": "string"},
                },
                "required": ["제목", "위험도", "재현 절차", "재현 결과"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["issues"],
    "additionalProperties": False,
}


def _load_inventory(inventory_path: Path | None) -> dict:
    """tc_inventory.json을 로드한다. 없으면 빈 dict 반환."""
    path = inventory_path or _INVENTORY_PATH
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _find_relevant_features(issue_description: str, inventory: dict) -> list[dict]:
    """
    이슈 설명과 관련 있는 기능을 인벤토리에서 추출한다.
    Claude에게 feature_id 목록만 뽑아달라고 요청해 토큰을 최소화한다.
    관련 기능이 없으면 빈 리스트 반환.
    """
    if not inventory:
        return []

    # 인벤토리 요약 (feature_id + feature_name + description만 — rules는 아직 전달 안 함)
    summary = {
        fid: {
            "feature_name": f.get("feature_name", ""),
            "description":  f.get("description", ""),
        }
        for fid, f in inventory.items()
    }

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": (
                "아래 이슈와 관련된 feature_id를 JSON 배열로만 반환하세요. "
                "관련 기능이 없으면 []를 반환하세요.\n\n"
                f"이슈:\n{issue_description}\n\n"
                f"기능 목록:\n{json.dumps(summary, ensure_ascii=False)}"
            ),
        }],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "feature_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        }
                    },
                    "required": ["feature_ids"],
                    "additionalProperties": False,
                },
            }
        },
    )

    text = next(b.text for b in response.content if b.type == "text")
    matched_ids = json.loads(text).get("feature_ids", [])

    # 매칭된 기능의 전체 정보(rules 포함)만 반환
    return [
        {"feature_id": fid, **inventory[fid]}
        for fid in matched_ids
        if fid in inventory
    ]


def _build_user_message(issue_description: str, relevant_features: list[dict]) -> str:
    """
    이슈 설명 + (있으면) 관련 기능 컨텍스트를 합쳐 최종 user 메시지를 만든다.
    """
    if not relevant_features:
        return issue_description

    feature_ctx = json.dumps(relevant_features, ensure_ascii=False, indent=2)
    return (
        f"{issue_description}\n\n"
        f"---\n"
        f"[기획서 기능 정보 — 재현 절차 작성 시 아래 rule과 흐름을 우선 참고하세요]\n"
        f"{feature_ctx}"
    )


def generate_issue_report(
    issue_description: str,
    inventory_path: Path | None = None,
) -> list[dict]:
    """
    이슈 설명(단건 또는 다건) → Notion 등록용 속성 리스트 반환

    Args:
        issue_description: 사용자가 입력한 이슈 설명
        inventory_path: tc_inventory.json 경로 (기본: input/tc_inventory.json)

    Returns:
        [{"제목": ..., "위험도": ..., "재현 절차": ..., "재현 결과": ...}, ...]
    """
    # 1. 인벤토리 로드
    inventory = _load_inventory(inventory_path)

    # 2. 관련 기능 탐색
    if inventory:
        print("  tc_inventory.json 참조 중...")
        relevant = _find_relevant_features(issue_description, inventory)
        if relevant:
            names = [f.get("feature_name", f["feature_id"]) for f in relevant]
            print(f"  관련 기능 {len(relevant)}개 발견: {', '.join(names)}")
        else:
            print("  관련 기능 없음 → 일반 UX 관행 기준으로 생성")
    else:
        relevant = []
        print("  tc_inventory.json 없음 → 일반 UX 관행 기준으로 생성")

    # 3. 이슈 리포트 생성
    user_message = _build_user_message(issue_description, relevant)

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": user_message,
        }],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": _OUTPUT_SCHEMA,
            }
        },
    )

    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)["issues"]


def format_for_display(issues: list[dict]) -> str:
    """CLI 출력용 포맷팅"""
    lines = []
    for i, issue in enumerate(issues, 1):
        if len(issues) > 1:
            lines.append(f"=== 이슈 {i} ===")
        lines.append(f"제목: {issue['제목']}")
        lines.append(f"위험도: {issue['위험도']}")
        lines.append(f"재현 절차:\n{issue['재현 절차']}")
        lines.append(f"재현 결과: {issue['재현 결과']}")
        if i < len(issues):
            lines.append("")
    return "\n".join(lines)
