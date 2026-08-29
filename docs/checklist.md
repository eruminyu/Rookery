# 작업 체크리스트

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
