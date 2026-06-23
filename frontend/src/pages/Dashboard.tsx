import { useState, useEffect, useRef } from "react";
import { Plus, Trash2, Video, Radio, Play, AlertTriangle, Square, AlertCircle, Users, Eye, Loader2, WifiOff, MessageSquare, ChevronDown, Lock, LayoutGrid, List, RefreshCw } from "lucide-react";
import { api, client, Channel, Platform, PlatformStatus, PLATFORM_LABELS } from "../api/client";
// client를 직접 import해서 멀티 플랫폼 엔드포인트에 접근
const client_raw = client;
import { useToast } from "../components/ui/Toast";
import { useConfirm } from "../components/ui/ConfirmModal";
import { formatDuration, formatBytes } from "../utils/format";
import { getErrorMessage } from "../utils/error";
import { TagManager } from "../components/ui/TagManager";

// 플랫폼별 배지 색상
const PLATFORM_BADGE_STYLES: Record<Platform, string> = {
    chzzk: "bg-purple-500/20 text-purple-300 border-purple-500/30",
    twitcasting: "bg-orange-500/20 text-orange-300 border-orange-500/30",
    x_spaces: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
    youtube: "bg-red-500/20 text-red-300 border-red-500/30",
};

export default function Dashboard() {
    const [channels, setChannels] = useState<Channel[]>([]);
    const [newChannelId, setNewChannelId] = useState("");
    const [selectedPlatform, setSelectedPlatform] = useState<Platform>("chzzk");
    const [platformDropdownOpen, setPlatformDropdownOpen] = useState(false);
    const [platformStatus, setPlatformStatus] = useState<PlatformStatus | null>(null);
    const [loading, setLoading] = useState(false);
    const [initialLoading, setInitialLoading] = useState(true);
    const [connectionError, setConnectionError] = useState(false);
    const toast = useToast();
    const confirm = useConfirm();

    const [filter, setFilter] = useState<"all"|"recording"|"live"|"offline">("all");
    const [viewMode, setViewMode] = useState<"grid"|"list">(
        () => (localStorage.getItem("dashboardViewMode") as "grid" | "list") || "grid"
    );

    const [globalTags, setGlobalTags] = useState<string[]>([]);
    const [selectedFilterTags, setSelectedFilterTags] = useState<string[]>([]);

    useEffect(() => {
        localStorage.setItem("dashboardViewMode", viewMode);
    }, [viewMode]);

    useEffect(() => {
        let eventSource: EventSource | null = null;
        let reconnectTimeout: ReturnType<typeof setTimeout>;

        const connectSSE = () => {
            const baseUrl = client_raw.defaults.baseURL || "/api";
            eventSource = new EventSource(`${baseUrl}/events`);
            
            eventSource.onmessage = (event) => {
                const text = event.data;
                if (!text || text === "ping") return;
                
                try {
                    const parsed = JSON.parse(text);
                    if (parsed.type === "status_update") {
                        setChannels(parsed.data);
                        setConnectionError(false);
                        setInitialLoading(false);
                    }
                } catch (e) {
                    console.error("Failed to parse SSE message:", e);
                }
            };

            eventSource.onerror = () => {
                setConnectionError(true);
                eventSource?.close();
                // 5초 후 재연결 시도
                reconnectTimeout = setTimeout(connectSSE, 5000);
            };
        };

        connectSSE();

        // 부가 정보 Fetch
        api.getPlatformStatus().then(setPlatformStatus).catch(() => {});
        api.getTags().then((data) => setGlobalTags(data.tags)).catch(() => {});

        // 기존처럼 수동으로 한번 당겨와야 SSE 실패 시에도 보여줄 수 있으므로 fallback
        fetchChannels().finally(() => setInitialLoading(false));

        return () => {
            if (eventSource) eventSource.close();
            clearTimeout(reconnectTimeout);
        };
    }, []);

    const isPlatformEnabled = (p: Platform): boolean => {
        if (!platformStatus) return p === "chzzk" || p === "youtube";
        if (p === "chzzk" || p === "youtube") return true;
        if (p === "twitcasting") return platformStatus.twitcasting.enabled;
        if (p === "x_spaces") return platformStatus.x_spaces.enabled;
        return false;
    };

    const fetchChannels = async () => {
        try {
            // 멀티 플랫폼 엔드포인트 사용
            const data = await client_raw.get<Channel[]>("/platforms/channels").then(r => r.data);
            setChannels(data);
            setConnectionError(false);
        } catch {
            setConnectionError(true);
        }
    };

    const handleAddChannel = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newChannelId) return;
        setLoading(true);
        setPlatformDropdownOpen(false);
        try {
            if (selectedPlatform === "chzzk") {
                await api.addChannel(newChannelId);
            } else {
                await api.addPlatformChannel(selectedPlatform, newChannelId);
            }
            setNewChannelId("");
            toast.success("채널이 추가되었습니다.");
            fetchChannels();
        } catch (e: unknown) {
            toast.error(getErrorMessage(e, "채널 추가에 실패했습니다."));
        } finally {
            setLoading(false);
        }
    };

    const handleRemoveChannel = async (channel: Channel) => {
        const displayName = channel.channel_name || channel.channel_id;
        const ok = await confirm({
            title: "채널 제거",
            message: `'${displayName}' 채널을 감시 목록에서 제거할까요?`,
            confirmText: "제거",
            variant: "danger",
        });
        if (!ok) return;
        try {
            const platform = channel.platform || "chzzk";
            if (platform === "chzzk") {
                await api.removeChannel(channel.channel_id);
            } else {
                await api.removePlatformChannel(platform, channel.channel_id);
            }
            toast.success("채널이 제거되었습니다.");
            fetchChannels();
        } catch {
            toast.error("채널 제거에 실패했습니다.");
        }
    };

    const [actionLoading, setActionLoading] = useState<string | null>(null);

    const getChannelKey = (channel: Channel) => channel.composite_key || channel.channel_id;

    const handleStartRecord = async (channel: Channel) => {
        const key = getChannelKey(channel);
        if (actionLoading) return;
        setActionLoading(key);
        try {
            await api.startRecording(key);
            toast.success("녹화를 시작합니다.");
            fetchChannels();
        } catch (e: unknown) {
            toast.error(getErrorMessage(e, "녹화 시작에 실패했습니다."));
        } finally {
            setActionLoading(null);
        }
    };

    const handleStopRecord = async (channel: Channel) => {
        const key = getChannelKey(channel);
        if (actionLoading) return;
        const ok = await confirm({
            title: "녹화 중지",
            message: "현재 진행 중인 녹화를 중지할까요?",
            confirmText: "중지",
            variant: "danger",
        });
        if (!ok) return;
        setActionLoading(key);
        try {
            await api.stopRecording(key);
            toast.success("녹화가 중지되었습니다.");
            fetchChannels();
        } catch (e: unknown) {
            toast.error(getErrorMessage(e, "녹화 중지에 실패했습니다."));
        } finally {
            setActionLoading(null);
        }
    };

    const handleStopAll = async () => {
        const ok = await confirm({
            title: "전체 녹화 중지",
            message: "현재 진행 중인 모든 녹화를 중지하시겠습니까?",
            confirmText: "모두 중지",
            variant: "danger",
            requireTyping: "모두 중지",
        });
        if (!ok) return;

        try {
            const res = await api.stopAllRecordings();
            toast.success(res.message);
            fetchChannels();
        } catch (e: unknown) {
            toast.error(getErrorMessage(e, "전체 녹화 중지에 실패했습니다."));
        }
    };

    const handleScanNow = async () => {
        try {
            await api.scanNow();
            toast.success("즉시 스캔 요청됨. 잠시 후 상태가 업데이트됩니다.");
        } catch {
            toast.error("즉시 스캔 요청에 실패했습니다.");
        }
    };

    const handleToggleAutoRecord = async (channel: Channel) => {
        const platform = channel.platform || "chzzk";
        try {
            if (platform === "chzzk") {
                await api.toggleAutoRecord(channel.channel_id);
            } else {
                await api.togglePlatformAutoRecord(platform, channel.channel_id);
            }
            fetchChannels();
        } catch {
            toast.error("자동 녹화 설정 변경에 실패했습니다.");
        }
    };

    const handleChannelAddTag = async (channel: Channel, tag: string) => {
        const key = getChannelKey(channel);
        const currentTags = channel.tags || [];
        if (!currentTags.includes(tag)) {
            const newTags = [...currentTags, tag];
            try {
                await api.updateChannelTags(key, newTags);
                fetchChannels();
            } catch {
                toast.error("태그 추가 실패");
            }
        }
    };

    const handleChannelRemoveTag = async (channel: Channel, tag: string) => {
        const key = getChannelKey(channel);
        const currentTags = channel.tags || [];
        const newTags = currentTags.filter((t) => t !== tag);
        try {
            await api.updateChannelTags(key, newTags);
            fetchChannels();
        } catch {
            toast.error("태그 제거 실패");
        }
    };

    const handleCreateGlobalTag = async (tagName: string) => {
        try {
            const data = await api.createTag(tagName);
            setGlobalTags(data.tags);
        } catch {
            toast.error("태그 생성 실패");
        }
    };

    const liveCount = channels.filter(ch => ch.is_live).length;
    const recCount = channels.filter(ch => ch.recording?.is_recording).length;

    const filteredChannels = channels.filter((ch) => {
        if (filter === "recording" && !ch.recording?.is_recording) return false;
        if (filter === "live" && !ch.is_live) return false;
        if (filter === "offline" && ch.is_live) return false;
        
        if (selectedFilterTags.length > 0) {
            const chTags = ch.tags || [];
            if (!selectedFilterTags.some((t) => chTags.includes(t))) return false;
        }

        return true;
    });

    return (
        <div className="space-y-6">
            {/* 연결 끊김 배너 */}
            {connectionError && !initialLoading && (
                <div className="flex items-center gap-3 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
                    <WifiOff className="w-5 h-5 shrink-0" />
                    <span>서버와 연결이 끊어졌습니다. 자동으로 재연결을 시도합니다...</span>
                </div>
            )}

            <div className="flex flex-col gap-4">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                        <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                            <Radio className="w-6 h-6 text-green-500" />
                            Live Dashboard
                        </h2>
                        <p className="text-zinc-400">
                            채널 {channels.length}개 감시 중 ·{" "}
                            <span className="text-red-400 font-mono">{liveCount} LIVE</span> ·{" "}
                            <span className="text-green-400 font-mono">{recCount} REC</span>
                        </p>
                    </div>

                    <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                        <form onSubmit={handleAddChannel} className="flex gap-2">
                            {/* 플랫폼 드롭다운 */}
                            <div className="relative shrink-0">
                                <button
                                    type="button"
                                    onClick={() => setPlatformDropdownOpen(!platformDropdownOpen)}
                                    className="h-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-white text-sm flex items-center gap-1.5 hover:border-zinc-700 transition-colors"
                                >
                                    <span className={`inline-block w-2 h-2 rounded-full ${
                                        selectedPlatform === "chzzk" ? "bg-purple-400" :
                                        selectedPlatform === "twitcasting" ? "bg-orange-400" :
                                        selectedPlatform === "youtube" ? "bg-red-500" : "bg-cyan-400"
                                    }`} />
                                    <span className="hidden sm:inline-block">{PLATFORM_LABELS[selectedPlatform]}</span>
                                    <ChevronDown className="w-3 h-3 text-zinc-500" />
                                </button>
                                {platformDropdownOpen && (
                                    <div className="absolute top-full mt-1 right-0 sm:left-0 z-20 bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl min-w-[180px] overflow-hidden">
                                        {(Object.keys(PLATFORM_LABELS) as Platform[]).map((p) => {
                                            const enabled = isPlatformEnabled(p);
                                            return (
                                                <button
                                                    key={p}
                                                    type="button"
                                                    disabled={!enabled}
                                                    onClick={() => { if (enabled) { setSelectedPlatform(p); setPlatformDropdownOpen(false); } }}
                                                    className={`w-full text-left px-3 py-2 text-sm flex items-center gap-2 transition-colors ${
                                                        !enabled
                                                            ? "text-zinc-600 cursor-not-allowed"
                                                            : selectedPlatform === p
                                                                ? "text-white hover:bg-zinc-800"
                                                                : "text-zinc-400 hover:bg-zinc-800"
                                                    }`}
                                                >
                                                    <span className={`inline-block w-2 h-2 rounded-full ${
                                                        !enabled ? "bg-zinc-700" :
                                                        p === "chzzk" ? "bg-purple-400" :
                                                        p === "twitcasting" ? "bg-orange-400" :
                                                        p === "youtube" ? "bg-red-500" : "bg-cyan-400"
                                                    }`} />
                                                    <span className="flex-1">{PLATFORM_LABELS[p]}</span>
                                                    {!enabled && (
                                                        <span className="flex items-center gap-1 text-[10px] text-zinc-600">
                                                            <Lock className="w-3 h-3" />
                                                            설정 필요
                                                        </span>
                                                    )}
                                                </button>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>
                            <input
                                type="text"
                                value={newChannelId}
                                onChange={(e) => setNewChannelId(e.target.value)}
                                placeholder={
                                    selectedPlatform === "chzzk" ? "치지직 채널 ID..." :
                                    selectedPlatform === "youtube" ? "핸들(@username) 또는 채널 ID..." :
                                    selectedPlatform === "x_spaces" ? "X 유저네임..." : "채널 ID..."
                                }
                                className="w-full sm:w-48 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-1 focus:ring-green-500 min-w-0"
                            />
                            <button
                                type="submit"
                                disabled={loading}
                                className="shrink-0 bg-green-600 hover:bg-green-500 text-white px-3 sm:px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 disabled:opacity-50"
                            >
                                <Plus className="w-4 h-4" /> <span className="hidden sm:inline-block">추가</span>
                            </button>
                        </form>
                        
                        <div className="w-px h-8 bg-zinc-800 hidden sm:block" />
                        
                        <div className="flex bg-zinc-900 border border-zinc-800 rounded-lg p-1 shrink-0 self-end sm:self-auto">
                            <button
                                type="button"
                                onClick={() => setViewMode("grid")}
                                className={`p-1.5 rounded-md transition-colors ${viewMode === "grid" ? "bg-zinc-800 text-white" : "text-zinc-500 hover:text-white"}`}
                                title="그리드 뷰"
                            >
                                <LayoutGrid className="w-4 h-4" />
                            </button>
                            <button
                                type="button"
                                onClick={() => setViewMode("list")}
                                className={`p-1.5 rounded-md transition-colors ${viewMode === "list" ? "bg-zinc-800 text-white" : "text-zinc-500 hover:text-white"}`}
                                title="리스트 뷰"
                            >
                                <List className="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                </div>

                {/* Filters Row */}
                <div className="flex flex-col gap-3 border-b border-zinc-800/50 pb-4">
                    <div className="flex items-center justify-between overflow-x-auto">
                        <div className="flex space-x-2">
                            <button onClick={()=>setFilter("all")} className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${filter === "all" ? "bg-zinc-800 text-white" : "text-zinc-400 hover:bg-zinc-800/50"}`}>전체</button>
                            <button onClick={()=>setFilter("recording")} className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${filter === "recording" ? "bg-zinc-800 text-green-400" : "text-zinc-400 hover:bg-zinc-800/50"}`}>녹화 중</button>
                            <button onClick={()=>setFilter("live")} className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${filter === "live" ? "bg-zinc-800 text-red-400" : "text-zinc-400 hover:bg-zinc-800/50"}`}>라이브</button>
                            <button onClick={()=>setFilter("offline")} className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${filter === "offline" ? "bg-zinc-800 text-zinc-300" : "text-zinc-400 hover:bg-zinc-800/50"}`}>오프라인</button>
                        </div>
                        <div className="flex gap-2">
                            <button onClick={handleScanNow} className="px-3 py-1.5 bg-blue-500/10 text-blue-400 border border-blue-500/20 hover:bg-blue-500/20 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5 whitespace-nowrap">
                                <RefreshCw className="w-4 h-4" /> 즉시 스캔
                            </button>
                            <button onClick={handleStopAll} disabled={recCount === 0} className="px-3 py-1.5 bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5 disabled:opacity-50 hover:shadow-lg hover:shadow-red-500/20 whitespace-nowrap">
                                <Square className="w-4 h-4 fill-current" /> 전체 중지
                            </button>
                        </div>
                    </div>
                    {/* Tags Filter */}
                    <div className="flex items-center">
                        <span className="text-xs font-semibold text-zinc-500 mr-3 shrink-0">태그 필터</span>
                        <TagManager 
                            availableTags={globalTags}
                            selectedTags={selectedFilterTags}
                            onAddTag={(tag) => setSelectedFilterTags(prev => [...prev, tag])}
                            onRemoveTag={(tag) => setSelectedFilterTags(prev => prev.filter(t => t !== tag))}
                            onCreateTag={handleCreateGlobalTag}
                        />
                    </div>
                </div>
            </div>

            <div className={viewMode === "grid" ? "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4" : "flex flex-col gap-3"}>
                {/* 초기 로딩 스켈레톤 */}
                {initialLoading && (
                    <>
                        {[1, 2, 3].map((i) => (
                            <div key={i} className={`bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden animate-pulse ${viewMode === "list" ? "flex" : ""}`}>
                                <div className={`bg-zinc-800 ${viewMode === "list" ? "w-48 h-full min-h-[108px] shrink-0" : "w-full aspect-video"}`} />
                                <div className="p-4 space-y-3 flex-1 flex flex-col">
                                    <div className="flex items-center gap-3">
                                        <div className="w-9 h-9 rounded-full bg-zinc-800 shrink-0" />
                                        <div className="flex-1 space-y-2">
                                            <div className="h-4 bg-zinc-800 rounded w-3/4" />
                                            <div className="h-3 bg-zinc-800 rounded w-1/2" />
                                        </div>
                                    </div>
                                    <div className="h-8 bg-zinc-800 rounded mt-auto" />
                                </div>
                            </div>
                        ))}
                    </>
                )}

                {!initialLoading && filteredChannels?.map((channel) => (
                    <ChannelCard
                        key={channel.composite_key || channel.channel_id}
                        channel={channel}
                        onStartRecord={handleStartRecord}
                        onStopRecord={handleStopRecord}
                        onRemove={handleRemoveChannel}
                        onToggleAutoRecord={handleToggleAutoRecord}
                        isActionLoading={actionLoading === (channel.composite_key || channel.channel_id)}
                        viewMode={viewMode}
                        globalTags={globalTags}
                        onAddTag={handleChannelAddTag}
                        onRemoveTag={handleChannelRemoveTag}
                        onCreateTag={handleCreateGlobalTag}
                    />
                ))}

                {!initialLoading && filteredChannels.length === 0 && (
                    <div className="col-span-full py-12 text-center text-zinc-500">
                        {channels.length === 0 ? "감시 중인 채널이 없습니다. 채널 ID를 입력하여 모니터링을 시작하세요." : "필터 조건에 맞는 채널이 없습니다."}
                    </div>
                )}
            </div>
        </div>
    );
}

// ── 채널 카드 서브 컴포넌트 ──────────────────────────

import { clsx } from "clsx";

interface ChannelCardProps {
    channel: Channel;
    onStartRecord: (channel: Channel) => void;
    onStopRecord: (channel: Channel) => void;
    onRemove: (channel: Channel) => void;
    onToggleAutoRecord: (channel: Channel) => void;
    isActionLoading: boolean;
    viewMode: "grid"|"list";
    globalTags: string[];
    onAddTag: (channel: Channel, tag: string) => void;
    onRemoveTag: (channel: Channel, tag: string) => void;
    onCreateTag: (tag: string) => void;
}

function ChannelCard({ 
    channel, 
    onStartRecord, 
    onStopRecord, 
    onRemove, 
    onToggleAutoRecord, 
    isActionLoading, 
    viewMode,
    globalTags,
    onAddTag,
    onRemoveTag,
    onCreateTag
}: ChannelCardProps) {
    const displayName = channel.channel_name || channel.channel_id;
    const platform = channel.platform || "chzzk";

    // ── 로컬 1초 타이머: start_time 기준으로 경과 시간 직접 계산 ──
    const [localDuration, setLocalDuration] = useState(channel.recording?.duration_seconds ?? 0);
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

    useEffect(() => {
        if (timerRef.current) {
            clearInterval(timerRef.current);
            timerRef.current = null;
        }

        const startTimeStr = channel.recording?.start_time;
        if (channel.recording?.is_recording && startTimeStr) {
            // 백엔드에서 받은 start_time 기준으로 현재 경과 시간 즉시 계산
            const startMs = new Date(startTimeStr).getTime();
            const tick = () => setLocalDuration(Math.floor((Date.now() - startMs) / 1000));
            tick(); // 즉시 1회 실행
            timerRef.current = setInterval(tick, 1000);
        } else {
            setLocalDuration(channel.recording?.duration_seconds ?? 0);
        }

        return () => {
            if (timerRef.current) {
                clearInterval(timerRef.current);
                timerRef.current = null;
            }
        };
    }, [channel.recording?.is_recording, channel.recording?.start_time]);

    return (
        <div className={clsx(
            "bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden hover:border-zinc-700 transition-all group",
            viewMode === "list" ? "flex items-stretch" : "flex flex-col",
            channel.recording?.is_recording && "animate-pulse-border"
        )}>
            {/* 썸네일 영역 */}
            <div className={clsx(
                "relative bg-zinc-950 overflow-hidden shrink-0",
                viewMode === "list" ? "w-48 xl:w-64" : "w-full aspect-video"
            )}>
                {channel.is_live && channel.thumbnail_url ? (
                    <img
                        src={channel.thumbnail_url}
                        alt={`${displayName} 방송 썸네일`}
                        className="w-full h-full object-cover transition-opacity duration-300"
                        loading="lazy"
                    />
                ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center text-zinc-700 bg-linear-to-br from-zinc-900 to-zinc-950">
                        <AlertCircle className="w-10 h-10 mb-2 opacity-40" />
                        <span className="text-xs font-semibold tracking-wider opacity-60">OFFLINE</span>
                    </div>
                )}

                {/* LIVE / REC 배지 */}
                {channel.is_live && (
                    <div className="absolute top-2 left-2 flex gap-1.5">
                        <span className="bg-red-600 text-white text-[10px] font-bold px-2 py-0.5 rounded-sm flex items-center gap-1 shadow-lg shadow-red-500/30 animate-pulse">
                            ● LIVE
                        </span>
                        {channel.recording?.is_recording && (
                            <span className="bg-green-600 text-white text-[10px] font-bold px-2 py-0.5 rounded-sm flex items-center gap-1 shadow-lg shadow-green-500/30">
                                REC
                            </span>
                        )}
                    </div>
                )}

                {/* 시청자 수 */}
                {channel.is_live && channel.viewer_count != null && channel.viewer_count > 0 && (
                    <div className="absolute bottom-2 right-2 bg-black/70 backdrop-blur-sm text-white text-[11px] font-medium px-2 py-0.5 rounded flex items-center gap-1">
                        <Eye className="w-3 h-3" />
                        {channel.viewer_count.toLocaleString()}
                    </div>
                )}

                {/* 플랫폼 배지 */}
                {platform !== "chzzk" && (
                    <div className={`absolute bottom-2 left-2 text-[10px] font-bold px-2 py-0.5 rounded-sm border ${PLATFORM_BADGE_STYLES[platform]}`}>
                        {PLATFORM_LABELS[platform]}
                    </div>
                )}

                {/* 우측 상단 액션/배지 그룹 */}
                <div className="absolute top-2 right-2 flex items-start gap-1.5 z-10">
                    {/* 에러 배지 */}
                    {channel.last_error && (
                        <div className="relative group/error">
                            <div className="p-1.5 bg-red-600/90 text-white rounded-lg backdrop-blur-sm shadow-lg shadow-red-500/30 flex items-center justify-center cursor-help">
                                <AlertTriangle className="w-3.5 h-3.5 text-white" />
                            </div>
                            {/* 툴팁 */}
                            <div className="absolute top-full right-0 mt-1 w-48 bg-zinc-900 border border-red-500/50 text-red-200 text-xs p-2.5 rounded-lg shadow-xl opacity-0 invisible group-hover/error:opacity-100 group-hover/error:visible transition-all z-20 pointer-events-none wrap-break-word">
                                {channel.last_error}
                            </div>
                        </div>
                    )}

                    {/* 삭제 버튼 (hover) */}
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            onRemove(channel);
                        }}
                        className="p-1.5 bg-black/60 backdrop-blur-sm hover:bg-red-500/80 text-zinc-400 hover:text-white rounded-lg transition-all opacity-0 group-hover:opacity-100"
                        title="채널 제거"
                    >
                        <Trash2 className="w-3.5 h-3.5" />
                    </button>
                </div>
            </div>

            {/* 채널 정보 */}
            <div className={clsx(
                "p-4 flex-1 flex",
                viewMode === "list" ? "flex-row items-center gap-4 py-3" : "flex-col"
            )}>
                {/* 리스트뷰 좌측: 썸네일+이름 */}
                <div className={clsx(
                    "flex min-w-0 flex-1",
                    viewMode === "list" ? "items-center gap-4 pr-4" : "items-center gap-3 mb-2"
                )}>
                    {/* 프로필 이미지 */}
                    {channel.profile_image_url ? (
                        <img
                            src={channel.profile_image_url}
                            alt={displayName}
                            className="w-9 h-9 rounded-full object-cover shrink-0 border-2 border-zinc-700"
                        />
                    ) : (
                        <div className="w-9 h-9 rounded-full bg-zinc-800 flex items-center justify-center shrink-0 border-2 border-zinc-700">
                            <Users className="w-4 h-4 text-zinc-500" />
                        </div>
                    )}
                    <div className="min-w-0 flex-1">
                        <h3 className="font-bold text-white text-sm truncate" title={displayName}>
                            {displayName}
                        </h3>
                        {channel.title && channel.is_live ? (
                            <p className="text-xs text-zinc-400 truncate" title={channel.title}>
                                {channel.title}
                            </p>
                        ) : (
                            <p className="text-xs text-zinc-600 font-mono truncate">
                                {channel.channel_id}
                            </p>
                        )}
                    </div>
                </div>

                {/* 관련 태그 및 카테고리 (그리드뷰 전용 또는 리스트뷰 컬럼 방식) */}
                <div className="flex flex-col gap-2 mb-3">
                    {channel.category && channel.is_live && viewMode === "grid" && (
                        <div className="whitespace-nowrap">
                            <span className="text-[11px] bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded-full inline-block max-w-[150px] truncate align-bottom border border-zinc-700">
                                {channel.category}
                            </span>
                        </div>
                    )}
                    <div className="w-full">
                        <TagManager 
                            availableTags={globalTags}
                            selectedTags={channel.tags || []}
                            onAddTag={(tag) => onAddTag(channel, tag)}
                            onRemoveTag={(tag) => onRemoveTag(channel, tag)}
                            onCreateTag={onCreateTag}
                        />
                    </div>
                </div>

                {/* 상태 정보 */}
                <div className={clsx(
                    "flex shrink-0",
                    viewMode === "list" ? "items-center gap-6 px-4 border-l border-zinc-800/50" : "flex-col gap-3 mb-3"
                )}>
                    {viewMode === "grid" && (
                        <div className="flex items-center justify-between text-xs">
                            <span className="text-zinc-500">상태</span>
                            <span className={`font-medium ${channel.is_live ? 'text-red-400' : 'text-zinc-500'}`}>
                                {channel.is_live ? 'LIVE' : 'OFFLINE'}
                            </span>
                        </div>
                    )}
                    <div className={clsx("flex items-center text-xs", viewMode === "list" ? "gap-2" : "justify-between")}>
                        <span className="text-zinc-500 shrink-0">자동 녹화</span>
                        <button
                            onClick={() => onToggleAutoRecord(channel)}
                            className={`relative w-9 h-5 rounded-full transition-colors duration-200 shrink-0 ${channel.auto_record ? 'bg-green-500' : 'bg-zinc-700'
                                }`}
                            title={channel.auto_record ? '자동 녹화 끄기' : '자동 녹화 켜기'}
                        >
                            <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200 ${channel.auto_record ? 'translate-x-4' : 'translate-x-0'
                                }`} />
                        </button>
                    </div>
                </div>

                {/* 녹화 컨트롤 */}
                <div className={clsx("mt-auto shrink-0", viewMode === "list" ? "ml-4 w-60 border-l border-zinc-800/50 pl-4 mt-0 flex items-center" : "")}>
                    {channel.recording?.is_recording ? (
                        <div className={clsx("w-full space-y-2", viewMode === "list" && "mb-0")}>
                            <div className="flex items-center gap-2">
                                <div className="flex-1 bg-red-500/10 border border-red-500/20 rounded-lg p-2 flex items-center justify-center gap-2 text-xs text-red-400 animate-pulse">
                                    <Video className="w-3 h-3" />
                                    {formatDuration(localDuration)}
                                </div>
                                <button
                                    onClick={() => onStopRecord(channel)}
                                    disabled={isActionLoading}
                                    className="p-2 bg-zinc-800 hover:bg-red-600 text-red-400 hover:text-white rounded-lg border border-zinc-700 hover:border-red-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                    title="녹화 중단"
                                >
                                    {isActionLoading ? (
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                    ) : (
                                        <Square className="w-4 h-4 fill-current" />
                                    )}
                                </button>
                            </div>
                            {/* 녹화 통계 */}
                            <div className="grid grid-cols-3 gap-2 text-xs">
                                <div className="bg-zinc-900/50 border border-zinc-800 rounded px-2 py-1">
                                    <div className="text-zinc-500">용량</div>
                                    <div className="text-zinc-300 font-mono">
                                        {formatBytes(channel.recording.file_size_bytes || 0)}
                                    </div>
                                </div>
                                <div className="bg-zinc-900/50 border border-zinc-800 rounded px-2 py-1">
                                    <div className="text-zinc-500">속도</div>
                                    <div className="text-zinc-300 font-mono">
                                        {(channel.recording.download_speed || 0).toFixed(2)} MB/s
                                    </div>
                                </div>
                                <div className="bg-zinc-900/50 border border-zinc-800 rounded px-2 py-1">
                                    <div className="text-zinc-500">비트레이트</div>
                                    <div className="text-zinc-300 font-mono">
                                        {(channel.recording.bitrate || 0).toFixed(0)} kbps
                                    </div>
                                </div>
                            </div>

                            {/* 채팅 아카이빙 상태 */}
                            {channel.chat_archiving?.is_running && (
                                <div className="flex items-center gap-2 bg-cyan-500/10 border border-cyan-500/20 rounded-lg p-2 text-xs text-cyan-400">
                                    <MessageSquare className="w-3 h-3" />
                                    채팅 수집 중 ({channel.chat_archiving.message_count.toLocaleString()}개)
                                </div>
                            )}
                        </div>
                    ) : channel.is_live ? (
                        <button
                            onClick={() => onStartRecord(channel)}
                            disabled={isActionLoading}
                            className="w-full bg-zinc-800 hover:bg-zinc-700 text-green-400 border border-zinc-700 rounded-lg p-2 flex items-center justify-center gap-2 text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {isActionLoading ? (
                                <>
                                    <Loader2 className="w-3 h-3 animate-spin" />
                                    처리 중...
                                </>
                            ) : (
                                <>
                                    <Play className="w-3 h-3 fill-current" />
                                    수동 녹화 시작
                                </>
                            )}
                        </button>
                    ) : (
                        <div className="bg-zinc-800/50 border border-zinc-800 rounded-lg p-2 flex items-center gap-2 text-xs text-zinc-500">
                            <AlertCircle className="w-3 h-3" />
                            방송 대기 중...
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
