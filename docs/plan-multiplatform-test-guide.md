# TwitCasting / Twitter Spaces 라이브 감지 & 자동녹화 테스트 가이드

> 작성일: 2026-03-23
> 대상: 멀티플랫폼 녹화 기능이 처음인 사용자

---

## 개요

Signal Recorder는 치지직 외에 **TwitCasting**과 **Twitter Spaces** 라이브를 자동 감지하고 녹화할 수 있다.

| 플랫폼 | 감지 방법 | 스트림 추출 | 출력 형식 |
|--------|----------|------------|----------|
| TwitCasting | TwitCasting API v2 | Streamlink | ts / mp4 |
| Twitter Spaces | Twitter API v2 | yt-dlp | m4a (오디오) |

---

## 사전 준비

### 공통

- 서버가 정상 실행 중이어야 함 (`sudo systemctl status signal-recorder` 또는 `start.sh`)
- WebUI 접속 가능 상태: `http://localhost:8000` (또는 서버 IP:8000)

### TwitCasting 전제조건

**Client ID / Client Secret 발급:**

1. [https://twitcasting.tv/developer.php](https://twitcasting.tv/developer.php) 접속
2. TwitCasting 계정으로 로그인
3. "アプリ登録" (앱 등록) 클릭
4. 앱 이름, 설명, 리다이렉트 URI 입력 (리다이렉트 URI는 임의값 가능: `http://localhost`)
5. 등록 완료 후 **ClientID**와 **ClientSecret** 메모

> 무료 개발자 계정으로도 라이브 감지 API 사용 가능

### Twitter Spaces 전제조건

> **중요**: Twitter Spaces 감지는 **비공식 GraphQL API**를 사용하므로 **쿠키 파일이 필수**다.
> 공식 Bearer Token은 사용하지 않는다.

**쿠키 파일 추출 방법:**

브라우저에서 twitter.com(또는 x.com)에 로그인한 상태로 Netscape 형식 쿠키를 추출한다.

추천 브라우저 확장 프로그램:
- Chrome: **EditThisCookie** 또는 **Get cookies.txt LOCALLY**
- Firefox: **cookies.txt** 확장

추출 시 `auth_token`과 `ct0` 쿠키가 반드시 포함되어야 한다.

추출 후 저장 경로 예시:
```
/home/user/signal-recorder/cookies/twitter_cookies.txt
```

**채널 ID (`@username` 핸들):**

> Twitter Spaces는 채널 추가 시 숫자 ID가 아닌 **`@` 없는 username 핸들**을 사용한다.
> 예: `https://twitter.com/KalserianT` → 채널 ID: `KalserianT`

**yt-dlp 설치 확인 (서버에서):**

```bash
# yt-dlp가 설치되어 있는지 확인
yt-dlp --version

# 없으면 설치
pip install yt-dlp
# 또는
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp
chmod a+rx /usr/local/bin/yt-dlp
```

---

## 1단계: 인증 설정

1. WebUI에서 **Settings** 메뉴 이동
2. **TwitCasting** 섹션:
   - `Client ID` 입력
   - `Client Secret` 입력
   - **저장** 클릭 → "설정이 저장되었습니다" 토스트 확인
3. **Twitter Spaces** 섹션:
   - `쿠키 파일 경로` 입력 (Netscape 형식 .txt 파일의 서버 절대 경로)
   - 예: `/home/user/signal-recorder/cookies/twitter_cookies.txt`
   - **저장** 클릭

---

## 2단계: 채널 추가

1. WebUI에서 **Live Dashboard** 이동
2. "채널 추가" 버튼 클릭
3. **플랫폼 선택** 드롭다운:
   - 인증이 설정되지 않은 플랫폼은 🔒 아이콘과 함께 비활성화됨
4. 채널 ID 입력:
   - TwitCasting: URL의 사용자명 (`twitcasting.tv/someuser` → `someuser`)
   - Twitter Spaces: `@` 없는 username 핸들 (`https://twitter.com/KalserianT` → `KalserianT`)
5. 자동 녹화 토글 켜기
6. **추가** 클릭

---

## 3단계: 테스트 확인 포인트

### TwitCasting 테스트

**라이브 감지 확인:**

```bash
# 서버에서
tail -f ~/signal-recorder/logs/service.log | grep -i twitcast
```

라이브 방송 시작 시 아래 로그가 출력되어야 함:
```
[twitcasting:someuser] 방송 시작 감지: 제목명
[twitcasting:someuser] 녹화 시작 → /path/to/recordings/someuser_날짜.ts
```

**녹화 파일 확인:**
```bash
ls -lh ~/signal-recorder/recordings/
# → [TwitCasting채널명] 제목_YYYYMMDD_HHMMSS.ts 형식의 파일 생성 확인
```

**WebUI에서 확인:**
- Dashboard 채널 카드에 🔴 LIVE 배지 표시
- 녹화 통계 (파일 크기, 속도) 실시간 업데이트

### Twitter Spaces 테스트

**동작 흐름:**

```
감시 루프 → GraphQL UserByScreenName (username → user_id)
         → GraphQL UserTweets (활성 Space 탐색)
         → live_video_stream/status/{media_key} (m3u8 URL 캡처)
         → Space 종료 후 캡처된 m3u8 URL로 yt-dlp 다운로드
```

**라이브 감지 확인:**

```bash
tail -f ~/signal-recorder/logs/service.log | grep -i twitter
```

Space 시작 시 아래 로그가 순서대로 출력되어야 함:
```
[TwitterSpaces:KalserianT] 라이브 Space 감지: 1abcXXXXXXX — Space 제목 (m3u8 캡처 완료)
[twitter_spaces:KalserianT] 🔴 방송 시작 감지!
```

m3u8 캡처 성공 시 Discord에도 알림이 발송된다 (봇 설정 시).

**Space 종료 후 다운로드:**

Space가 종료되면 캡처된 m3u8 URL로 자동 다운로드가 시작된다.
또는 Discord에서 수동으로 다운로드:
```
/download-space url:<캡처된_m3u8_url>
```

**녹화 파일 확인:**
```bash
ls -lh ~/signal-recorder/recordings/
# → [KalserianT] Space제목_YYYYMMDD_HHMMSS.m4a 형식
```

> **주의**: Twitter Spaces는 오디오 전용 녹화 (m4a 포맷)

---

## 트러블슈팅

### TwitCasting 인증 실패

**증상**: 채널 카드가 항상 오프라인으로 표시
**확인**:
```bash
grep "TwitCasting" ~/signal-recorder/logs/service.log | tail -20
```
- `API 응답 401` → Client ID/Secret 오류. Settings에서 재입력
- `API 요청 실패` → 네트워크 문제 또는 TwitCasting API 서버 다운

### Twitter Spaces 쿠키 인증 오류

**증상**: 채널 추가 후 감지 안 됨, 항상 오프라인으로 표시
**확인**:
```bash
grep "twitter_spaces\|TwitterSpaces" ~/signal-recorder/logs/service.log | tail -20
```
- `쿠키 파일이 설정되지 않았거나 없습니다` → Settings에서 쿠키 파일 경로 확인
- `auth_token/ct0를 찾을 수 없습니다` → 쿠키 파일에 `auth_token`, `ct0` 항목 없음. 브라우저에서 재추출
- `쿠키 인증 만료 (401)` → twitter.com에 재로그인 후 쿠키 재추출
- `UserByScreenName 조회 실패` → username 핸들 확인 (숫자 ID가 아닌 문자 핸들이어야 함)

**GraphQL QUERY_ID 만료:**

Twitter 배포 시 QUERY_ID가 변경될 수 있다. 증상: `400 Bad Request` 로그.
최신 QUERY_ID는 twspace-dl 또는 yt-dlp 소스에서 확인 가능.

### yt-dlp를 찾을 수 없음

**증상**: `service-error.log`에 `yt-dlp not found` 에러
**해결**:
```bash
which yt-dlp        # 경로 확인
pip install yt-dlp  # 가상환경 안에 설치
# 또는 venv 환경에서:
~/signal-recorder/.venv/bin/pip install yt-dlp
```

### 감시 루프 확인

모든 플랫폼이 감지가 안 된다면 감시 루프 상태를 확인:
```bash
grep "감시 오류\|감시 시작\|방송 시작" ~/signal-recorder/logs/service.log | tail -30
```

### 로그 실시간 모니터링

```bash
# 전체 로그
tail -f ~/signal-recorder/logs/service.log

# 에러만
tail -f ~/signal-recorder/logs/service-error.log

# 특정 채널
tail -f ~/signal-recorder/logs/service.log | grep "채널ID"
```

---

## 체크리스트

### TwitCasting

- [ ] twitcasting.tv/developer.php에서 앱 등록 완료
- [ ] Settings > TwitCasting에 Client ID/Secret 저장
- [ ] Dashboard에서 TwitCasting 채널 추가 (플랫폼 드롭다운에서 TwitCasting 선택)
- [ ] 라이브 중인 채널로 감지 로그 확인
- [ ] 녹화 파일 생성 확인

### Twitter Spaces

- [ ] twitter.com 로그인 상태에서 Netscape 형식 쿠키 파일 추출 (auth_token, ct0 포함 확인)
- [ ] `yt-dlp --version` 으로 설치 확인
- [ ] Settings > Twitter Spaces에 쿠키 파일 경로 저장
- [ ] username 핸들 확인 (`@` 제외한 문자 핸들, 숫자 ID 아님)
- [ ] Dashboard에서 Twitter Spaces 채널 추가
- [ ] 라이브 Space 감지 + m3u8 캡처 로그 확인
- [ ] Space 종료 후 m4a 녹화 파일 생성 확인
