import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle, Check, Copy, ExternalLink, KeyRound, RotateCw, X } from "lucide-react";
import type { VodTask } from "../../api/client";
import { diagnoseVodError } from "../../utils/vodError";
import { Badge, Button } from "./primitives";
import { useToast } from "./Toast";

interface VodErrorModalProps {
    task: VodTask;
    onClose: () => void;
    onRetry: (taskId: string) => Promise<void>;
}

/**
 * VOD 다운로드 실패 원인을 서버 로그 없이 화면에서 바로 확인할 수 있는 진단 팝업 모달.
 */
export function VodErrorModal({ task, onClose, onRetry }: VodErrorModalProps) {
    const navigate = useNavigate();
    const toast = useToast();
    const [copied, setCopied] = useState(false);
    const [retrying, setRetrying] = useState(false);

    const diagnosis = diagnoseVodError(task);

    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") onClose();
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [onClose]);

    const handleCopy = async () => {
        const text = [
            `[제목] ${task.title}`,
            `[URL] ${task.url}`,
            `[화질] ${task.quality}`,
            `[분류] ${diagnosis.category}`,
            `[원인] ${diagnosis.summary}`,
            `[상세 오류] ${diagnosis.rawMessage}`,
        ].join("\n");
        try {
            await navigator.clipboard.writeText(text);
            setCopied(true);
            toast.success("오류 상세 내용이 클립보드에 복사되었습니다.");
            setTimeout(() => setCopied(false), 2000);
        } catch {
            toast.error("클립보드 복사에 실패했습니다.");
        }
    };

    const handleRetryClick = async () => {
        setRetrying(true);
        try {
            await onRetry(task.task_id);
            toast.success("다운로드를 다시 시작했습니다.");
            onClose();
        } catch {
            toast.error("재다운로드 요청에 실패했습니다.");
        } finally {
            setRetrying(false);
        }
    };

    const handleOpenAuthSettings = () => {
        onClose();
        navigate("/settings");
    };

    return (
        <div
            className="fixed inset-0 z-[9998] flex items-center justify-center animate-backdrop p-4"
            onClick={onClose}
            role="dialog"
            aria-modal="true"
            aria-labelledby="vod-error-modal-title"
        >
            {/* Backdrop */}
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

            {/* Modal */}
            <div
                className="relative bg-surface-2/95 backdrop-blur-xl border border-line-strong rounded-[calc(var(--radius-card)+4px)] shadow-2xl p-6 w-full max-w-lg animate-modal-in surface-raise space-y-5 max-h-[90vh] overflow-y-auto"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3.5 min-w-0">
                        <div className="shrink-0 w-10 h-10 rounded-[var(--radius-control)] bg-danger/10 border border-danger/25 flex items-center justify-center">
                            <AlertCircle className="w-5 h-5 text-danger" />
                        </div>
                        <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                                <h3 id="vod-error-modal-title" className="text-ink font-bold text-base">
                                    VOD 다운로드 오류 원인
                                </h3>
                                <Badge tone="danger">{diagnosis.category}</Badge>
                            </div>
                            <p className="text-ink-muted text-xs mt-1">{diagnosis.headline}</p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="icon-button shrink-0 text-ink-faint hover:text-ink"
                        aria-label="닫기"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>

                {/* 대상 영상 정보 */}
                <div className="p-3.5 rounded-[var(--radius-control)] bg-surface-1 border border-line space-y-1.5 text-xs">
                    <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-ink truncate" title={task.title}>
                            {task.title !== "Unknown" ? task.title : "제목 미확인 영상"}
                        </span>
                        <span className="font-mono text-[11px] text-ink-faint shrink-0">
                            화질: {task.quality}
                        </span>
                    </div>
                    {task.url && (
                        <div className="flex items-center gap-1.5 text-ink-faint font-mono text-[11px] truncate">
                            <span className="truncate">{task.url}</span>
                            <a
                                href={task.url}
                                target="_blank"
                                rel="noreferrer"
                                className="shrink-0 hover:text-ink transition-colors"
                                title="원본 링크 열기"
                            >
                                <ExternalLink className="w-3.5 h-3.5" />
                            </a>
                        </div>
                    )}
                </div>

                {/* 핵심 원인 설명 */}
                <div className="p-4 rounded-[var(--radius-control)] bg-danger/5 border border-danger/20 space-y-2">
                    <p className="text-xs font-semibold text-danger">원인 분석</p>
                    <p className="text-sm text-ink leading-relaxed whitespace-pre-line">
                        {diagnosis.summary}
                    </p>
                </div>

                {/* 권장 해결 방법 */}
                <div className="space-y-2">
                    <p className="text-xs font-semibold text-ink-muted">해결 방법 안내</p>
                    <ul className="space-y-1.5 text-xs text-ink-muted list-disc pl-4 leading-relaxed">
                        {diagnosis.suggestions.map((item, idx) => (
                            <li key={idx}>{item}</li>
                        ))}
                    </ul>
                </div>

                {/* 원본 상세 오류 메시지 (로그 확인 불필요) */}
                <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                        <span className="text-[11px] font-semibold text-ink-faint">
                            원본 상세 오류 메시지
                        </span>
                        <button
                            type="button"
                            onClick={handleCopy}
                            className="inline-flex items-center gap-1 text-[11px] text-ink-muted hover:text-ink transition-colors"
                        >
                            {copied ? (
                                <>
                                    <Check className="w-3.5 h-3.5 text-ok" />
                                    <span className="text-ok">복사됨</span>
                                </>
                            ) : (
                                <>
                                    <Copy className="w-3.5 h-3.5" />
                                    <span>오류 내용 복사</span>
                                </>
                            )}
                        </button>
                    </div>
                    <pre className="p-3 rounded-[var(--radius-control)] bg-surface-1 border border-line text-[11px] font-mono text-ink-muted whitespace-pre-wrap break-all max-h-32 overflow-y-auto">
                        {diagnosis.rawMessage}
                    </pre>
                </div>

                {/* 하단 액션 버튼 */}
                <div className="flex flex-wrap items-center justify-end gap-2.5 pt-1">
                    {diagnosis.needsAuthCheck && (
                        <Button icon={KeyRound} onClick={handleOpenAuthSettings}>
                            인증 설정 열기
                        </Button>
                    )}
                    <Button
                        icon={RotateCw}
                        variant="primary"
                        loading={retrying}
                        onClick={handleRetryClick}
                    >
                        다시 다운로드
                    </Button>
                    <Button onClick={onClose}>닫기</Button>
                </div>
            </div>
        </div>
    );
}
