import type { VodTask } from "../api/client";

export interface VodErrorDiagnosis {
    /** 오류 유형 배지 문구 */
    category: string;
    /** 한 줄 핵심 원인 제목 */
    headline: string;
    /** 사용자가 로그 없이 이해할 수 있는 상세 원인 설명 */
    summary: string;
    /** 해결을 위한 권장 조치 목록 */
    suggestions: string[];
    /** 인증 설정(/settings) 바로가기 버튼 노출 여부 */
    needsAuthCheck: boolean;
    /** 재시도 권장 여부 */
    canRetry: boolean;
    /** 불필요한 접두어를 정리한 원본 오류 메시지 */
    rawMessage: string;
}

/**
 * yt-dlp 및 백엔드 VOD 엔진의 오류 문자열을 분석하여
 * 팝업 모달에 표시할 한국어 원인 진단 정보를 생성한다.
 */
export function diagnoseVodError(
    task: Pick<VodTask, "url" | "title" | "quality" | "error_message">,
): VodErrorDiagnosis {
    const raw = (task.error_message || "알 수 없는 오류가 발생했습니다.").trim();
    const stripped = raw
        .replace(/^재시도\s*\d+회\s*실패:\s*/i, "")
        .replace(/^재시도\s*중\.\.\.\s*\(\d+\/\d+\):\s*/i, "")
        .replace(/^ERROR:\s*/i, "")
        .trim();
    const lower = stripped.toLowerCase();

    // 1. 성인 인증 / 로그인 / 쿠키 만료 / 비밀번호 보호
    if (
        stripped.includes("성인 인증") ||
        stripped.includes("로그인") ||
        stripped.includes("비밀번호") ||
        lower.includes("adult video") ||
        lower.includes("age-restricted") ||
        lower.includes("sign in to confirm your age") ||
        lower.includes("login required") ||
        lower.includes("protected by a password") ||
        lower.includes("http error 401")
    ) {
        return {
            category: "인증 / 권한 필요",
            headline: "성인 인증 또는 로그인 권한이 필요한 영상입니다",
            summary:
                stripped.includes("성인 인증") || stripped.includes("로그인") || stripped.includes("비밀번호")
                    ? stripped
                    : "비로그인 상태에서는 접근할 수 없거나, 현재 등록된 플랫폼 인증 쿠키가 만료되어 스트림 주소를 받지 못했습니다.",
            suggestions: [
                "[설정 → 인증] 탭에서 치지직 쿠키(NID_AUT, NID_SES) 또는 해당 플랫폼 쿠키가 올바르게 등록되어 있는지 확인하세요.",
                "성인(연령 제한) 영상인 경우 네이버 계정에서 본인·성인 인증이 완료된 상태여야 합니다.",
                "쿠키를 갱신한 뒤 '다시 다운로드'를 눌러 재시도해 보세요.",
            ],
            needsAuthCheck: true,
            canRetry: true,
            rawMessage: raw,
        };
    }

    // 2. 삭제 / 비공개 / 블라인드 / 구독자 전용
    if (
        stripped.includes("삭제되었거나") ||
        stripped.includes("존재하지 않는") ||
        stripped.includes("비공개") ||
        stripped.includes("블라인드") ||
        stripped.includes("구독자 전용") ||
        lower.includes("http error 404") ||
        lower.includes("http error 403") ||
        lower.includes("private video") ||
        lower.includes("video unavailable") ||
        lower.includes("members-only") ||
        lower.includes("subscribers only")
    ) {
        return {
            category: "비공개 / 접근 불가",
            headline: "삭제되었거나 접근이 제한된 영상입니다",
            summary:
                stripped.includes("치지지") || stripped.includes("치지직") || stripped.includes("삭제") || stripped.includes("비공개")
                    ? stripped
                    : "원본 영상이 삭제·비공개 처리되었거나 구독자(멤버십) 전용으로 제한되어 다운로드할 수 없습니다.",
            suggestions: [
                "브라우저에서 해당 영상 URL이 정상적으로 열리는지 먼저 확인해 보세요.",
                "구독자 전용 영상이라면 구독 권한이 있는 계정의 쿠키가 등록되어 있어야 합니다.",
            ],
            needsAuthCheck: lower.includes("403") || stripped.includes("구독자"),
            canRetry: false,
            rawMessage: raw,
        };
    }

    // 3. HLS / DASH 매니페스트 · 세그먼트 초기화 · 포맷 선택 오류
    if (
        lower.includes("initialization fragment") ||
        lower.includes("requested format is not available") ||
        lower.includes("m3u8") ||
        lower.includes("manifest") ||
        stripped.includes("스트림을 준비 중") ||
        stripped.includes("재생 URL을 추출할 수 없습니다")
    ) {
        return {
            category: "스트림 / 포맷 오류",
            headline: "스트림 매니페스트 또는 화질 포맷을 처리하지 못했습니다",
            summary:
                stripped.includes("준비 중")
                    ? stripped
                    : "방송 종료 직후 다시보기 인코딩이 아직 끝나지 않았거나, 요청한 화질 포맷을 스트림에서 찾을 수 없습니다.",
            suggestions: [
                "방금 종료된 생방송의 다시보기라면 잠시 후 인코딩이 완료된 뒤 다시 시도해 보세요.",
                "특정 화질(1080p 등) 지정 시 실패했다면 화질을 '최고 화질 (Best)'로 바꾸어 다시 시도해 보세요.",
            ],
            needsAuthCheck: false,
            canRetry: true,
            rawMessage: raw,
        };
    }

    // 4. 네트워크 타임아웃 / CDN 연결 끊김 / 5xx 서버 오류
    if (
        lower.includes("timed out") ||
        lower.includes("timeout") ||
        lower.includes("connection reset") ||
        lower.includes("http error 5") ||
        lower.includes("unable to download webpage") ||
        lower.includes("incompleteread") ||
        lower.includes("network")
    ) {
        return {
            category: "네트워크 / 서버 지연",
            headline: "스트리밍 서버 응답 지연 또는 네트워크 연결 끊김",
            summary:
                "다운로드 도중 스트리밍 서버(CDN) 응답이 시간 초과되었거나 일시적인 네트워크 순단으로 자동 재시도 횟수를 모두 소진했습니다.",
            suggestions: [
                "일시적인 서버 지연일 가능성이 높으니 잠시 후 '다시 다운로드'를 눌러 재시도해 보세요.",
                "동시 다운로드 개수가 많다면 [설정 → 다운로드]에서 동시 다운로드 개수를 줄여보세요.",
            ],
            needsAuthCheck: false,
            canRetry: true,
            rawMessage: raw,
        };
    }

    // 5. FFmpeg / 디스크 용량 / 파일 쓰기 권한 오류
    if (
        lower.includes("ffmpeg") ||
        lower.includes("ffprobe") ||
        lower.includes("no space left") ||
        lower.includes("permission denied") ||
        stripped.includes("파일이 없거나 비어 있습니다")
    ) {
        return {
            category: "FFmpeg / 저장소 오류",
            headline: "영상 병합(FFmpeg) 또는 파일 저장 중 오류가 발생했습니다",
            summary:
                "다운로드한 세그먼트를 하나로 합치는 FFmpeg 실행 과정이나 저장 폴더 쓰기 단계에서 실패했습니다.",
            suggestions: [
                "저장 경로의 디스크 여유 공간과 폴더 쓰기 권한이 충분한지 확인해 주세요.",
                "[설정 → 시스템]에서 FFmpeg 상태가 정상인지 확인해 주세요.",
            ],
            needsAuthCheck: false,
            canRetry: true,
            rawMessage: raw,
        };
    }

    // 6. 기본 폴백
    return {
        category: "다운로드 오류",
        headline: "영상 다운로드 중 오류가 발생했습니다",
        summary: stripped || "예기치 않은 오류로 다운로드가 중단되었습니다.",
        suggestions: [
            "입력한 영상 주소(URL)가 올바른지 확인하고 '다시 다운로드'를 눌러 재시도해 보세요.",
            "문제가 반복되면 아래 원본 오류 메시지를 복사해 원인을 확인할 수 있습니다.",
        ],
        needsAuthCheck: false,
        canRetry: true,
        rawMessage: raw,
    };
}
