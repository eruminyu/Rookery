import { useState, useEffect, useCallback, useRef } from "react";
import { useBlocker } from "react-router-dom";
import {
    Settings as SettingsIcon,
    Shield,
    Save,
    Key,
    Download,
    RefreshCcw,
    Film,
    Gauge,
    Timer,
    Loader2,
    MessageSquare,
    MessageCircle,
    FolderOpen,
    Folder,
    Palette,
    Type,
    ImageIcon,
    RotateCcw,
    ArrowLeft,
    ChevronRight,
    X,
    Info,
    AlertCircle,
    Upload,
    Trash2,
    CheckCircle2,
    Gift,
    Terminal,
} from "lucide-react";
import { api, Settings as SettingsType, BrowseDirsResponse, DirEntry, UpdateInfo } from "../api/client";
import { UpdateModal } from "../components/ui/UpdateModal";
import { useToast } from "../components/ui/Toast";
import { useConfirm } from "../components/ui/ConfirmModal";
import { getErrorMessage } from "../utils/error";
import { DirInput } from "../components/ui/DirInput";
import { useTheme, THEMES, ThemeId } from "../context/ThemeContext";

// ── ToggleSwitch ─────────────────────────────────────────

interface ToggleSwitchProps {
    checked: boolean;
    onChange: (v: boolean) => void;
    activeColor?: string;
    focusRingColor?: string;
}

function ToggleSwitch({
    checked,
    onChange,
    activeColor = "bg-green-600",
    focusRingColor = "focus:ring-green-500",
}: ToggleSwitchProps) {
    return (
        <button
            type="button"
            onClick={() => onChange(!checked)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors
                        focus:outline-none focus:ring-2 ${focusRingColor}
                        focus:ring-offset-2 focus:ring-offset-zinc-900
                        ${checked ? activeColor : "bg-zinc-700"}`}
        >
            <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white
                            transition-transform ${checked ? "translate-x-6" : "translate-x-1"}`}
            />
        </button>
    );
}

// ── Select ─────────────────────────────────────────────

function Select({
    value,
    onChange,
    options,
}: {
    value: string;
    onChange: (v: string) => void;
    options: { value: string; label: string }[];
}) {
    return (
        <select
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-green-500 appearance-none cursor-pointer"
        >
            {options.map((o) => (
                <option key={o.value} value={o.value}>
                    {o.label}
                </option>
            ))}
        </select>
    );
}

// ── 탭 정의 ──────────────────────────────────────────────

type TabId = "general" | "download" | "auth" | "notifications" | "appearance" | "info" | "system";

const TABS: { id: TabId; label: string; icon: string }[] = [
    { id: "general",       label: "일반",   icon: "⚙️" },
    { id: "download",      label: "다운로드", icon: "⬇️" },
    { id: "auth",          label: "인증",   icon: "🔑" },
    { id: "notifications", label: "알림",   icon: "🔔" },
    { id: "appearance",    label: "외관",   icon: "🎨" },
    { id: "system",        label: "시스템", icon: "💻" },
    { id: "info",          label: "정보",   icon: "ℹ️" },
];

// ── Settings 메인 컴포넌트 ────────────────────────────────

