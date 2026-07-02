# 주주배정 유상증자 트래커

DART 주요사항보고서를 매일 스캔해서 "주주배정후 실권주 일반공모" 방식의 유상증자만
자동으로 목록화하고, 각 건마다 앞서 만든 것과 같은 형태의 타임라인 페이지를 생성합니다.
1차 발행가액 확정, 정정공시가 뜨면 해당 페이지가 자동으로 갱신됩니다.

## 준비물

1. DART Open API 인증키 발급 — https://opendart.fss.or.kr → 인증키 신청/관리
2. 이 폴더를 GitHub 레포로 올린 뒤 **Settings → Secrets and variables → Actions**에서
   `DART_API_KEY`라는 이름으로 발급받은 키를 등록
3. **Settings → Pages**에서 Source를 `main` 브랜치 `/root`로 설정

이후 `https://[username].github.io/[repo명]` 으로 접속하면 목록 페이지가 뜹니다.

## 동작 방식

- `.github/workflows/daily-scan.yml`이 매일 KST 07:00에 자동 실행됩니다
  (Actions 탭 → Run workflow로 수동 실행도 가능)
- `scripts/scan.py`: 오늘 접수된 주요사항보고 중 "유상증자결정"을 걸러내고, 원문에서
  "주주배정후 실권주 일반공모" 문구가 있는 건만 `data/offerings.json`에 저장
- 정정 공시(`[기재정정]유상증자결정`)가 들어오면 "최초제출일" 필드를 기준으로 기존
  레코드를 찾아 갱신하고, 정정 이력에 추가
- `scripts/render.py`: `data/offerings.json` → `index.html`(목록) + `offerings/*.html`(상세)
  을 생성
- 변경사항이 있으면 GitHub Actions가 자동 커밋 → Pages가 재배포

## 정확히 알아두시면 좋은 점

- DART 원문(document.xml)의 표 구조는 회사·시점마다 조금씩 다를 수 있어서, 정규식 기반
  필드 추출(`parse_offering.py`)이 100% 완벽하진 않습니다. 필드 하나가 안 잡혀도 나머지는
  정상 작동하도록 개별적으로 방어해뒀지만, 실제 운영 전에 최근 공시 몇 건으로 한 번
  테스트해보고 라벨 정규식을 다듬는 걸 추천드립니다.
- `document.xml` 응답이 zip으로 오는 경우와 xml 그대로 오는 경우를 모두 처리하도록
  방어 코드를 넣었습니다 (DART API에서 흔한 케이스입니다).
- DART 인증키는 하루 호출 횟수 제한이 있습니다. 정확한 한도는 인증키 관리 페이지에서
  확인해두시는 게 안전합니다. 하루 스캔에 필요한 호출 수는 "그날 접수된 유상증자결정
  공시 건수 × (list.json 1회 + document.xml 1회)" 정도라 보통은 여유롭습니다.
- 정정공시가 최초 공시보다 먼저 스캔되는 경우(같은 날 발생 시)는 원본을 못 찾을 수
  있는데, 이 경우 로그에 `[주의]`로 남기고 건너뛰도록 만들어뒀습니다. 다음 날 재실행 시
  자연히 잡힙니다.

## 로컬 테스트

```bash
cd scripts
export DART_API_KEY=발급받은키
pip install requests
python scan.py
python render.py
```

## 확장 아이디어

- `parse_offering.py`에 CB/BW 발행결정, 주식관련사채 발행결정 등 다른 공시 유형을 추가해서
  통합 모니터링 대시보드로 확장 가능 (기존에 만들어두신 DART 모니터링 파이프라인과
  같은 패턴)
- Slack/텔레그램 웹훅을 `scan.py` 끝에 추가하면 신규 건 등록 시 알림 발송
