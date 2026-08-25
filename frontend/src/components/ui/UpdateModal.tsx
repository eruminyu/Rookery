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
                return (
                    <div className="space-y-4">
                        <p className="text-sm text-ink-muted">
                            Windows 데스크톱 환경에서는 브라우저에서 최신 버전을 직접 다운로드하여 설치해야 합니다.
                        </p>
                        <div className="bg-surface-1 p-4 rounded-[var(--radius-control)] border border-line">
                            <ol className="list-decimal list-inside space-y-2 text-sm text-ink-muted">
                                <li>아래 버튼을 눌러 GitHub 릴리즈 페이지로 이동합니다.</li>
                                <li><span className="text-[var(--primary)] font-mono">Signal_Recorder.exe</span> 파일을 다운로드합니다.</li>
                                <li>현재 실행 중인 프로그램을 종료합니다.</li>
                                <li>다운로드한 파일로 기존 파일을 덮어쓰기 한 후 다시 실행합니다.</li>
                            </ol>
                        </div>
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
                const dockerCommand = `cd $(dirname $(find / -name "docker-compose.yml" -path "*/signal-recorder/*" 2>/dev/null | head -1)) && docker-compose pull && docker-compose up -d`;
                return (
                    <div className="space-y-4">
                        <p className="text-sm text-ink-muted">
                            Docker 컨테이너로 실행 중입니다. 호스트 머신의 터미널에서 다음 명령어를 실행하여 이미지를 최신으로 교체하세요.
                        </p>
                        <div className="relative group">
                            <div className="bg-surface-1 border border-line rounded-[var(--radius-control)] p-3 overflow-x-auto">
                                <code className="text-xs text-[var(--primary)] font-mono whitespace-nowrap">
                                    docker-compose pull && docker-compose up -d
                                </code>
                            </div>
                            <button
                                onClick={() => handleCopy("docker-compose pull && docker-compose up -d")}
                                className="absolute top-2 right-2 p-1.5 bg-surface-3 hover:bg-surface-4 text-ink-faint hover:text-ink rounded-md transition-colors"
                            >
                                {copied ? <CheckCircle2 className="w-4 h-4 text-ok" /> : <Copy className="w-4 h-4" />}
                            </button>
                        </div>
                        <p className="text-xs text-ink-faint">
                            만약 원라이너 자동 설치 스크립트를 사용하셨다면, 기존 설치 명령어를 그대로 다시 실행하셔도 업데이트됩니다.
                        </p>
                    </div>
                );
            case "linux-native":
            default:
                const linuxCommand = `curl -fsSL https://raw.githubusercontent.com/eruminyu/Signal-Recorder/main/scripts/install.sh | bash`;
                return (
                    <div className="space-y-4">
                        <p className="text-sm text-ink-muted">
                            Linux Native 환경입니다. 터미널에서 아래의 원라이너 설치 스크립트를 다시 실행하시면 자동으로 최신 버전으로 업데이트 후 재시작됩니다.
                        </p>
                        <div className="relative group">
                            <div className="bg-surface-1 border border-line rounded-[var(--radius-control)] p-3 overflow-x-auto">
                                <code className="text-xs text-[var(--primary)] font-mono whitespace-nowrap">
                                    {linuxCommand}
                                </code>
                            </div>
                            <button
                                onClick={() => handleCopy(linuxCommand)}
                                className="absolute top-2 right-2 p-1.5 bg-surface-3 hover:bg-surface-4 text-ink-faint hover:text-ink rounded-md transition-colors"
                            >
                                {copied ? <CheckCircle2 className="w-4 h-4 text-ok" /> : <Copy className="w-4 h-4" />}
                            </button>
                        </div>
                        <p className="text-xs text-ink-faint">
                            ※ 스크립트 실행 시 시스템 패키지 관리를 위해 sudo 비밀번호를 요구할 수 있습니다.
                        </p>
                    </div>
                );
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
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
