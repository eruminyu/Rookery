# Codex 작업 지시서 — Discord 슬래시 전용화 / 알림 설정 재배치

## 프로젝트

- 경로: `C:\Workspace\Signal-Recorder`
- 브랜치: `refactor/notification-pipeline` (이 브랜치에서 작업)
- 스택: FastAPI(Python 3.12) + React 19 / TypeScript / Vite / Tailwind CSS v4
- Python 실행: `backend\.venv\Scripts\python.exe` (venv 구성됨)
- Node: `C:\Program Files\nodejs` (PATH에 없을 수 있으니 절대 경로로 실행)

개인용으로 **실사용 중인** 프로그램이다. 치지직 라이브를 감지·녹화하고
유튜브/트윗캐스팅/X Spaces를 서브 플랫폼으로 지원한다. 동작이 깨지면 실제 녹화가 실패한다.

---

## 이미 끝난 작업 — 되돌리지 말 것

`backend/app/services/discord_bot.py`에 **명령어 권한 검사가 이미 적용되어 있다.**
아래 구조를 그대로 유지한 채 작업한다.

| 요소 | 위치 | 역할 |
|------|------|------|
| `_is_authorized(user_id, channel_id)` | `discord_bot.py` | 권한 판정 단일 지점 |
| `_prefix_authorization_check` | 동일 | 프리픽스 명령 전역 check (`bot.add_check`) |
| `_AuthorizedCommandTree` | `_build_bot` 내부 | 슬래시 명령 `interaction_check` |
| `_DENIED_MESSAGE` | 동일 | 거부 안내 문구 |
| `discord_command_user_ids` / `discord_command_channel_id` | `config.py`, `settings.py`, `client.ts`, `NotificationsTab.tsx` | 설정 항목 |
| `backend/tests/test_discord_auth.py` | | 권한 판정 테스트 |

판정 규칙(변경 금지):

- `DISCORD_COMMAND_USER_IDS`가 설정되면 해당 사용자만 허용
- `DISCORD_COMMAND_CHANNEL_ID`가 설정되면 해당 채널에서만 허용
- 둘 다 설정되면 **둘 다** 만족해야 허용
- 둘 다 비어 있으면 `DISCORD_NOTIFICATION_CHANNEL_ID`를 채널 조건으로 사용
- 어느 것도 없으면 **거부**(fail-closed)

기준선: `188 passed, 29 skipped`.

---

## 작업 A — 프리픽스 명령 제거, 슬래시 전용화

### 배경

현재 8개 명령이 `!` 프리픽스와 슬래시로 **완전히 중복 구현**되어 있다
(`backend/app/services/discord_bot.py`의 `_register_commands`).
프리픽스 명령 때문에 `intents.message_content = True`가 필요한데, 이는 Discord
개발자 포털에서 별도로 켜야 하는 privileged intent라 봇 설정의 최대 진입 장벽이다.
실제로 `PrivilegedIntentsRequired` 처리 분기까지 들어가 있다.

슬래시 전용으로 가면 privileged intent 요구가 사라지고 봇 코드가 절반으로 줄어든다.

### 구현 내용

- `@bot.command(...)` 프리픽스 핸들러 전부 제거. `@bot.tree.command(...)`만 남긴다
- `intents.message_content = True` 제거 → `discord.Intents.default()`만 사용
- `PrivilegedIntentsRequired` 처리 분기 제거 또는 메시지 수정
- `_prefix_authorization_check`와 `bot.add_check(...)` 호출 제거.
  **`_is_authorized`와 `_AuthorizedCommandTree`는 반드시 유지한다**
- `on_command_error` 핸들러 제거 (프리픽스 전용이다)
- 모듈 docstring의 명령어 목록에서 프리픽스 표기 제거
- 슬래시 커맨드 동기화 로직(`bot.tree.copy_global_to` + `sync`)은 **유지**
- `backend/tests/test_discord_auth.py`의 `TestBotWiring`에서 프리픽스 관련
  단언(`bot._checks`, `bot.commands`, `test_prefix_check_denies_and_replies`)을
  슬래시 기준으로 옮긴다. 테스트를 삭제하지 말고 대상만 바꿀 것

### 함께 갱신할 문서

- `README.md`의 Discord 명령어 안내
- `docs/` 내 Discord 관련 안내에서 `!command` 표기 제거

---

## 작업 B — 알림 설정 웹훅 우선 재배치

**프론트엔드만 건드린다. API 계약 변경 없음.**

### 배경

알림 전송 채널은 두 가지고 이미 둘 다 구현되어 있다
(`backend/app/services/notifications.py` — `DiscordWebhookTransport`, 봇 폴백 포함).

| | 설정 비용 | 얻는 것 |
|---|---|---|
| 웹훅 | 채널 설정에서 URL 복사, 30초 | 모든 알림 |
| 봇 | 개발자 포털에서 앱 생성·토큰 발급 | 알림 + 원격 제어 |

