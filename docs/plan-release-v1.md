# v1.0.0 릴리즈 배포 계획

## 목적
Signal-Recorder v1.0.0을 GitHub에 첫 정식 릴리즈한다.
README 보완, 누락 파일 추가, Windows exe 빌드, GitHub Release 생성까지 처리.

## 변경 파일 목록

| 파일 | 작업 |
|------|------|
| `LICENSE` (신규) | MIT License 파일 생성 |
| `backend/app/core/config.py` | ffmpeg_path 기본값 `"ffmpeg"`으로 변경 |
| `docs/CHANGELOG.md` | username → eruminyu, 날짜 확정 |
| `README.md` | React 배지 수정, 스크린샷/시스템 요구사항/업데이트 방법/FAQ 섹션 추가 |
| `assets/screenshots/` (신규) | 대시보드, VOD 다운로드 스크린샷 |

## 구현 방법

### 1단계: 코드 수정
- LICENSE 파일 생성 (MIT)
- config.py의 로컬 하드코딩 경로 제거
- CHANGELOG의 placeholder 값 실제 값으로 교체
- README에 배포용 섹션 추가

### 2단계: 스크린샷
- 앱 실행 후 대시보드, VOD 다운로드 화면 캡처
- `assets/screenshots/` 폴더에 저장

### 3단계: 빌드
- 프론트엔드 빌드 (`npm ci && npm run build`)
- PyInstaller 빌드 (`pyinstaller signal_recorder.spec --clean`)
- exe 실행 테스트

### 4단계: 릴리즈
- git tag v1.0.0 생성
- GitHub Release 페이지에서 ZIP 파일 업로드
- Release 노트에 CHANGELOG 내용 + Linux 설치 명령어 기재

## 예상 영향 범위
- config.py: ffmpeg 기본 경로 변경으로 기존 `.env` 설정이 없는 사용자는 시스템 PATH의 ffmpeg을 사용하게 됨
- README: 사용자 문서 개선 (기능 변경 없음)
