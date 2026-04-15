# TC 에이전트 프로젝트

QA 엔지니어를 위한 TC 작성 및 이슈 등록용 프롬프트 운영 프로젝트입니다.

## 사용 방법

| 작업 | 명령어 |
|------|--------|
| 기획서 분석 및 TC 작성 | `/tc input/기획서.pdf` |
| Notion 이슈 등록 | `/issue 이슈 설명` |

## 운영 원칙

- 이 저장소의 중심은 실행 코드보다 `prompts/*.md` 규칙이다
- `tc_inventory.json`이 상태의 단일 기준이며, `tc_progress.json`은 집계용이다
- Claude가 생성한 CSV는 완료 처리 전에 검증한다
- 권장 검증 명령:
  `python3 scripts/validate_tc_outputs.py --project output/active_project/[문서폴더]`
- progress 동기화 명령:
  `python3 scripts/sync_tc_progress.py --project output/active_project/[문서폴더]`
- Excel 생성 명령:
  `python3 scripts/export_tc_excel.py --project output/active_project/[문서폴더]`

## 프로젝트 구조

```
.claude/commands/tc.md   # /tc 슬래시 커맨드
.claude/commands/issue.md # /issue 슬래시 커맨드
prompts/tc_system_prompt.md    # TC 생성 system prompt 본문
prompts/issue_system_prompt.md # 이슈 등록 system prompt 본문
schemas/tc_inventory.schema.json # tc_inventory 구조 기준
schemas/tc_progress.schema.json  # tc_progress 구조 기준
scripts/validate_tc_outputs.py # TC 산출물 정합성 검증
scripts/sync_tc_progress.py    # tc_progress 집계 동기화
scripts/export_tc_excel.py     # CSV -> Excel 변환
docs/workflow.md         # 사람이 보는 운영 흐름
```
