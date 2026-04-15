# TC 에이전트 워크플로우

## 목적

이 저장소는 실행 앱보다 프롬프트 운영 규칙을 중심으로 TC와 이슈 산출물을 만드는 구조다.

## 흐름

1. 사용자가 `/tc input/기획서.pdf` 또는 `/issue 이슈 설명`을 실행한다.
2. `.claude/commands/*.md`가 실제 프롬프트 본문 파일을 읽도록 연결한다.
3. Claude는 `prompts/*_system_prompt.md` 규칙에 따라 산출물을 만든다.
4. 산출물은 `output/` 아래 프로젝트 폴더에 저장한다.
5. 작업 중 프로젝트는 `output/active_project/` 아래 1개만 유지한다.
6. 루트에서 `make all`로 집계, 검증, Excel 생성을 한 번에 실행한다.

## 상태 파일 원칙

- `tc_inventory.json`이 상태의 단일 기준이다.
- `tc_progress.json`은 집계와 작업 히스토리용이다.
- 실제 완료/진행 여부 판단은 `tc_inventory.json`의 `tc_status`를 우선한다.

## 권장 검증 명령

```bash
make all
```
