"""
TC 에이전트 시스템 — CLI 진입점

사용법:
  python main.py tc --pdf input/기획서.pdf --pages 120 --sheet 채팅방
  python main.py issue --description "로그인 버튼이 비활성화됨"
  python main.py issue --file issues.txt
"""
import argparse
import json
import sys
from pathlib import Path


def cmd_tc(args):
    from agents.tc_agent import (
        upload_pdf,
        build_feature_inventory,
        generate_tc_for_feature,
        save_tc_csv,
        build_excel,
    )

    print("=" * 60)
    print("TC 에이전트 시작")
    print("=" * 60)

    # 1. PDF 업로드
    print("\n[1/4] PDF 업로드")
    file_id = upload_pdf(args.pdf)

    # 2. 기능 인벤토리 생성
    print("\n[2/4] 기능 인벤토리 생성")
    inventory = build_feature_inventory(file_id, args.pages)

    inventory_path = Path("input") / "tc_inventory.json"
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n  인벤토리 저장: {inventory_path}")
    print(f"  총 기능 수: {len(inventory)}개")

    # 사용자 확인 (제외 기능 / 우선순위 조정)
    if not args.yes:
        print("\n기능 인벤토리를 확인하세요:")
        for fid, f in inventory.items():
            print(f"  {fid}: {f.get('feature_name')} [{f.get('status')}]")
        answer = input("\n이대로 TC를 생성할까요? (y/n): ").strip().lower()
        if answer != "y":
            print("취소되었습니다. tc_inventory.json을 수정 후 다시 실행하세요.")
            sys.exit(0)

    # 3. TC 생성 (기능별 순차)
    print("\n[3/4] TC 생성")
    progress = {"total_tc_generated": 0}
    csv_files = []

    for feature_id, feature in inventory.items():
        rows = generate_tc_for_feature(feature, progress)
        if rows:
            csv_path = save_tc_csv(feature_id, feature.get("feature_name", feature_id), rows)
            csv_files.append(csv_path)

    # 진행 상태 저장
    progress_path = Path("input") / "tc_progress.json"
    progress_path.write_text(
        json.dumps({
            "session_summary": {
                "total_features": len(inventory),
                "completed_features": len(csv_files),
                "total_tc_generated": progress["total_tc_generated"],
            },
            "completed": list(inventory.keys()),
            "csv_files": csv_files,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n  진행 상태 저장: {progress_path}")

    # 4. Excel 마스터 생성
    print("\n[4/4] Excel 마스터 생성")
    pdf_stem = Path(args.pdf).stem
    output_path = str(Path("output") / f"{pdf_stem}_TC_마스터.xlsx")
    sheet_name = args.sheet or pdf_stem
    build_excel(csv_files, sheet_name, output_path)

    print("\n" + "=" * 60)
    print(f"완료: TC {progress['total_tc_generated']}개 생성")
    print(f"Excel: {output_path}")
    print("=" * 60)


def cmd_issue(args):
    from agents.issue_agent import generate_issue_report, format_for_display

    # 입력 소스 결정
    if args.file:
        description = Path(args.file).read_text(encoding="utf-8")
    elif args.description:
        description = args.description
    else:
        print("이슈 설명을 입력하세요 (Ctrl+D로 종료):")
        description = sys.stdin.read()

    print("\n이슈 리포트 생성 중...")
    issues = generate_issue_report(description)

    print("\n" + "=" * 60)
    print(format_for_display(issues))
    print("=" * 60)

    # JSON 출력 옵션
    if args.json:
        print("\n[JSON]")
        print(json.dumps(issues, ensure_ascii=False, indent=2))

    return issues


def main():
    parser = argparse.ArgumentParser(
        description="TC 에이전트 / 이슈 리포트 에이전트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python main.py tc --pdf input/기획서.pdf --pages 120
  python main.py tc --pdf input/기획서.pdf --pages 120 --sheet 채팅방 --yes
  python main.py issue --description "홈 화면에서 배너 클릭 시 앱 크래시"
  python main.py issue --file issues.txt --json
        """,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # TC 커맨드
    tc_cmd = sub.add_parser("tc", help="기획서 PDF → TC 생성")
    tc_cmd.add_argument("--pdf",   required=True, help="기획서 PDF 경로")
    tc_cmd.add_argument("--pages", required=True, type=int, help="총 페이지 수")
    tc_cmd.add_argument("--sheet", default=None, help="Excel 시트명 (기본: PDF 파일명)")
    tc_cmd.add_argument("--yes",   action="store_true", help="기능 인벤토리 확인 단계 건너뜀")
    tc_cmd.set_defaults(func=cmd_tc)

    # 이슈 커맨드
    issue_cmd = sub.add_parser("issue", help="이슈 설명 → Notion 등록 속성 생성")
    issue_cmd.add_argument("--description", "-d", default=None, help="이슈 설명 (인라인)")
    issue_cmd.add_argument("--file",        "-f", default=None, help="이슈 설명 파일 경로")
    issue_cmd.add_argument("--json",        action="store_true", help="JSON 형식으로도 출력")
    issue_cmd.set_defaults(func=cmd_issue)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