현재 `frontend/src/components/settings/NotificationsTab.tsx`는 봇 카드가 먼저 오고
웹훅이 "폴백"으로 뒤에 있다. 그래서 알림만 필요한 사용자도 봇을 만들어야 하는 것처럼
보인다. 대부분은 웹훅으로 충분하다.

### 구현 내용

- 웹훅 카드를 **맨 위 기본 경로**로 올린다. 제목에서 "폴백" 표현을 빼고
  "권장" 배지를 붙인다
- 봇 카드를 그 아래로 내리고 **접힌 고급 섹션**으로 만든다.
  헤더 문구: "디스코드에서 원격 제어까지 하려면"
- 봇 카드 안에 이미 있는 권한 설정 필드 2개(`명령어 허용 사용자 ID`,
  `명령어 허용 채널 ID`)는 그대로 둔다
- 카드/헤더는 `frontend/src/components/ui/primitives.tsx`의 `Card`, `CardHeader` 사용.
  접기 UI에 필요한 프리미티브가 없으면 `primitives.tsx`에 추가한다
  (탭 안에서 로컬 컴포넌트 생성 금지)
- 저장 핸들러, `dirty` 추적(`markDirty` / `onDirtyChange`),
  `api.updateDiscordSettings` 페이로드는 **그대로 유지**

---

## 작업 C — Rookery 리네이밍 (이번 범위 밖)

프로젝트명을 `Signal-Recorder` → `Rookery`로 변경하는 계획이 별도로 있다.
전체 내용은 [`docs/plan-rename-rookery.md`](plan-rename-rookery.md) 참조.

**작업 A, B가 병합된 뒤 별도 브랜치에서 진행한다.** 리네이밍은 60여 파일을
건드리므로 먼저 하면 위 작업들이 전부 충돌한다.

---

## 제약 / 주의사항

1. **API 계약을 바꾸지 말 것.** 엔드포인트·필드명·페이로드 구조 그대로.

2. **주석은 한국어로.** 무엇을 하는지가 아니라 **왜 그런지**를 적는다.

3. **줄바꿈은 건드리는 파일의 기존 방식을 유지.** 저장소 대부분이 CRLF다.
   파일 전체 줄바꿈을 바꾸면 diff가 부풀어 리뷰가 불가능해진다.

4. **검증은 반드시 실행하고 결과를 보고할 것:**
   ```bash
   cd backend && .venv\Scripts\python.exe -m pytest -q
   cd frontend && npx tsc --noEmit -p tsconfig.json
   cd frontend && npm run build
   ```
   pytest 기준선은 **188 passed, 29 skipped**. 줄어들면 안 된다.

5. **커밋은 작업 A / B를 나눠서** 각각 하나씩.
   커밋 메시지는 영어 제목 + 한국어 본문, 마지막 줄에:
   ```
   Co-Authored-By: Codex <noreply@openai.com>
   ```

6. 실행해서 확인:
   ```bash
   backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
   ```
   → `http://localhost:8000`

---

## 알아두면 좋은 함정

- `claude/amazing-albattani-307981` 브랜치와 그 워크트리는 **`main` 분기라 폐기 대상**이다.
  merge하지 말 것. 거기 있던 작업은 이미 현재 브랜치에 이식되었다.
- `discord.py`는 선택적 의존성이다. import 실패 시에도 앱이 기동되어야 한다.
  테스트는 `pytest.importorskip`으로 처리되어 있다.
- `_build_bot`은 **동기 함수**다 (`main`에서는 async였다). 테스트에서 await하지 말 것.
- 샌드박스 환경에서 pytest가 `PermissionError: ...Temp\pytest-of-user`로 무더기 실패하면
  코드 문제가 아니라 임시 디렉토리 권한 문제다. `--basetemp=<쓰기 가능한 경로>`로 우회한다.
- **fail-closed는 기존 사용자에게 동작 변경이다.** 지금까지 아무 채널에서나
  명령을 쓰던 사용자는 알림 채널 밖에서 거부당한다. 릴리즈 노트에 명시할 것.
- `frontend/tsconfig.tsbuildinfo`는 gitignore 대상이다. 커밋하지 말 것.
- Tailwind v4는 `tailwind.config.js`가 없다. 토큰은 `frontend/src/index.css`의
  `@theme` 블록에 있다. `zinc-*` 같은 원시 색 대신 의미 토큰
  (`bg-surface-*`, `text-ink*`, `border-line*`)을 쓴다.
- 백엔드 테스트는 `conftest.py`가 임시 SQLite와 임시 `.env`를 주입한다.
  이 격리를 우회하면 개발자의 실제 `.env`가 덮어써진다.
- 빌드 시 "chunks larger than 500 kB" 경고는 기존부터 있던 것이다. 범위 밖.
