# 작업 체크리스트

## v2.0.6 대시보드 플랫폼 메뉴 수정·릴리즈 준비 (2026-09-05)

- [x] `PageHeader`의 `overflow-hidden`이 플랫폼 목록을 자르는 원인 확인
- [x] 장식 배경에만 잘림을 적용하고 헤더 액션 메뉴는 밖으로 표시
- [x] 모바일에서 플랫폼 메뉴를 왼쪽 기준으로 배치하고 최대 높이·세로 스크롤 적용
- [x] 프런트엔드 TypeScript 검사와 프로덕션 빌드 통과 (`npm run build`)
- [x] 격리된 Edge 브라우저 테스트 3개 통과: 1440×900, 390×844, 640×280
- [x] 네 플랫폼 항목의 클릭 가능 영역, YouTube 선택·입력 안내 변경·메뉴 닫힘, 낮은 창의 내부 스크롤 확인
- [x] 기존 헤더 잘림 속성을 복원하면 YouTube 항목이 가려지는 것을 테스트에서 재현
- [x] 백엔드·npm 패키지·lockfile·CHANGELOG 버전을 `2.0.6`으로 통일
- [x] 백엔드 전체 테스트 통과 (`242 passed, 29 skipped`)
- [x] PyInstaller Windows one-file 실행 파일 빌드 통과
- [x] 깨끗한 폴더에서 실행 파일의 헬스 API·내장 SPA·최초 설정 상태 확인
- [x] 실행 파일의 `FileVersion`·`ProductVersion`이 `2.0.6`인지 확인

브라우저 검증은 테스트 전용 API 모의 응답으로 수행했다. 실제 채널 추가 요청이나 녹화는 실행하지 않았다.
로컬 검증 스크립트: `build/platform-menu-regression.cjs` (Git 제외, Playwright 런타임 필요).

빌드 산출물: `dist/Rookery.exe` (38,076,862 bytes)

SHA-256: `C2DCF670B93CB31FE56560F941E9690685B18D308EB8639B291E758C6AF13A4E`

## v2.0.5 릴리즈 준비 (2026-08-29)

- [x] `main`과 `origin/main`이 같은 커밋인지 확인
- [x] `v2.0.4` 이후 릴리즈 대상이 정확히 6개 커밋인지 확인
- [x] 백엔드·npm 패키지·lockfile 버전을 `2.0.5`로 통일
- [x] CHANGELOG 릴리즈 항목과 비교 링크 갱신
- [x] 릴리즈 메타데이터 일관성 회귀 테스트 추가
- [x] 백엔드 전체 테스트 통과 (`242 passed, 29 skipped`)
- [x] FastAPI `0.135.2`와 CI의 `0.141.1` 환경에서 동일한 결과 확인
- [x] 프런트엔드 TypeScript 검사와 프로덕션 빌드 통과
- [x] PyInstaller Windows one-file 실행 파일 빌드 통과
- [x] 빈 폴더에서 실행 파일의 헬스 API와 내장 프런트엔드 응답 확인
- [x] 실행 파일의 `FileVersion`·`ProductVersion`이 `2.0.5`인지 확인

빌드 산출물: `dist/Rookery.exe`

SHA-256: `1BF0E47C3AEF834B2E0CB5BE31006B8815B0BB0BA8A28C6338DA16EB56D1D868`
