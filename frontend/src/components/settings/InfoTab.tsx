import { useEffect, type ReactNode } from "react";
import { Info } from "lucide-react";
import type { Settings as SettingsType } from "../../api/client";
import { Card, CardHeader } from "../ui/primitives";

interface Props {
    settings: SettingsType | null;
    /** 정보 탭은 읽기 전용이지만 탭 props 형태를 통일한다. */
    onSaved: () => void;
    /** 정보 탭에는 편집 폼이 없음을 상위에 알린다. */
    onDirtyChange?: (dirty: boolean) => void;
}

function InfoRow({ label, children, last = false }: { label: string; children: ReactNode; last?: boolean }) {
    return (
        <div className={`flex justify-between gap-4 py-2 ${last ? "" : "border-b border-line"}`}>
            <span className="text-ink-faint">{label}</span>
            {children}
        </div>
    );
}

export function InfoTab({ settings, onDirtyChange }: Props) {
    useEffect(() => onDirtyChange?.(false), [onDirtyChange]);

    return (
        <Card>
            <CardHeader icon={Info} title="시스템 정보" />
            <div className="space-y-1 text-sm">
                <InfoRow label="앱 이름"><span className="text-ink-muted">{settings?.app_name || "Loading..."}</span></InfoRow>
                <InfoRow label="FFmpeg 경로"><span className="text-ink-muted truncate max-w-[220px]" title={settings?.ffmpeg_path}>{settings?.ffmpeg_path || "Loading..."}</span></InfoRow>
                <InfoRow label="서버"><span className="text-ink-muted">{settings ? `${settings.host}:${settings.port}` : "Loading..."}</span></InfoRow>
                <InfoRow label="Discord Bot"><span className={settings?.discord_bot_configured ? "text-ok" : "text-ink-faint"}>{settings?.discord_bot_configured ? "연결됨" : "미설정"}</span></InfoRow>
                <InfoRow label="TwitCasting 설정"><span className={settings?.twitcasting_client_id ? "text-twitcasting" : "text-ink-faint"}>{settings?.twitcasting_client_id ? "설정됨" : "미설정"}</span></InfoRow>
                <InfoRow label="X Spaces 쿠키" last><span className={settings?.x_cookie_file ? "text-xspaces" : "text-ink-faint"}>{settings?.x_cookie_file ? "설정됨" : "미설정"}</span></InfoRow>
            </div>
        </Card>
    );
}
