# TC_에이전트

기획서를 바탕으로 테스트 케이스 CSV를 생성하고, 진행 상태를 동기화하고, 결과를 검증한 뒤 Excel 마스터 파일로 내보내기 위한 운영 저장소다.

GitHub에서는 이 `README.md`를 기준 문서로 사용한다. 운영 절차, 검증 기준, QA 확인 방법도 여기서 같이 관리한다.

## 목적

- Claude: 기획 해석, 기능 정리, rule 정리, TC 초안 작성
- 스크립트: 집계 동기화, 정합성 검증, Excel 생성
- QA 사람: 최종 판단, 우선순위 조정, `ASSUMED` 승인, 중복 여부 판단

## 주요 경로

- `input/`: 원본 기획서 입력
- `output/active_project/`: 현재 작업 중인 프로젝트
- `output/completed/`: 완료된 프로젝트
- `scripts/`: 동기화, 검증, export 스크립트
- `schemas/`: 데이터 구조 정의
- `prompts/`: 시스템 프롬프트

## 기본 명령

루트에서 실행한다.

```bash
make sync
make validate
make export
make all
```

기본 동작:

- `make sync`: `tc_inventory.json` 기준으로 집계와 `tc_progress.json`을 동기화
- `make validate`: CSV, inventory, progress 정합성 검증
- `make export`: `tc_output/*.csv`를 `TC_마스터.xlsx`로 변환
- `make all`: `sync -> validate -> export` 순서로 일괄 실행

특정 프로젝트를 직접 지정하려면:

```bash
make all PROJECT="output/active_project/[문서폴더]" SHEET_NAME="[시트명]"
```

## 작업 절차

### 1. TC 생성 요청

Claude에게 `/tc`로 기획서 분석과 TC 생성을 요청한다.

예시:

```text
/tc input/CDP-20260204C 아이콘 관리 v1.0.5 20260407.pdf
```

기대 산출물:

- `tc_inventory.json`
- `tc_output/*.csv`
- 필요 시 `tc_progress.json`

### 2. QA 1차 확인

생성 직후 아래를 먼저 본다.

- 기능이 빠지지 않았는지
- `ASSUMED=Y`가 필요한 곳에만 들어갔는지
- `partial`, `pending`, `needs_review` 상태가 남아 있는지
- TC가 너무 뭉뚱그려져 있지 않은지
- 같은 의미의 TC가 feature 이름만 바뀐 채 중복 작성되지 않았는지

중복 판단 기준:

- `정책` feature는 최대 개수, 최신순, 우선순위, 승격 같은 규칙 검증 중심으로 둔다
- `유저 화면` feature는 위치, 레이아웃, 화면별 노출 차이 검증 중심으로 둔다
- `사전 조건`, `테스트 단계`, `기대 결과`가 사실상 같으면 같은 TC로 본다
- 기획서 페이지가 달라도 검증 의도가 같으면 하나로 통합 후보로 본다

### 3. progress 동기화

```bash
make sync
```

이 단계에서는 아래를 맞춘다.

- `tc_inventory.json` 기준 집계 재계산
- CSV row 수 기준 `tc_count` 갱신
- `tc_progress.json` 재생성

### 4. 정합성 검증

```bash
make validate
```

검사 항목:

- 필수 컬럼 누락
- `ASSUMED`, `우선순위`, `분류`, `결과` 값 형식
- `rule_id` 기준 누락 rule 존재 여부
- boundary rule의 `BV-MIN / BV-EXACT / BV-MAX` 존재 여부
- TC ID 형식, 중복, 연속성
- `tc_progress.json` 총 TC 수와 실제 CSV row 수 일치 여부

### 5. 경고 확인 방법

`make validate`의 경고는 자동 수정 대상이 아니라 QA 확인 후보다.

확인 순서:

1. 경고 문구에서 `feature_id`, `TC ID`, `파일명`, `행번호`를 확인한다.
2. 해당 CSV 행의 `테스트 목적`, `사전 조건`, `테스트 단계`, `기대 결과`를 읽는다.
3. 기획서 원문 또는 정책과 대조한다.
4. `유지`, `수정`, `삭제`, `번호 재정리` 중 하나로 처리한다.

경고별 해석 기준:

- `ASSUMED=Y`: 기획서에 없는 내용을 임시 가정으로 보완한 것인지 확인한다. 확정 전까지 유지 가능하고, 확정되면 `N`으로 정리한다.
- `TC ID sequence gap`: 누락된 TC인지, 삭제 후 비어 있는 자리인지, 의도적 공백인지 확인한다. 실제 누락이면 추가하고 단순 공백이면 재채번 여부만 결정한다.
- `semantic duplicate candidate`: 두 TC가 실제로 같은 검증인지, 대상만 다르고 검증 포인트는 같은지, 서로 다른 feature로 분리 유지해야 하는지 확인한다. 검증 의도가 같으면 통합하고 실질 차이가 있으면 유지한다.

