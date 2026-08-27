import { useState } from "react";
import { X, ExternalLink, Copy, CheckCircle2, Terminal } from "lucide-react";
import { UpdateInfo } from "../../api/client";

interface UpdateModalProps {
    info: UpdateInfo;
    onClose: () => void;
}

export function UpdateModal({ info, onClose }: UpdateModalProps) {
    const [copied, setCopied] = useState(false);

    const handleCopy = (text: string) => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const renderContent = () => {
        switch (info.environment) {
            case "windows-exe":
                // 릴리즈 asset 이름에 버전이 들어간다: Rookery-v2.0.0-windows-x64.exe
                const assetName = `Rookery-v${info.latest_version}-windows-x64.exe`;
                return (
                    <div className="space-y-4">
                        <p className="text-sm text-ink-muted">
                            Windows 데스크톱 환경에서는 브라우저에서 최신 버전을 직접 다운로드하여 설치해야 합니다.
                        </p>
                        <div className="bg-surface-1 p-4 rounded-[var(--radius-control)] border border-line">
                            <ol className="list-decimal list-inside space-y-2 text-sm text-ink-muted">
                                <li>아래 버튼을 눌러 GitHub 릴리즈 페이지로 이동합니다.</li>
                                <li><span className="text-[var(--primary)] font-mono break-all">{assetName}</span> 파일을 다운로드합니다.</li>
                                <li>현재 실행 중인 프로그램을 종료합니다.</li>
                                <li>
                                    받은 파일을 <b className="text-ink-muted">기존 실행 파일과 같은 폴더</b>로 옮긴 뒤 실행합니다.
                                </li>
                                <li>정상 동작을 확인했으면 이전 버전 파일은 삭제해도 됩니다.</li>
                            </ol>
                        </div>
                        <p className="text-xs text-ink-faint flex items-start gap-1.5">
                            <span className="text-warn">⚠️</span>
                            <span>
                                설정(<span className="font-mono">.env</span>)과 데이터(<span className="font-mono">data/</span>)는
                                실행 파일 옆에 저장됩니다. 다른 폴더에서 실행하면 채널 목록이 비어 보이고 초기 설정 마법사가 다시 표시됩니다.
                            </span>
                        </p>
                        <a
                            href={info.download_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="w-full btn-primary py-2.5 rounded-[var(--radius-control)] font-bold transition-colors flex items-center justify-center gap-2"
                        >
                            <ExternalLink className="w-4 h-4" />
                            GitHub 릴리즈에서 다운로드
                        </a>
                    </div>
                );
            case "docker":
            case "linux-native":
            default:
                // 네이티브는 manage.sh가 설치한 rookery 명령으로 끝난다.
                // Docker는 manage.sh 대상이 아니므로 compose를 직접 쓴다.
                const isDocker = info.environment === "docker";
                const updateCommand = isDocker
                    ? "git pull && docker compose up --build -d"
                    : "rookery update";
                return (
                    <div className="space-y-4">
                        <p className="text-sm text-ink-muted">
                            {isDocker
                                ? "Docker로 실행 중입니다. 호스트 머신의 저장소 디렉토리에서 아래 명령을 실행하세요."
                                : "터미널에서 아래 명령을 실행하면 최신 버전으로 갱신한 뒤 자동으로 재시작됩니다."}
                        </p>
                        <div className="relative group">
                            <div className="bg-surface-1 border border-line rounded-[var(--radius-control)] p-3 overflow-x-auto">
                                <code className="text-xs text-[var(--primary)] font-mono whitespace-nowrap">
                                    {updateCommand}
                                </code>
                            </div>
                            <button
                                onClick={() => handleCopy(updateCommand)}
                                className="absolute top-2 right-2 p-1.5 bg-surface-3 hover:bg-surface-4 text-ink-faint hover:text-ink rounded-md transition-colors"
                            >
                                {copied ? <CheckCircle2 className="w-4 h-4 text-ok" /> : <Copy className="w-4 h-4" />}
                            </button>
                        </div>
                        <p className="text-xs text-ink-faint">
                            {isDocker
                                ? "config/ 와 recordings/ 는 호스트에 마운트되어 있어 재빌드해도 유지됩니다."
                                : "명령을 찾을 수 없다면 설치 원라이너를 그대로 다시 실행해도 업데이트됩니다. 시스템 패키지를 다룰 때 sudo 비밀번호를 물을 수 있습니다."}
                        </p>
                    </div>
                );
        }
    };

    return (
        <div className="fixed inset-0 z-[9998] flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
            <div className="relative bg-surface-2 border border-line-strong rounded-[calc(var(--radius-card)+4px)] w-full max-w-lg shadow-2xl surface-raise animate-modal-in">
                <div className="flex items-center justify-between p-5 border-b border-line">
                    <h3 className="text-lg font-bold text-ink flex items-center gap-2">
                        <Terminal className="w-5 h-5 text-[var(--primary)]" />
                        업데이트 안내
                    </h3>
                    <button
                        onClick={onClose}
                        className="text-ink-faint hover:text-ink transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>
                
                <div className="p-6">
                    {renderContent()}
                </div>
            </div>
        </div>
    );
}
