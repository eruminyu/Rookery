import { useCallback, useEffect, useState } from "react";
import { useBlocker } from "react-router-dom";
import {
    Bell,
    Download,
    Info,
    KeyRound,
    MonitorCog,
    Palette,
    Settings as SettingsIcon,
    type LucideIcon,
} from "lucide-react";
import { api, type Settings as SettingsType } from "../api/client";
import { AppearanceTab } from "../components/settings/AppearanceTab";
import { AuthTab } from "../components/settings/AuthTab";
import { DownloadTab } from "../components/settings/DownloadTab";
import { GeneralTab } from "../components/settings/GeneralTab";
import { InfoTab } from "../components/settings/InfoTab";
import { NotificationsTab } from "../components/settings/NotificationsTab";
import { SystemTab } from "../components/settings/SystemTab";
import { useConfirm } from "../components/ui/ConfirmModal";
import { useToast } from "../components/ui/Toast";

type TabId = "general" | "download" | "auth" | "notifications" | "appearance" | "system" | "info";

const TABS: { id: TabId; label: string; icon: LucideIcon }[] = [
    { id: "general", label: "일반", icon: SettingsIcon },
    { id: "download", label: "다운로드", icon: Download },
    { id: "auth", label: "인증", icon: KeyRound },
    { id: "notifications", label: "알림", icon: Bell },
    { id: "appearance", label: "외관", icon: Palette },
    { id: "system", label: "시스템", icon: MonitorCog },
    { id: "info", label: "정보", icon: Info },
];

const EMPTY_DIRTY: Record<TabId, boolean> = {
    general: false,
    download: false,
    auth: false,
    notifications: false,
    appearance: false,
    system: false,
    info: false,
};

export default function Settings() {
    const [settings, setSettings] = useState<SettingsType | null>(null);
    const [isDocker, setIsDocker] = useState(false);
    const [activeTab, setActiveTab] = useState<TabId>("general");
    const [dirtyTabs, setDirtyTabs] = useState<Record<TabId, boolean>>(EMPTY_DIRTY);
    const [updateAvailable, setUpdateAvailable] = useState(false);
    const toast = useToast();
    const confirm = useConfirm();

    const loadSettings = useCallback(async () => {
        try {
            setSettings(await api.getSettings());
        } catch {
            toast.error("설정을 불러오는 데 실패했습니다.");
        }
    }, [toast]);

    useEffect(() => {
        loadSettings();
        // 시스템 탭을 열기 전에도 새 버전 표시를 놓치지 않도록 상태를 미리 읽는다.
        api.getUpdateStatus()
            .then((info) => setUpdateAvailable(info.has_update))
            .catch(() => {});
        fetch("/api/setup/status")
            .then((response) => response.json())
            .then((data) => setIsDocker(data.is_docker))
            .catch(() => {});
    }, [loadSettings]);

    const setTabDirty = useCallback((tab: TabId, dirty: boolean) => {
        setDirtyTabs((current) => current[tab] === dirty ? current : { ...current, [tab]: dirty });
    }, []);

    const hasDirtyTab = TABS.some((tab) => dirtyTabs[tab.id]);

    const handleTabChange = async (newTab: TabId) => {
        if (activeTab === newTab) return;
        if (dirtyTabs[activeTab]) {
            const ok = await confirm({
                title: "저장되지 않은 변경사항",
                message: "현재 탭에 저장하지 않은 설정이 있습니다. 이동하시겠습니까?\n이동하면 변경사항은 초기화됩니다.",
                confirmText: "이동",
                variant: "danger",
            });
            if (!ok) return;

            setTabDirty(activeTab, false);
            loadSettings();
        }
        setActiveTab(newTab);
    };

    const blocker = useBlocker(
        ({ currentLocation, nextLocation }) =>
            currentLocation.pathname !== nextLocation.pathname && hasDirtyTab,
    );

    useEffect(() => {
        if (blocker.state !== "blocked") return;
        confirm({
            title: "저장되지 않은 변경사항",
            message: "저장하지 않은 설정이 있습니다. 페이지를 이동하시겠습니까?\n이동하면 변경사항은 초기화됩니다.",
            confirmText: "이동",
            variant: "danger",
        }).then((ok) => ok ? blocker.proceed() : blocker.reset());
    }, [blocker.state]);

    useEffect(() => {
        const warnBeforeUnload = (event: BeforeUnloadEvent) => {
            if (!hasDirtyTab) return;
            event.preventDefault();
            event.returnValue = "";
        };
        window.addEventListener("beforeunload", warnBeforeUnload);
        return () => window.removeEventListener("beforeunload", warnBeforeUnload);
    }, [hasDirtyTab]);

    return (
        <div className="space-y-6">
            <header>
                <h2 className="text-2xl font-bold text-ink flex items-center gap-2">
                    <SettingsIcon className="w-6 h-6" style={{ color: "var(--primary)" }} />
                    Settings
                </h2>
                <p className="text-ink-faint">애플리케이션 설정을 관리합니다.</p>
            </header>

            <nav className="flex gap-1 border-b border-line overflow-x-auto" aria-label="설정 탭">
                {TABS.map((tab) => {
                    const Icon = tab.icon;
                    return (
                        <button
                            key={tab.id}
                            onClick={() => handleTabChange(tab.id)}
                            className={`flex shrink-0 items-center gap-1.5 px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-colors border-b-2 -mb-px relative ${activeTab === tab.id ? "border-[var(--primary)] text-ink" : "border-transparent text-ink-faint hover:text-ink-muted"}`}
                        >
                            <Icon className="w-4 h-4" />
                            {tab.label}
                            {dirtyTabs[tab.id] && <span className="w-2 h-2 rounded-full bg-warn absolute top-2 right-2 animate-pulse" />}
                            {tab.id === "system" && updateAvailable && <span className="w-2 h-2 rounded-full bg-ok absolute top-2 right-2 animate-pulse" />}
                        </button>
                    );
                })}
            </nav>

            {activeTab === "general" && <GeneralTab settings={settings} isDocker={isDocker} onSaved={loadSettings} onDirtyChange={(dirty) => setTabDirty("general", dirty)} />}
            {activeTab === "download" && <DownloadTab settings={settings} onSaved={loadSettings} onDirtyChange={(dirty) => setTabDirty("download", dirty)} />}
            {activeTab === "auth" && <AuthTab settings={settings} onSaved={loadSettings} onDirtyChange={(dirty) => setTabDirty("auth", dirty)} />}
            {activeTab === "notifications" && <NotificationsTab settings={settings} onSaved={loadSettings} onDirtyChange={(dirty) => setTabDirty("notifications", dirty)} />}
            {activeTab === "appearance" && <AppearanceTab settings={settings} onSaved={loadSettings} onDirtyChange={(dirty) => setTabDirty("appearance", dirty)} />}
            {activeTab === "system" && <SystemTab settings={settings} onSaved={loadSettings} onDirtyChange={(dirty) => setTabDirty("system", dirty)} onUpdateAvailabilityChange={setUpdateAvailable} />}
            {activeTab === "info" && <InfoTab settings={settings} onSaved={loadSettings} onDirtyChange={(dirty) => setTabDirty("info", dirty)} />}
        </div>
    );
}
