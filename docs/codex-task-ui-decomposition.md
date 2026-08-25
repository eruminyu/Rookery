# Codex 작업 지시서 — Settings / Dashboard 컴포넌트 분해

## 프로젝트

- 경로: `C:\Workspace\Signal-Recorder`
- 브랜치: `refactor/notification-pipeline` (이 브랜치에서 계속 작업)
- 스택: FastAPI(Python 3.12.10) + React 19 / TypeScript 5.8 / Vite 6 / Tailwind CSS v4
- Python 실행: `backend\.venv\Scripts\python.exe` (venv 이미 구성됨)
- Node: v24.19.0, npm 11 (설치됨, `frontend/node_modules` 존재)

개인용으로 **실사용 중인** 프로그램이다. 치지직 라이브를 감지·녹화하고,
유튜브/트윗캐스팅/X Spaces를 서브 플랫폼으로 지원하며 VOD를 다운로드한다.
동작이 깨지면 실제 녹화가 실패하므로 **기능 변경 없는 순수 리팩토링**으로 진행할 것.

---

## 이미 끝난 작업 (그대로 재사용할 것, 다시 만들지 말 것)

### 1. 디자인 토큰 — `frontend/src/index.css`

Tailwind v4 `@theme` 블록에 의미 토큰이 정의되어 있다. **새 컴포넌트는
`zinc-*` 같은 원시 색을 직접 쓰지 말고 반드시 아래 토큰을 쓴다.**

| 토큰 | 용도 |
|------|------|
| `bg-surface-0` | 앱 배경 |
| `bg-surface-1` | 사이드바, 헤더 |
| `bg-surface-2` | 카드 |
| `bg-surface-3` | 카드 위 요소, 입력창 |
| `bg-surface-4` | hover 상태 |
| `border-line` | 기본 구분선 |
| `border-line-strong` | 입력창 테두리 |
| `text-ink` | 제목 |
| `text-ink-muted` | 본문 |
| `text-ink-faint` | 보조 설명 |
| `text-live` / `text-ok` / `text-warn` / `text-danger` / `text-info` | 상태 색 |
| `text-chzzk` / `text-twitcasting` / `text-xspaces` / `text-youtube` | 플랫폼 색 |

강조색은 CSS 변수: `var(--primary)`, `var(--primary-dim)`, `var(--primary-dark)`,
`var(--primary-ring)`, `var(--primary-ink)`.
`--primary-ink`는 **강조색 배경 위에 올릴 글자색**이다. 치지직 그린처럼 밝은
강조색 위에 흰 글자를 쓰면 안 보이므로 반드시 이 변수를 쓴다.

유틸 클래스: `.btn-primary`, `.btn-ghost-primary`, `.input-focus`,
`.surface-raise`, `.nav-active`, `.skeleton`.
반경: `rounded-[var(--radius-card)]`(카드), `rounded-[var(--radius-control)]`(컨트롤).

### 2. UI 프리미티브 — `frontend/src/components/ui/primitives.tsx` (434줄)

```
Card, CardHeader, Field, SettingRow, Input, Select, Switch,
Button, Badge, StatusDot, SegmentedControl, EmptyState, Divider
```

- `Switch`는 `role="switch"` + `aria-checked` + `aria-label`을 내장한다.
- `Button`은 `variant`(primary/secondary/ghost/danger), `icon`(LucideIcon), `loading` 지원.
- `CardHeader`는 `icon`, `title`, `description`, `action`, `tone` 지원.

**부족한 프리미티브가 있으면 이 파일에 추가**한다. 페이지 안에서 로컬로
만들지 말 것.

### 3. 참고 구현 — `frontend/src/components/settings/NotificationsTab.tsx` (531줄)

이미 분해가 끝난 탭이다. **파일 구조·props 형태·주석 스타일을 이것과 맞춘다.**

```tsx
interface Props {
    settings: SettingsType | null;
    onSaved: () => void;                          // 저장 후 상위 상태 갱신
    onDirtyChange?: (dirty: boolean) => void;     // 변경 여부를 상위에 보고
}
```

---

## 작업 A — `frontend/src/pages/Settings.tsx` 분해 (1316줄)

7개 탭이 한 파일에 있다. 각 탭을 `frontend/src/components/settings/` 아래로 뺀다.

| 탭 | 현재 위치 (대략) | 새 파일 |
|----|------------------|---------|
| general | 557~718 | `GeneralTab.tsx` |
| download | 719~893 | `DownloadTab.tsx` |
| auth | 894~1074 | `AuthTab.tsx` |
| notifications | 1075~1083 | **완료됨** (`NotificationsTab.tsx`) |
| appearance | 1084~1202 | `AppearanceTab.tsx` |
| system | 1203~1259 | `SystemTab.tsx` |
| info | 1260~ | `InfoTab.tsx` |

행 번호는 참고용이다. 실제 경계는 `{activeTab === "..." && (` 로 찾을 것.

### 반드시 보존해야 하는 동작

1. **탭 전환 시 미저장 경고** — `isTabDirty(tabId)` / `handleTabChange`.
   각 탭이 `onDirtyChange`로 자기 dirty 상태를 보고하고, `Settings.tsx`는
   탭별 dirty 플래그만 들고 있게 바꾼다. (`notifications`는 이미 이 방식이다 —
   `notificationsDirty` state 참고.)
2. **페이지 이탈 경고** — `useBlocker` + `beforeunload`. `TABS.some(t => isTabDirty(t.id))`.
3. **각 탭의 저장 핸들러와 API 호출** — `api.updateGeneralSettings`,
   `updateDownloadSettings`, `updateVodSettings`, `updateChatSettings`,
   `updateTwitcastingSettings` 등. 요청 페이로드를 바꾸지 말 것.