실무 판단 질문:

- 이 경고는 실제 누락 또는 오류인가
- 아니면 의도된 작성 결과를 검증기가 보수적으로 잡은 것인가
- 수정하면 중복이 줄어드는가, 아니면 필요한 검증이 사라지는가

Claude에게 요청할 때는 이렇게 적으면 된다.

```text
make validate 경고 기준으로 해당 CSV 행을 검토해서
유지 / 수정 / 삭제 의견을 정리해줘.
semantic duplicate candidate는 두 TC의 차이점까지 같이 설명해줘.
```

### 6. Excel 생성

```bash
make export
```

이 단계에서 `tc_output/*.csv`를 읽어 `TC_마스터.xlsx`를 생성한다.

## 이어서 작업할 때

다음 세션에서 이어서 작업할 때는 상태 파일을 기준으로 요청한다.

권장 첨부:

- `tc_inventory.json`
- `tc_progress.json`
- 기존 `tc_output/*.csv`

예시:

```text
tc_inventory.json, tc_progress.json, 기존 CSV 기준으로 pending 기능부터 이어서 TC 생성해줘.
```

특정 기능만 지정할 수도 있다.

```text
F-007부터 이어서 해줘.
기존 CSV와 중복되지 않게 작성해줘.
```

중복 방지 요청 문구 예시:

```text
기존 tc_output/*.csv를 먼저 보고 feature 역할을 분리해줘.
정책 TC와 화면 TC가 같은 의미로 중복되지 않게 작성해줘.
새 TC를 추가할 때는 기존 TC와 사전 조건 / 테스트 단계 / 기대 결과가 겹치면 재사용 또는 통합해줘.
```

운영 원칙:

- 실제 상태 판단은 `tc_inventory.json`의 `tc_status`를 우선한다
- `tc_progress.json`은 채번과 집계 참고용이다
- 보완 후에는 다시 `make all`을 실행한다

## 검증 실패 시 처리 절차

오류가 나오면 오류 내용을 기준으로 Claude에게 보완 요청한다.

예시:

```text
R-004-02 경계값 TC가 부족해.
BV-MIN / BV-EXACT / BV-MAX 기준으로 보완해줘.
```

```text
F-002에서 uncovered rule이 나왔어.
누락된 rule 기준으로 TC를 추가해줘.
```

```text
기존 CSV 형식은 유지하고, 필수 컬럼 누락 없이 다시 정리해줘.
```

```text
정책/유저화면 간 의미 중복 TC를 제거해줘.
정책에는 규칙 검증만 남기고, 유저화면에는 위치/화면 차이만 남겨줘.
```

보완 후에는 다시 아래를 실행한다.

```bash
make all
```

## 버전 업데이트 시 작업 절차

기획서가 새 버전으로 바뀌면 구버전과 신버전, 기존 상태 파일을 같이 두고 작업한다.

권장 첨부:

- 구버전 PDF
- 신버전 PDF
- 기존 `tc_inventory.json`
- 필요 시 기존 CSV

예시:

```text
구버전 PDF, 신버전 PDF, tc_inventory.json 기준으로 변경 영향 있는 기능만 다시 봐줘.
영향 있는 기능의 rule과 TC만 보완해줘.
```

운영 원칙:

- Claude는 변경 영향을 추정할 수 있지만 정밀 diff를 자동 보장하지 않는다
- 영향이 명확한 기능부터 우선 보완한다
- 불명확하면 `ASSUMED` 또는 `needs_review`로 남기고 사람이 확인한다
- 수정 후 다시 `make all`을 실행한다

## 이슈 작성

이슈 작성은 `/issue`를 사용한다.

예시:

```text
/issue 상품 상세에서 아이콘이 전시 기간 종료 후에도 계속 노출됨
```

Claude는 아래를 정리한다.

- 제목
- 위험도
- 재현 절차
- 재현 결과

기존 TC 또는 기획 맥락이 필요하면 관련 `tc_inventory.json` 또는 CSV를 함께 참고시킨다.

## 권장 작업 루틴

1. `/tc`로 초안 생성
2. QA가 1차 확인
3. `make all` 실행
4. 오류가 있으면 Claude에게 보완 요청
5. 경고와 중복 후보 검토 후 최종 산출물 확정

## 한 줄 요약

- 무엇을 테스트해야 하는가: Claude
- 제대로 작성되었는가: 스크립트
- 실제로 승인할 수 있는가: QA 사람
- 중복 없이 역할이 분리되었는가: Claude와 QA가 함께 확인
