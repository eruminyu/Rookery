# Rookery

치지직·TwitCasting·X Spaces·YouTube 라이브를 감시해 자동 녹화하고, VOD 다운로드와
채팅 아카이브·통계·Discord 알림까지 하나의 웹 UI에서 관리하는 **개인용** 도구.

FastAPI(Python 3.12) + React 19 / TypeScript / Vite / Tailwind CSS v4.
**실사용 중인 프로그램이다.** 동작이 깨지면 실제 녹화가 실패한다.

## 지금 무슨 작업 중인가

`refactor/notification-pipeline` 브랜치에서 진행 중이다.
**작업을 시작하기 전에 [`docs/handoff-2026-08-25.md`](docs/handoff-2026-08-25.md)를 읽을 것.**
지금까지의 결정과 그 근거, 남은 일, 환경 함정이 전부 거기 있다.

계획된 작업은 모두 끝났다. 리포지토리는 `eruminyu/Rookery`이고 코드의 슬러그도 맞춰져 있다.

살아있는 문서는 이 하나뿐이다 — `docs/handoff-2026-08-25.md`.
`docs/done-*.md`와 `plan-*.md`는 **과거 기록**이다. 현재 상태를 반영하지 않으니
참고만 하고 고치지 말 것.

## 검증

작업 후 반드시 실행하고 결과를 보고한다.

```bash
cd backend && .venv/Scripts/python.exe -m pytest -q
cd frontend && npx tsc --noEmit -p tsconfig.json
cd frontend && npm run build
```

- **기준선: `194 passed, 29 skipped`.** 줄어들면 안 된다.
- 샌드박스에서 `PermissionError: ...Temp\pytest-of-user`로 무더기 실패하면 코드 문제가
  아니라 임시 디렉토리 권한 문제다. `--basetemp=<쓰기 가능한 경로>`로 우회한다.
- 셸에 node가 PATH에 없을 수 있다. `C:\Program Files\nodejs`를 직접 잡는다.

## 규칙

- **API 계약을 바꾸지 않는다.** 엔드포인트·필드명·페이로드 구조 그대로. 필드 추가는 허용.
- **주석은 한국어로.** 무엇을 하는지가 아니라 **왜 그런지**를 적는다.
- **줄바꿈은 건드리는 파일의 기존 방식을 유지한다.** 저장소 대부분이 CRLF다.
  `.gitattributes`가 `*.sh`는 LF, `*.bat`은 CRLF로 고정한다 —
  셸 스크립트가 CRLF면 셔뱅이 `bash\r`로 읽혀 원라이너 설치가 실패한다.
- **`git add --renormalize`를 쓰지 않는다.** `.gitattributes`와 무관하게 저장소 전체를
  재정규화해서, 건드리지도 않은 파일 50여 개가 줄바꿈만 바뀐 채 staged 된다.
- UI는 원시 색(`zinc-*`)이 아니라 `frontend/src/index.css`의 `@theme` 토큰
  (`bg-surface-*`, `text-ink*`, `border-line*`)을 쓴다. Tailwind v4라 설정 파일이 없다.
- 공통 UI는 `frontend/src/components/ui/primitives.tsx`에 추가한다. 페이지 안에서
  로컬 컴포넌트를 만들지 않는다.
- 커밋은 영어 제목 + 한국어 본문. 푸시는 요청받았을 때만.

## 실행

```bash
scripts/manage.sh install     # Linux/macOS — 설치·업데이트 통합 진입점
scripts\manage.bat install    # Windows
scripts\manage.bat dev        # 백엔드 + 프론트엔드 개발 서버
```

설정은 프로젝트 루트 `.env`에서 읽는다(`backend/app/core/config.py`의 `_resolve_env_file`).
`.env`, `backend/data/`, `.venv`, `node_modules`, `backend/app/static/`은 gitignore 대상이다.