4. **`loadSettings()` 재조회 흐름** — 저장 성공 후 호출.
5. `DirInput`, `UpdateModal`, `useToast`, `useConfirm`, `useTheme` 사용부.

### 함께 정리할 것

- 탭 정의 `TABS`의 이모지 아이콘(`⚙️ ⬇️ 🔑 🔔 🎨 💻 ℹ️`)을 **lucide-react 아이콘으로 교체**.
  나머지 UI는 전부 lucide를 쓰는데 여기만 이모지라 톤이 어긋난다.
- 파일 상단의 로컬 `ToggleSwitch`, `Select`를 제거하고 프리미티브의
  `Switch`, `Select`로 교체.
- 하드코딩된 `purple-*`, `green-*` 계열 색을 토큰/강조색으로 교체.
- 탭 목록 UI는 모바일에서 가로 스크롤되게 (현재 좁은 화면에서 눌림).

목표: `Settings.tsx`는 **200줄 이하**의 상태 관리 + 탭 라우팅 껍데기.

---

## 작업 B — `frontend/src/pages/Dashboard.tsx` 분해 (801줄)

채널 카드/리스트, 채널 추가 폼, 필터, SSE 연결이 한 파일에 있다.
`frontend/src/components/dashboard/` 아래로 분리:

- `ChannelCard.tsx` — 그리드 뷰 카드 1개
- `ChannelRow.tsx` — 리스트 뷰 행 1개
- `AddChannelForm.tsx` — 플랫폼 선택 + 채널 ID 입력
- `DashboardFilters.tsx` — 상태 필터(all/recording/live/offline) + 태그 필터 + 그리드/리스트 전환
- `useChannelStream.ts` (`frontend/src/hooks/`) — SSE 구독 + 폴백 fetch 로직

### 반드시 보존해야 하는 동작

1. **SSE 재연결** — `EventSource` 실패 시 5초 후 재연결, `status_update` 이벤트로 채널 상태 갱신.
2. **SSE 실패 시 폴백** — `fetchChannels()`로 `/platforms/channels` 직접 조회.
3. **플랫폼별 활성화 판정** — `isPlatformEnabled()` (twitcasting/x_spaces는 인증 설정 필요).
4. `localStorage`의 `dashboardViewMode` 유지.
5. 채널 추가/삭제/자동녹화 토글/수동 녹화 시작·중지 API 호출.

### 함께 개선할 것

- 로딩 중에 `.skeleton` 클래스로 스켈레톤 표시 (현재 스피너만).
- 채널이 없을 때 `EmptyState` 프리미티브 사용.
- `PLATFORM_BADGE_STYLES`의 하드코딩 색을 플랫폼 토큰
  (`text-chzzk` 등)으로 교체.
- 녹화 중 카드에 `.animate-pulse-border` 적용 (이미 CSS에 정의됨).

목표: `Dashboard.tsx`는 **250줄 이하**.

---

## 제약 / 주의사항

1. **API 계약을 바꾸지 말 것.** 백엔드 엔드포인트, 요청/응답 필드명 전부 그대로.
   프론트만 건드린다. (`frontend/src/api/client.ts`의 타입 추가는 허용,
   기존 필드 변경은 금지.)

2. **주석은 한국어로**, 기존 코드 스타일을 따른다. 무엇을 하는지가 아니라
   **왜 그런지**를 적는다. 예:
   ```tsx
   // SSE가 끊겨도 목록이 비지 않도록 최초 1회는 직접 조회한다.
   ```

3. **줄바꿈은 CRLF.** 저장소 대부분이 CRLF다. 파일을 LF로 바꾸면 diff가
   전체 파일로 부풀어 리뷰가 불가능해진다.
   (예외: `frontend/src/pages/Dashboard.tsx`, `youtube.py` 등 일부는 LF —
   **건드리는 파일의 기존 줄바꿈을 그대로 유지**할 것.)

4. **검증은 반드시 실행하고 결과를 보고할 것:**
   ```bash
   cd frontend && npx tsc --noEmit -p tsconfig.json
   cd frontend && npm run build
   cd backend && .venv\Scripts\python.exe -m pytest -q
   ```
   - 백엔드 테스트는 166 passed, 29 skipped 가 기준선이다. 줄어들면 안 된다.
   - `npm run build` 결과물은 `backend/app/static/`에 들어간다 (gitignore됨).

5. **커밋은 작업 A / 작업 B를 나눠서** 각각 하나씩.
   커밋 메시지는 한국어 본문 + 영어 제목, 마지막 줄에:
   ```
   Co-Authored-By: Codex <noreply@openai.com>
   ```

6. 실행해서 눈으로 확인하려면:
   ```bash
   backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
   ```
   → `http://localhost:8000`

---

## 알아두면 좋은 함정

- `frontend/tsconfig.tsbuildinfo`는 gitignore 대상이다. 커밋하지 말 것.
- 백엔드 테스트는 `conftest.py`가 임시 SQLite와 임시 `.env`를 주입한다.
  이 격리를 우회하는 테스트를 쓰면 개발자의 실제 `.env`가 덮어써진다.
- `Settings.tsx`의 `handleTabChange`는 `async`이고 내부에서 `confirm()`을
  await 한다. 분해할 때 이 비동기 흐름을 깨뜨리지 말 것.
- Tailwind v4는 `tailwind.config.js`가 없다. 토큰은 전부 `index.css`의
  `@theme` 블록에 있다.
- 빌드 시 "chunks larger than 500 kB" 경고가 뜨는데 기존부터 있던 것이다.
  이번 작업에서 코드 스플리팅까지 하지는 말 것 (범위 밖).