export default function Settings() {
    const [settings, setSettings] = useState<SettingsType | null>(null);
    const [isDocker, setIsDocker] = useState(false);
    const [activeTab, setActiveTab] = useState<TabId>("general");
    const toast = useToast();
    const confirm = useConfirm();

    // ── Auth state ──
    const [nidAut, setNidAut] = useState("");
    const [nidSes, setNidSes] = useState("");
    const [cookieStatus, setCookieStatus] = useState<"valid" | "invalid" | "checking" | "unknown">("unknown");
    const [nickname, setNickname] = useState<string | null>(null);

    const checkCookieStatus = async () => {
        setCookieStatus("checking");
        try {
            const res = await api.testCookies();
            if (res.valid) {
                setCookieStatus("valid");
                setNickname(res.user_status?.nickname || null);
            } else {
                setCookieStatus("invalid");
            }
        } catch {
            setCookieStatus("invalid");
        }
    };

    useEffect(() => {
        if (activeTab === "auth" && cookieStatus === "unknown") {
            checkCookieStatus();
        }
    }, [activeTab]);

    // ── TwitCasting auth state ──
    const [twitcastingClientId, setTwitcastingClientId] = useState("");
    const [twitcastingClientSecret, setTwitcastingClientSecret] = useState("");
    const [twitcastingSaving, setTwitcastingSaving] = useState(false);

    // ── X Spaces auth state ──
    const [xCookieFileSet, setXCookieFileSet] = useState(false);
    const [xCookieUploading, setXCookieUploading] = useState(false);
    const cookieFileInputRef = useRef<HTMLInputElement>(null);

    // ── Download state ──
    const [keepParts, setKeepParts] = useState(false);
    const [maxRetries, setMaxRetries] = useState(3);
    const [dlSaving, setDlSaving] = useState(false);

    // ── General state ──
    const [downloadDir, setDownloadDir] = useState("");
    const [monitorInterval, setMonitorInterval] = useState(30);
    const [liveFormat, setLiveFormat] = useState("ts");
    const [vodFormat, setVodFormat] = useState("mp4");
    const [recordingQuality, setRecordingQuality] = useState("best");
    const [splitDownloadDirs, setSplitDownloadDirs] = useState(false);
    const [vodChzzkDir, setVodChzzkDir] = useState("");
    const [vodExternalDir, setVodExternalDir] = useState("");
    const [genSaving, setGenSaving] = useState(false);

    // ── VOD settings state ──
    const [vodMaxConcurrent, setVodMaxConcurrent] = useState(3);
    const [vodDefaultQuality, setVodDefaultQuality] = useState("best");
    const [vodMaxSpeed, setVodMaxSpeed] = useState(0);
    const [vodSaving, setVodSaving] = useState(false);

    // ── Chat settings state ──
    const [chatArchiveEnabled, setChatArchiveEnabled] = useState(false);
    const [chatSaving, setChatSaving] = useState(false);

    // Discord Settings
    const [discordBotToken, setDiscordBotToken] = useState("");
    const [discordChannelId, setDiscordChannelId] = useState("");
    const [discordSaving, setDiscordSaving] = useState(false);

    // Appearance
    const { themeId, customColor, pageTitle, setTheme, setCustomColor, setPageTitle, setIconUrl, resetAll } = useTheme();
    const [titleInput, setTitleInput] = useState(pageTitle);
    const iconInputRef = useRef<HTMLInputElement>(null);
    const colorPickerRef = useRef<HTMLInputElement>(null);

    // System & Update
    const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
    const [checkingUpdate, setCheckingUpdate] = useState(false);
    const [showUpdateModal, setShowUpdateModal] = useState(false);

    const loadUpdateStatus = async () => {
        try {
            const res = await api.getUpdateStatus();
            setUpdateInfo(res);
        } catch (err) {
            console.error("업데이트 정보 로드 실패", err);
        }
    };

    useEffect(() => {
        loadUpdateStatus();
    }, []);

    const handleCheckUpdate = async () => {
        setCheckingUpdate(true);
        try {
            const res = await api.checkUpdateNow();
            setUpdateInfo(res);
            if (res.has_update) {
                toast.success("새로운 버전이 있습니다!");
            } else {
                toast.success("최신 버전을 사용 중입니다.");
            }
        } catch (err: unknown) {
            toast.error(getErrorMessage(err, "업데이트 확인에 실패했습니다."));
        } finally {
            setCheckingUpdate(false);
        }
    };

    const isTabDirty = (tabId: TabId) => {
        if (!settings) return false;
        switch (tabId) {
            case "general":
                return downloadDir !== settings.download_dir ||
                       monitorInterval !== settings.monitor_interval ||
                       liveFormat !== (settings.live_format || "ts") ||
                       recordingQuality !== (settings.recording_quality || "best") ||
                       splitDownloadDirs !== (settings.split_download_dirs ?? false) ||
                       vodChzzkDir !== (settings.vod_chzzk_dir ?? "") ||
                       vodExternalDir !== (settings.vod_external_dir ?? "");
            case "download":
                return keepParts !== settings.keep_download_parts ||
                       maxRetries !== settings.max_record_retries ||
                       vodMaxConcurrent !== settings.vod_max_concurrent ||
                       vodDefaultQuality !== settings.vod_default_quality ||
                       vodMaxSpeed !== settings.vod_max_speed ||
                       vodFormat !== (settings.vod_format || "mp4");
            case "auth":
                return (twitcastingClientId !== "" || twitcastingClientSecret !== "") ||
                       (nidAut !== "" || nidSes !== "");
            case "notifications":
                return chatArchiveEnabled !== settings.chat_archive_enabled ||
                       discordChannelId !== (settings.discord_notification_channel_id || "");
            case "appearance":
                return titleInput !== pageTitle;
            default:
                return false;
        }
    };

    const handleTabChange = async (newTab: TabId) => {
        if (activeTab === newTab) return;
        if (isTabDirty(activeTab)) {
            const ok = await confirm({
                title: "저장되지 않은 변경사항",
                message: "현재 탭에 저장하지 않은 설정이 있습니다. 이동하시겠습니까?\n이동하면 변경사항은 초기화됩니다.",
                confirmText: "이동",
                variant: "danger"
            });
            if (!ok) return;
            
            if (activeTab === "auth") {
                setTwitcastingClientId("");
                setTwitcastingClientSecret("");
                setNidAut("");
                setNidSes("");
            } else if (activeTab === "appearance") {
                setTitleInput(pageTitle);
            } else {
                loadSettings();
            }
        }
        setActiveTab(newTab);
    };

    // ── 페이지 이탈 경고 (Bug 2: 사이드바 이탈) ──
    const blocker = useBlocker(
        ({ currentLocation, nextLocation }) =>
            currentLocation.pathname !== nextLocation.pathname &&
            TABS.some((t) => isTabDirty(t.id))
    );

    useEffect(() => {
        if (blocker.state !== "blocked") return;
        confirm({
            title: "저장되지 않은 변경사항",
            message: "저장하지 않은 설정이 있습니다. 페이지를 이동하시겠습니까?\n이동하면 변경사항은 초기화됩니다.",
            confirmText: "이동",
            variant: "danger",
        }).then((ok) => {
            if (ok) blocker.proceed();
            else blocker.reset();
        });
    }, [blocker.state]);

    useEffect(() => {
        loadSettings();
        fetch("/api/setup/status")
            .then((r) => r.json())
            .then((data) => setIsDocker(data.is_docker))
            .catch(() => {});
    }, []);

    const loadSettings = async () => {
        try {
            const [data, platformStatus] = await Promise.all([
                api.getSettings(),
                api.getPlatformStatus(),
            ]);
            setXCookieFileSet(platformStatus.x_spaces.cookie_file_set);
            setSettings(data);
            setKeepParts(data.keep_download_parts);
            setMaxRetries(data.max_record_retries);
            setDownloadDir(data.download_dir);
            setMonitorInterval(data.monitor_interval);
            setLiveFormat(data.live_format || "ts");
            setVodFormat(data.vod_format || "mp4");
            setRecordingQuality(data.recording_quality || "best");
            setVodMaxConcurrent(data.vod_max_concurrent);
            setVodDefaultQuality(data.vod_default_quality);
            setVodMaxSpeed(data.vod_max_speed);
            setChatArchiveEnabled(data.chat_archive_enabled);
            setDiscordChannelId(data.discord_notification_channel_id || "");
            setSplitDownloadDirs(data.split_download_dirs ?? false);
            setVodChzzkDir(data.vod_chzzk_dir ?? "");
            setVodExternalDir(data.vod_external_dir ?? "");
        } catch {
            toast.error("설정을 불러오는 데 실패했습니다.");
        }
    };

    // ── Auth handlers ──
    const handleUpdateCookies = async () => {
        try {
            await api.updateCookies(nidAut, nidSes);
            toast.success("쿠키가 저장되었습니다!");
            loadSettings();
            setNidAut("");
            setNidSes("");
        } catch {
            toast.error("쿠키 저장에 실패했습니다.");
        }
    };

    const handleTestCookies = async () => {
        try {
            const res = await api.testCookies();
            if (res.valid) {
                setCookieStatus("valid");
                setNickname(res.user_status?.nickname || null);
                toast.success(`인증 성공! 닉네임: ${res.user_status?.nickname || "User"}`);
            } else {
                setCookieStatus("invalid");
                toast.error("쿠키가 유효하지 않습니다.");
            }
        } catch (e: unknown) {
            setCookieStatus("invalid");
            toast.error(getErrorMessage(e, "검증에 실패했습니다."));
        }
    };

    const handleSaveTwitcasting = async () => {
        if (!twitcastingClientId || !twitcastingClientSecret) {
            toast.error("Client ID와 Client Secret을 모두 입력하세요.");
            return;
        }
        setTwitcastingSaving(true);
        try {
            await api.updateTwitcastingSettings({
                client_id: twitcastingClientId,
                client_secret: twitcastingClientSecret,
            });
            toast.success("TwitCasting 인증 설정이 저장되었습니다.");
            setTwitcastingClientId("");
            setTwitcastingClientSecret("");
        } catch (e: unknown) {
            toast.error(getErrorMessage(e, "TwitCasting 설정 저장에 실패했습니다."));
        } finally {
            setTwitcastingSaving(false);
        }
    };

    const handleUploadXCookie = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;
        setXCookieUploading(true);
        try {
            await api.uploadXCookie(file);
            setXCookieFileSet(true);
            toast.success("쿠키 파일이 업로드되었습니다.");
        } catch (err: unknown) {
            toast.error(getErrorMessage(err, "쿠키 파일 업로드에 실패했습니다."));
        } finally {
            setXCookieUploading(false);
            if (cookieFileInputRef.current) cookieFileInputRef.current.value = "";
        }
    };

    const handleDeleteXCookie = async () => {
        const ok = await confirm({
            title: "쿠키 파일 삭제",
            message: "저장된 X 쿠키 파일을 삭제하시겠습니까?",
            confirmText: "삭제",
            variant: "danger",
        });
        if (!ok) return;
        try {
            await api.deleteXCookie();
            setXCookieFileSet(false);
            toast.success("쿠키 파일이 삭제되었습니다.");
        } catch (err: unknown) {
            toast.error(getErrorMessage(err, "쿠키 파일 삭제에 실패했습니다."));
        }
    };

    // ── Download settings save ──
    const handleSaveDownloadSettings = async () => {
        setDlSaving(true);
        try {
            await api.updateDownloadSettings(keepParts, maxRetries);
            toast.success("다운로드 설정이 저장되었습니다.");
            loadSettings();
        } catch {
            toast.error("다운로드 설정 저장에 실패했습니다.");
        } finally {
            setDlSaving(false);
        }
    };

    // ── General settings save ──
    const handleSaveGeneralSettings = async () => {
        setGenSaving(true);
        try {
            await api.updateGeneralSettings({
                download_dir: downloadDir,
                monitor_interval: monitorInterval,
                live_format: liveFormat,
                recording_quality: recordingQuality,
                split_download_dirs: splitDownloadDirs,
                vod_chzzk_dir: vodChzzkDir,
                vod_external_dir: vodExternalDir,
            });
            toast.success("일반 설정이 저장되었습니다.");
            loadSettings();
        } catch (e: unknown) {
            toast.error(getErrorMessage(e, "일반 설정 저장에 실패했습니다."));
        } finally {
            setGenSaving(false);
        }
    };

    // ── VOD settings save ──
    const handleSaveVodSettings = async () => {
        setVodSaving(true);
        try {
            await api.updateVodSettings({
                vod_max_concurrent: vodMaxConcurrent,
                vod_default_quality: vodDefaultQuality,
                vod_max_speed: vodMaxSpeed,
                vod_format: vodFormat,
            });
            toast.success("VOD 설정이 저장되었습니다.");
            loadSettings();
        } catch (e: unknown) {
            toast.error(getErrorMessage(e, "VOD 설정 저장에 실패했습니다."));
        } finally {
            setVodSaving(false);
        }
    };

    // ── Chat settings save ──
    const handleSaveChatSettings = async () => {
        setChatSaving(true);
        try {
            await api.updateChatSettings({
                chat_archive_enabled: chatArchiveEnabled,
            });
            toast.success("채팅 설정이 저장되었습니다.");
            loadSettings();
        } catch (e: unknown) {
            toast.error(getErrorMessage(e, "채팅 설정 저장에 실패했습니다."));
        } finally {
            setChatSaving(false);
        }
    };

    // ── Discord settings save ──
    const handleSaveDiscordSettings = async () => {
        setDiscordSaving(true);
        try {
            await api.updateDiscordSettings({
                discord_bot_token: discordBotToken || undefined,
                discord_notification_channel_id: discordChannelId || undefined,
            });
            toast.success("Discord 설정이 저장되었습니다. 재시작 후 적용됩니다.");
            loadSettings();
            setDiscordBotToken("");
        } catch (e: unknown) {
            toast.error(getErrorMessage(e, "Discord 설정 저장에 실패했습니다."));
        } finally {
            setDiscordSaving(false);
        }
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                    <SettingsIcon className="w-6 h-6 text-green-500" />
                    Settings
                </h2>
                <p className="text-zinc-400">애플리케이션 설정을 관리합니다.</p>
            </div>

            {/* 탭 네비게이션 */}
            <div className="flex gap-1 border-b border-zinc-800 overflow-x-auto">
                {TABS.map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => handleTabChange(tab.id)}
                        className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-colors border-b-2 -mb-px relative ${
                            activeTab === tab.id
                                ? "border-green-500 text-green-400"
                                : "border-transparent text-zinc-500 hover:text-zinc-300"
                        }`}
                    >
                        <span>{tab.icon}</span>
                        {tab.label}
                        {isTabDirty(tab.id) && (
                            <span className="w-2 h-2 rounded-full bg-orange-500 absolute top-2 right-2 animate-pulse" />
                        )}
                        {tab.id === "system" && updateInfo?.has_update && (
                            <span className="w-2 h-2 rounded-full bg-green-500 absolute top-2 right-2 animate-pulse" />
                        )}
                    </button>
                ))}
            </div>

            {/* 탭 콘텐츠 */}
            <div className="space-y-6">

                {/* ══════════════════ 일반 탭 ══════════════════ */}
                {activeTab === "general" && (
                    <div className="bg-zinc-900/50 p-6 rounded-xl border border-zinc-800 space-y-5">
                        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                            <SettingsIcon className="w-5 h-5 text-green-500" />
                            일반 설정
                        </h3>

                        {/* 기본 저장 경로 */}
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-zinc-300 flex items-center gap-2">
                                <FolderOpen className="w-4 h-4" />
                                저장 경로
                            </label>
                            {isDocker ? (
                                <div className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm text-zinc-500 font-mono cursor-not-allowed select-none">
                                    {downloadDir}
                                </div>
                            ) : (
                                <DirInput
                                    value={downloadDir}
                                    onChange={setDownloadDir}
                                    placeholder="예: E:\recordings"
                                />
                            )}
                            <p className="text-xs text-zinc-500">
                                {isDocker ? (
                                    <span className="flex items-start gap-1">
                                        <span className="text-yellow-400">⚠️</span>
                                        Docker 환경에서는 <b className="text-zinc-300">docker-compose.yml</b> 볼륨 설정으로 경로를 변경하세요. (<span className="font-mono">/your/path:/app/backend/recordings</span>)
                                    </span>
                                ) : (
                                    "라이브 녹화 + 채팅 로그가 저장되는 기본 경로입니다."
                                )}
                            </p>
                        </div>

                        {/* 분할 저장 경로 토글 */}
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <label className="text-sm font-medium text-zinc-300">
                                    분할 저장 경로 사용
                                </label>
                                <ToggleSwitch
                                    checked={splitDownloadDirs}
                                    onChange={setSplitDownloadDirs}
                                />
                            </div>
                            <p className="text-xs text-zinc-500">
                                활성화 시 콘텐츠 종류별로 저장 경로를 분리할 수 있습니다.
                            </p>

                            {splitDownloadDirs && (
                                <div className="space-y-4 pl-4 border-l-2 border-zinc-700 pt-1">
                                    <div className="space-y-2">
                                        <label className="text-xs font-medium text-zinc-400 flex items-center gap-1.5">
                                            <Folder className="w-3.5 h-3.5" />
                                            치지직 VOD / 클립 저장 경로
                                        </label>
                                        {isDocker ? (
                                            <div className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm text-zinc-500 font-mono cursor-not-allowed select-none">
                                                {vodChzzkDir || "기본 저장 경로 사용"}
                                            </div>
                                        ) : (
                                            <DirInput
                                                value={vodChzzkDir}
                                                onChange={setVodChzzkDir}
                                                placeholder="비어있으면 기본 저장 경로 사용"
                                            />
                                        )}
                                        <p className="text-xs text-zinc-600">chzzk.naver.com URL 다운로드에 적용됩니다.</p>
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-xs font-medium text-zinc-400 flex items-center gap-1.5">
                                            <Folder className="w-3.5 h-3.5" />
                                            외부 다운로드 저장 경로 (유튜브 등)
                                        </label>
                                        {isDocker ? (
                                            <div className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm text-zinc-500 font-mono cursor-not-allowed select-none">
                                                {vodExternalDir || "기본 저장 경로 사용"}
                                            </div>
                                        ) : (
                                            <DirInput
                                                value={vodExternalDir}
                                                onChange={setVodExternalDir}
                                                placeholder="비어있으면 기본 저장 경로 사용"
                                            />
                                        )}
                                        <p className="text-xs text-zinc-600">유튜브 등 외부 URL(yt-dlp) 다운로드에 적용됩니다.</p>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Monitor Interval */}
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-zinc-300 flex items-center gap-2">
                                <Timer className="w-4 h-4" />
                                감시 주기 (초)
                            </label>
                            <input
                                type="number"
                                min={5}
                                max={300}
                                value={monitorInterval}
                                onChange={(e) => setMonitorInterval(parseInt(e.target.value) || 30)}
                                className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-green-500"
                            />
                            <p className="text-xs text-zinc-500">채널 라이브 상태를 확인하는 간격 (5~300초).</p>
                        </div>

                        {/* Output Format */}
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-zinc-300 flex items-center gap-2">
                                <Film className="w-4 h-4" />
                                라이브 녹화 포맷
                            </label>
                            <Select
                                value={liveFormat}
                                onChange={setLiveFormat}
                                options={[
                                    { value: "ts", label: "TS — MPEG Transport Stream (권장)" },
                                    { value: "mkv", label: "MKV — Matroska" },
                                    { value: "mp4", label: "MP4 (권장하지 않음 — 라이브 중단 시 파일 손상 가능)" },
                                ]}
                            />
                            <p className="text-xs text-zinc-500">
                                TS/MKV는 스트리밍에 최적화된 컨테이너로 녹화 중단 시에도 파일이 유지됩니다. MP4는 라이브 녹화에 적합하지 않습니다.
                            </p>
                        </div>

                        {/* Recording Quality */}
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-zinc-300 flex items-center gap-2">
                                <Gauge className="w-4 h-4" />
                                녹화 품질
                            </label>
                            <Select
                                value={recordingQuality}
                                onChange={setRecordingQuality}
                                options={[
                                    { value: "best", label: "최고 (Best)" },
                                    { value: "1080p", label: "1080p" },
                                    { value: "720p", label: "720p" },
                                    { value: "480p", label: "480p" },
                                ]}
                            />
                            <p className="text-xs text-zinc-500">yt-dlp가 지원하는 화질 중 선택됩니다.</p>
                        </div>

                        <button
                            onClick={handleSaveGeneralSettings}
                            disabled={genSaving}
                            className="w-full bg-green-600 hover:bg-green-500 disabled:bg-zinc-700 text-white py-2.5 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
                        >
                            {genSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                            {genSaving ? "저장 중..." : "일반 설정 저장"}
                        </button>
                    </div>
                )}

                {/* ══════════════════ 다운로드 탭 ══════════════════ */}
                {activeTab === "download" && (
                    <div className="space-y-6">
                        {/* VOD Download Settings */}
                        <div className="bg-zinc-900/50 p-6 rounded-xl border border-zinc-800 space-y-5">
                            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                                <Film className="w-5 h-5 text-purple-500" />
                                VOD 다운로드 설정
                            </h3>

                            <div className="space-y-4">
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-zinc-300 flex items-center gap-2">
                                        <Download className="w-4 h-4" />
                                        동시 다운로드 개수
                                    </label>
                                    <input
                                        type="number"
                                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-purple-500"
                                        value={vodMaxConcurrent}
                                        onChange={(e) => setVodMaxConcurrent(Number(e.target.value))}
                                        min={1}
                                        max={10}
                                    />
                                    <p className="text-xs text-zinc-500">한 번에 다운로드할 수 있는 최대 영상 개수 (1-10개)</p>
                                </div>

                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-zinc-300 flex items-center gap-2">
                                        <Gauge className="w-4 h-4" />
                                        기본 화질
                                    </label>
                                    <Select
                                        value={vodDefaultQuality}
                                        onChange={setVodDefaultQuality}
                                        options={[
                                            { value: "best", label: "최고 화질 (Best)" },
                                            { value: "1080p", label: "1080p" },
                                            { value: "720p", label: "720p" },
                                            { value: "480p", label: "480p" },
                                        ]}
                                    />
                                    <p className="text-xs text-zinc-500">VOD 다운로드 시 기본으로 사용할 화질</p>
                                </div>

                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-zinc-300 flex items-center gap-2">
                                        <Gauge className="w-4 h-4" />
                                        최대 다운로드 속도 (MB/s)
                                    </label>
                                    <input
                                        type="number"
                                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-purple-500"
                                        value={vodMaxSpeed}
                                        onChange={(e) => setVodMaxSpeed(Number(e.target.value))}
                                        min={0}
                                        max={1000}
                                    />
                                    <p className="text-xs text-zinc-500">0 = 무제한, 네트워크 대역폭 제한 시 사용</p>
                                </div>

                                {/* VOD 다운로드 포맷 */}
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-zinc-300 flex items-center gap-2">
                                        <Film className="w-4 h-4" />
                                        VOD 다운로드 포맷
                                    </label>
                                    <Select
                                        value={vodFormat}
                                        onChange={setVodFormat}
                                        options={[
                                            { value: "mp4", label: "MP4 — MPEG-4 (권장)" },
                                            { value: "mkv", label: "MKV — Matroska" },
                                            { value: "ts", label: "TS — MPEG Transport Stream" },
                                        ]}
                                    />
                                    <p className="text-xs text-zinc-500">
                                        VOD/클립은 MP4가 가장 호환성이 좋습니다. 오디오·비디오 병합이 필요한 경우 ffmpeg를 사용합니다.
                                    </p>
                                </div>
                            </div>

                            <button
                                onClick={handleSaveVodSettings}
                                disabled={vodSaving}
                                className="w-full bg-purple-600 hover:bg-purple-500 text-white font-bold py-2 px-4 rounded-lg transition-all active:scale-95 disabled:opacity-50 flex items-center justify-center gap-2"
                            >
                                {vodSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                                {vodSaving ? "저장 중..." : "VOD 설정 저장"}
                            </button>
                        </div>

                        {/* Download Settings */}
                        <div className="bg-zinc-900/50 p-6 rounded-xl border border-zinc-800 space-y-5">
                            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                                <Download className="w-5 h-5 text-blue-500" />
                                다운로드 설정
                            </h3>

                            <div>
                                <label className="block text-sm font-medium text-zinc-300 mb-2">
                                    미완료 파일 보관 (.part)
                                </label>
                                <div className="flex items-center gap-3">
                                    <ToggleSwitch
                                        checked={keepParts}
                                        onChange={setKeepParts}
                                        activeColor="bg-green-600"
                                        focusRingColor="focus:ring-green-500"
                                    />
                                    <span className="text-sm text-zinc-500">
                                        {keepParts ? "취소/오류 시 보관" : "취소 시 삭제"}
                                    </span>
                                </div>
                            </div>

                            <div>
                                <label className="flex text-sm font-medium text-zinc-300 mb-2 items-center gap-2">
                                    <RefreshCcw className="w-4 h-4" />
                                    자동 재시도 횟수
                                </label>
                                <input
                                    type="number"
                                    min={0}
                                    max={100}
                                    value={maxRetries}
                                    onChange={(e) => setMaxRetries(parseInt(e.target.value) || 0)}
                                    className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-green-500"
                                />
                                <p className="text-xs text-zinc-500 mt-1">라이브 녹화 중단 시 자동 재시도 횟수.</p>
                            </div>

                            {/* Chat Archive (다운로드 관련) */}
                            <div>
                                <label className="block text-sm font-medium text-zinc-300 mb-2">
                                    실시간 채팅 저장
                                </label>
                                <div className="flex items-center gap-3">
                                    <ToggleSwitch
                                        checked={chatArchiveEnabled}
                                        onChange={setChatArchiveEnabled}
                                        activeColor="bg-cyan-600"
                                        focusRingColor="focus:ring-cyan-500"
                                    />
                                    <span className="text-sm text-zinc-500">
                                        {chatArchiveEnabled ? "녹화 시 채팅 자동 저장" : "채팅 저장 안 함"}
                                    </span>
                                </div>
                                <p className="text-xs text-zinc-500 mt-2">
                                    활성화 시 녹화와 함께 채팅 메시지를 JSONL 파일로 저장합니다.
                                </p>
                            </div>

                            <div className="flex gap-3">
                                <button
                                    onClick={handleSaveDownloadSettings}
                                    disabled={dlSaving}
                                    className="flex-1 bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-700 text-white py-2.5 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
                                >
                                    {dlSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                                    {dlSaving ? "저장 중..." : "저장"}
                                </button>
                                <button
                                    onClick={handleSaveChatSettings}
                                    disabled={chatSaving}
                                    className="flex-1 bg-cyan-600 hover:bg-cyan-500 disabled:bg-zinc-700 text-white py-2.5 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
                                >
                                    {chatSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <MessageSquare className="w-4 h-4" />}
                                    {chatSaving ? "저장 중..." : "채팅 설정 저장"}
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {/* ══════════════════ 인증 탭 ══════════════════ */}
                {activeTab === "auth" && (
                    <div className="space-y-6">
                        {/* ── Chzzk 인증 ── */}
                        <div className="bg-zinc-900/50 p-6 rounded-xl border border-zinc-800 space-y-5">
                            <div className="flex items-center justify-between">
                                <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                                    <span className="w-3 h-3 rounded-full bg-purple-400 inline-block" />
                                    치지직 (Chzzk)
                                </h3>
                                <div className="flex items-center gap-2">
                                    {cookieStatus === "checking" ? (
                                        <span className="px-2 py-1 rounded text-xs font-bold bg-zinc-800 text-zinc-400 flex items-center gap-1">
                                            <Loader2 className="w-3 h-3 animate-spin" /> CHECKING...
                                        </span>
                                    ) : cookieStatus === "valid" ? (
                                        <span className="px-2 py-1 rounded text-xs font-bold bg-green-500/20 text-green-400 flex items-center gap-1">
                                            <Shield className="w-3 h-3" /> 유효함 {nickname && `(${nickname})`}
                                        </span>
                                    ) : cookieStatus === "invalid" ? (
                                        <span className="px-2 py-1 rounded text-xs font-bold bg-red-500/20 text-red-400 flex items-center gap-1">
                                            <AlertCircle className="w-3 h-3" /> 만료/미설정
                                        </span>
                                    ) : (
                                        <button onClick={checkCookieStatus} className="px-2 py-1 rounded text-xs font-bold bg-zinc-800 text-zinc-400 hover:text-white transition-colors">
                                            상태 확인
                                        </button>
                                    )}
                                </div>
                            </div>

                            <div className="space-y-4">
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-zinc-300">NID_AUT</label>
                                    <input
                                        type="password"
                                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-purple-500"
                                        value={nidAut}
                                        onChange={(e) => setNidAut(e.target.value)}
                                        placeholder="NID_AUT 쿠키 값 입력..."
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-zinc-300">NID_SES</label>
                                    <input
                                        type="password"
                                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-purple-500"
                                        value={nidSes}
                                        onChange={(e) => setNidSes(e.target.value)}
                                        placeholder="NID_SES 쿠키 값 입력..."
                                    />
                                </div>
                            </div>

                            <div className="flex gap-3">
                                <button
                                    onClick={handleUpdateCookies}
                                    className="flex-1 bg-zinc-800 hover:bg-zinc-700 text-white py-2 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
                                >
                                    <Save className="w-4 h-4" /> 저장
                                </button>
                                <button
                                    onClick={handleTestCookies}
                                    className="flex-1 bg-purple-600 hover:bg-purple-500 text-white py-2 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
                                >
                                    <Shield className="w-4 h-4" /> 검증
                                </button>
                            </div>
                        </div>

                        {/* ── TwitCasting 인증 ── */}
                        <div className="bg-zinc-900/50 p-6 rounded-xl border border-zinc-800 space-y-5">
                            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                                <span className="w-3 h-3 rounded-full bg-orange-400 inline-block" />
                                TwitCasting
                            </h3>
                            <p className="text-xs text-zinc-500">
                                TwitCasting API v2 인증 정보입니다.{" "}
                                <a
                                    href="https://twitcasting.tv/developer.php"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-orange-400 hover:underline"
                                >
                                    twitcasting.tv/developer.php
                                </a>
                                {" "}에서 앱 등록 후 발급받으세요.
                            </p>

                            <div className="space-y-4">
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-zinc-300">Client ID</label>
                                    <input
                                        type="text"
                                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-orange-500"
                                        value={twitcastingClientId}
                                        onChange={(e) => setTwitcastingClientId(e.target.value)}
                                        placeholder="TwitCasting Client ID..."
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-zinc-300">Client Secret</label>
                                    <input
                                        type="password"
                                        className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-orange-500"
                                        value={twitcastingClientSecret}
                                        onChange={(e) => setTwitcastingClientSecret(e.target.value)}
                                        placeholder="TwitCasting Client Secret..."
                                    />
                                </div>
                            </div>

                            <button
                                onClick={handleSaveTwitcasting}
                                disabled={twitcastingSaving}
                                className="w-full bg-orange-600 hover:bg-orange-500 disabled:bg-zinc-700 text-white py-2.5 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
                            >
                                {twitcastingSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                                {twitcastingSaving ? "저장 중..." : "TwitCasting 설정 저장"}
                            </button>
                        </div>

                        {/* ── X Spaces 인증 ── */}
                        <div className="bg-zinc-900/50 p-6 rounded-xl border border-zinc-800 space-y-5">
                            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                                <span className="w-3 h-3 rounded-full bg-cyan-400 inline-block" />
                                X Spaces
                            </h3>
                            <p className="text-xs text-zinc-500">
                                X Spaces 녹화 시 사용할 쿠키 파일을 업로드하세요. 브라우저 확장(cookies.txt)으로 추출할 수 있습니다.
                            </p>

                            <div className="space-y-4">
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-zinc-300">
                                        쿠키 파일{" "}
                                        <span className="text-zinc-500 font-normal">(선택 — Netscape 형식)</span>
                                    </label>
                                    <div className="flex items-center gap-3">
                                        <div className={`flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg border ${xCookieFileSet ? "border-green-700 bg-green-950/40 text-green-400" : "border-zinc-700 bg-zinc-950 text-zinc-500"}`}>
                                            {xCookieFileSet
                                                ? <><CheckCircle2 className="w-3.5 h-3.5" /> 업로드됨</>
                                                : "없음"
                                            }
                                        </div>
                                        <input
                                            ref={cookieFileInputRef}
                                            type="file"
                                            accept=".txt"
                                            className="hidden"
                                            onChange={handleUploadXCookie}
                                        />
                                        <button
                                            type="button"
                                            onClick={() => cookieFileInputRef.current?.click()}
                                            disabled={xCookieUploading}
                                            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-zinc-800 hover:bg-zinc-700 disabled:bg-zinc-800 text-white rounded-lg border border-zinc-700 transition-colors"
                                        >
                                            {xCookieUploading
                                                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                                : <Upload className="w-3.5 h-3.5" />
                                            }
                                            {xCookieUploading ? "업로드 중..." : "파일 선택"}
                                        </button>
                                        {xCookieFileSet && (
                                            <button
                                                type="button"
                                                onClick={handleDeleteXCookie}
                                                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-zinc-800 hover:bg-red-900/50 text-zinc-400 hover:text-red-400 rounded-lg border border-zinc-700 hover:border-red-800 transition-colors"
                                            >
                                                <Trash2 className="w-3.5 h-3.5" />
                                                삭제
                                            </button>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* ══════════════════ 알림 탭 ══════════════════ */}
                {activeTab === "notifications" && (
                    <div className="bg-zinc-900/50 p-6 rounded-xl border border-zinc-800 space-y-5">
                        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                            <MessageCircle className="w-5 h-5 text-purple-500" />
                            Discord Bot 알림
                        </h3>

                        <div>
                            <label className="block text-sm font-medium text-zinc-300 mb-2">Bot 토큰</label>
                            <input
                                type="password"
                                value={discordBotToken}
                                onChange={(e) => setDiscordBotToken(e.target.value)}
                                placeholder="Bot 토큰을 입력하세요 (변경 시에만)"
                                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder:text-zinc-600 focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500"
                            />
                            <p className="text-xs text-zinc-500 mt-2">
                                비어있으면 기존 설정 유지. Discord Developer Portal에서 발급받은 Bot 토큰을 입력하세요.
                            </p>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-zinc-300 mb-2">알림 채널 ID</label>
                            <input
                                type="text"
                                value={discordChannelId}
                                onChange={(e) => setDiscordChannelId(e.target.value)}
                                placeholder="Discord 채널 ID를 입력하세요"
                                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder:text-zinc-600 focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500"
                            />
                            <p className="text-xs text-zinc-500 mt-2">
                                개발자 모드 활성화 후 채널 우클릭 → ID 복사로 확인 가능합니다.
                            </p>
                        </div>

                        <div className="flex items-center gap-2 text-sm">
                            <div className={`w-2 h-2 rounded-full ${settings?.discord_bot_configured ? "bg-green-500" : "bg-zinc-600"}`} />
                            <span className="text-zinc-400">
                                {settings?.discord_bot_configured ? "Bot 설정됨 (재시작 후 활성화)" : "Bot 미설정"}
                            </span>
                        </div>

                        <button
                            onClick={handleSaveDiscordSettings}
                            disabled={discordSaving}
                            className="w-full bg-purple-600 hover:bg-purple-500 disabled:bg-zinc-700 text-white py-2.5 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
                        >
                            {discordSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                            {discordSaving ? "저장 중..." : "Discord 설정 저장"}
                        </button>
                    </div>
                )}

                {/* ══════════════════ 외관 탭 ══════════════════ */}
                {activeTab === "appearance" && (
                    <div className="bg-zinc-900/50 p-6 rounded-xl border border-zinc-800 space-y-5">
                        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                            <Palette className="w-5 h-5" style={{ color: 'var(--primary)' }} />
                            외관 (Appearance)
                        </h3>

                        <div className="space-y-3">
                            <label className="text-sm font-medium text-zinc-300 flex items-center gap-2">
                                <Palette className="w-4 h-4" />
                                컬러 테마
                            </label>
                            <div className="flex gap-3 flex-wrap items-center">
                                {THEMES.map((t) => (
                                    <button
                                        key={t.id}
                                        onClick={() => setTheme(t.id as ThemeId)}
                                        title={t.label}
                                        className={`w-10 h-10 rounded-full border-4 transition-all hover:scale-110 ${themeId === t.id ? 'border-white scale-110' : 'border-transparent'}`}
                                        style={{ backgroundColor: t.primary }}
                                    />
                                ))}
                                <div className="relative">
                                    <input
                                        ref={colorPickerRef}
                                        type="color"
                                        className="absolute opacity-0 w-0 h-0"
                                        value={customColor}
                                        onChange={(e) => setCustomColor(e.target.value)}
                                    />
                                    <button
                                        onClick={() => colorPickerRef.current?.click()}
                                        title="사용자 지정 색상"
                                        className={`w-10 h-10 rounded-full border-4 transition-all hover:scale-110 overflow-hidden ${themeId === 'custom' ? 'border-white scale-110' : 'border-transparent'}`}
                                        style={{
                                            background: themeId === 'custom'
                                                ? customColor
                                                : 'conic-gradient(red, yellow, lime, cyan, blue, magenta, red)',
                                        }}
                                    />
                                </div>
                            </div>
                            <p className="text-xs text-zinc-500">
                                현재: <span className="font-medium" style={{ color: 'var(--primary)' }}>
                                    {themeId === 'custom'
                                        ? `사용자 지정 (${customColor})`
                                        : THEMES.find(t => t.id === themeId)?.label}
                                </span>
                            </p>
                        </div>

                        <div className="space-y-2">
                            <label className="text-sm font-medium text-zinc-300 flex items-center gap-2">
                                <Type className="w-4 h-4" />
                                페이지 타이틀
                            </label>
                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    maxLength={32}
                                    value={titleInput}
                                    onChange={(e) => setTitleInput(e.target.value)}
                                    placeholder="Signal Recorder"
                                    className="flex-1 bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:outline-none"
                                    style={{ borderColor: titleInput !== pageTitle ? 'var(--primary)' : '' }}
                                />
                                <button
                                    onClick={() => setPageTitle(titleInput)}
                                    className="px-4 py-2 rounded-lg text-sm font-medium text-black transition-colors"
                                    style={{ backgroundColor: 'var(--primary)' }}
                                >
                                    적용
                                </button>
                            </div>
                            <p className="text-xs text-zinc-500">브라우저 탭 제목이 변경됩니다 (최대 32자)</p>
                        </div>

                        <div className="space-y-2">
                            <label className="text-sm font-medium text-zinc-300 flex items-center gap-2">
                                <ImageIcon className="w-4 h-4" />
                                탭 아이콘 (Favicon)
                            </label>
                            <div className="flex gap-2">
                                <input
                                    ref={iconInputRef}
                                    type="file"
                                    accept="image/png,image/jpeg,image/webp,image/gif"
                                    className="hidden"
                                    onChange={(e) => {
                                        const file = e.target.files?.[0];
                                        if (!file) return;
                                        if (file.size > 512 * 1024) { alert('파일 크기는 512KB 이하여야 합니다.'); return; }
                                        const reader = new FileReader();
                                        reader.onload = (ev) => setIconUrl(ev.target?.result as string);
                                        reader.readAsDataURL(file);
                                    }}
                                />
                                <button
                                    onClick={() => iconInputRef.current?.click()}
                                    className="flex-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 py-2 rounded-lg text-sm transition-colors flex items-center justify-center gap-2"
                                >
                                    <ImageIcon className="w-4 h-4" />
                                    이미지 업로드 (PNG · JPG · WEBP, 512KB 이하)
                                </button>
                            </div>
                            <p className="text-xs text-zinc-500">브라우저 탭 좌측 아이콘이 변경됩니다</p>
                        </div>

                        <button
                            onClick={() => { resetAll(); setTitleInput('Signal Recorder'); }}
                            className="w-full bg-zinc-800 hover:bg-zinc-700 text-zinc-400 py-2.5 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
                        >
                            <RotateCcw className="w-4 h-4" />
                            외관 초기화 (기본값 복원)
                        </button>
                    </div>
                )}

                {/* ══════════════════ 시스템 탭 ══════════════════ */}
                {activeTab === "system" && (
                    <div className="bg-zinc-900/50 p-6 rounded-xl border border-zinc-800 space-y-5">
                        <div className="flex items-center justify-between">
                            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                                <Terminal className="w-5 h-5 text-emerald-500" />
                                시스템 관리 및 업데이트
                            </h3>
                        </div>

                        <div className="space-y-4">
                            <div className="bg-zinc-950 p-4 rounded-lg border border-zinc-800 flex items-center justify-between">
                                <div>
                                    <h4 className="text-sm font-medium text-white mb-1">현재 버전</h4>
                                    <p className="text-xs text-zinc-400 font-mono">v{updateInfo?.current_version || "..."}</p>
                                </div>
                                <div className="text-right">
                                    <h4 className="text-sm font-medium text-white mb-1">최신 릴리즈</h4>
                                    <p className="text-xs text-zinc-400 font-mono">{updateInfo?.latest_version ? `v${updateInfo.latest_version}` : "확인 중..."}</p>
                                </div>
                            </div>

                            <div className="flex gap-3">
                                <button
                                    onClick={handleCheckUpdate}
                                    disabled={checkingUpdate}
                                    className="flex-1 bg-zinc-800 hover:bg-zinc-700 disabled:bg-zinc-800 disabled:text-zinc-500 text-white py-2.5 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
                                >
                                    <RefreshCcw className={`w-4 h-4 ${checkingUpdate ? 'animate-spin' : ''}`} />
                                    {checkingUpdate ? "확인 중..." : "업데이트 확인"}
                                </button>
                                
                                {updateInfo?.has_update && (
                                    <button
                                        onClick={() => setShowUpdateModal(true)}
                                        className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white py-2.5 rounded-lg font-bold transition-colors shadow-[0_0_15px_rgba(16,185,129,0.3)] flex items-center justify-center gap-2"
                                    >
                                        <Gift className="w-4 h-4 animate-bounce" />
                                        v{updateInfo.latest_version} 업데이트 하기
                                    </button>
                                )}
                            </div>

                            {updateInfo?.has_update && updateInfo?.release_notes && (
                                <div className="mt-6">
                                    <h4 className="text-sm font-medium text-emerald-400 mb-2 flex items-center gap-2">
                                        <Gift className="w-4 h-4" /> 릴리즈 노트
                                    </h4>
                                    <div className="bg-zinc-950 border border-emerald-900/50 p-4 rounded-lg overflow-y-auto max-h-60 scrollbar-thin scrollbar-thumb-zinc-700 whitespace-pre-wrap text-sm text-zinc-300 font-mono leading-relaxed">
                                        {updateInfo.release_notes}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* ══════════════════ 정보 탭 ══════════════════ */}
                {activeTab === "info" && (
                    <div className="bg-zinc-900/50 p-6 rounded-xl border border-zinc-800">
                        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <Info className="w-5 h-5 text-zinc-500" />
                            시스템 정보
                        </h3>
                        <div className="space-y-3 text-sm">
                            <div className="flex justify-between py-2 border-b border-zinc-800">
                                <span className="text-zinc-500">앱 이름</span>
                                <span className="text-zinc-200">{settings?.app_name || "Loading..."}</span>
                            </div>
                            <div className="flex justify-between py-2 border-b border-zinc-800">
                                <span className="text-zinc-500">FFmpeg 경로</span>
                                <span className="text-zinc-200 truncate max-w-[220px]" title={settings?.ffmpeg_path}>
                                    {settings?.ffmpeg_path || "Loading..."}
                                </span>
                            </div>
                            <div className="flex justify-between py-2 border-b border-zinc-800">
                                <span className="text-zinc-500">서버</span>
                                <span className="text-zinc-200">
                                    {settings ? `${settings.host}:${settings.port}` : "Loading..."}
                                </span>
                            </div>
                            <div className="flex justify-between py-2 border-b border-zinc-800">
                                <span className="text-zinc-500">Discord Bot</span>
                                <span className={settings?.discord_bot_configured ? "text-green-400" : "text-zinc-500"}>
                                    {settings?.discord_bot_configured ? "연결됨" : "미설정"}
                                </span>
                            </div>
                            <div className="flex justify-between py-2 border-b border-zinc-800">
                                <span className="text-zinc-500">TwitCasting 설정</span>
                                <span className={settings?.twitcasting_client_id ? "text-orange-400" : "text-zinc-500"}>
                                    {settings?.twitcasting_client_id ? "설정됨" : "미설정"}
                                </span>
                            </div>
                            <div className="flex justify-between py-2">
                                <span className="text-zinc-500">X Spaces 쿠키</span>
                                <span className={settings?.x_cookie_file ? "text-cyan-400" : "text-zinc-500"}>
                                    {settings?.x_cookie_file ? "설정됨" : "미설정"}
                                </span>
                            </div>
                        </div>
                    </div>
                )}

            </div>

            {/* Update Modal */}
            {showUpdateModal && updateInfo && (
                <UpdateModal 
                    info={updateInfo} 
                    onClose={() => setShowUpdateModal(false)} 
                />
            )}
        </div>
    );
}
