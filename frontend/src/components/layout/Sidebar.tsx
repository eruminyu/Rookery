import { useState, useRef, useEffect } from "react";
import { NavLink } from "react-router-dom";
import { LayoutDashboard, Download, Settings, Tv, Menu, X, MessageSquare, BarChart2, Radio, Bell, CheckCircle, AlertCircle, AlertTriangle, Gift, Terminal } from "lucide-react";
import { clsx } from "clsx";
import { useTheme } from "../../context/ThemeContext";
import { useVod } from "../../contexts/VodContext";
import { useToast } from "../../components/ui/Toast";
import { api, UpdateInfo } from "../../api/client";

export function Sidebar() {
    const [mobileOpen, setMobileOpen] = useState(false);
    const [showNotifications, setShowNotifications] = useState(false);
    const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
    const notifRef = useRef<HTMLDivElement>(null);

    const { pageTitle, iconUrl } = useTheme();
    const { activeCount, tasks } = useVod();
    const { history, markAllRead } = useToast();

    const unreadCount = history.filter(h => !h.read).length;

    // 업데이트 정보 로드
    useEffect(() => {
        api.getUpdateStatus()
            .then(info => setUpdateInfo(info))
            .catch(err => console.error("업데이트 정보 로드 실패:", err));
    }, []);

    // 모달 외부 클릭 시 닫기
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
                setShowNotifications(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const downloadingTasks = tasks.filter(t => t.state === 'downloading');
    const primaryTask = downloadingTasks[0];

    const navGroups = [
        {
            title: "모니터링",
            items: [
                { name: "Live Dashboard", to: "/", icon: LayoutDashboard },
            ]
        },
        {
            title: "미디어 허브",
            items: [
                { name: "VOD Downloader", to: "/vod", icon: Download },
                { name: "X Spaces", to: "/archive", icon: Radio },
                { name: "Chat Logs", to: "/chat", icon: MessageSquare },
            ]
        },
        {
            title: "설정 및 기타",
            items: [
                { name: "Statistics", to: "/stats", icon: BarChart2 },
                { name: "Settings", to: "/settings", icon: Settings },
                { name: "System Logs", to: "/system-logs", icon: Terminal },
            ]
        }
    ];

    const navContent = (
        <>
            {/* ── 로고 헤더 ─── */}
            <div className="p-5 flex items-center justify-between border-b border-zinc-800 relative z-50">
                <div className="flex items-center gap-3 min-w-0">
                    {/* 아이콘: 커스텀 favicon 있으면 이미지, 없으면 기본 Tv 아이콘 */}
                    <div
                        className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 overflow-hidden"
                        style={{ background: "var(--primary-dim)", boxShadow: "0 0 0 1.5px var(--primary)" }}
                    >
                        {iconUrl ? (
                            <img
                                src={iconUrl}
                                alt="icon"
                                className="w-full h-full object-cover"
                            />
                        ) : (
                            <Tv className="w-5 h-5" style={{ color: "var(--primary)" }} />
                        )}
                    </div>

                    {/* 탭 이름 (pageTitle) */}
                    <h1
                        className="text-base font-bold truncate leading-tight"
                        style={{ color: "var(--primary)" }}
                        title={pageTitle}
                    >
                        {pageTitle}
                    </h1>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                    {/* 알림 센터 */}
                    <div className="relative" ref={notifRef}>
                        <button
                            onClick={() => {
                                setShowNotifications(!showNotifications);
                                if (!showNotifications && unreadCount > 0) {
                                    markAllRead();
                                }
                            }}
                            className="p-1.5 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors relative"
                        >
                            <Bell className="w-5 h-5" />
                            {unreadCount > 0 && (
                                <span className="absolute top-1 right-1.5 w-2 h-2 bg-red-500 rounded-full ring-2 ring-zinc-900" />
                            )}
                        </button>

                        {/* 알림 드롭다운 */}
                        {showNotifications && (
                            <div className="absolute top-full -left-20 sm:left-0 mt-2 w-72 bg-zinc-900/95 backdrop-blur-md border border-zinc-800 rounded-xl shadow-2xl overflow-hidden animate-in fade-in slide-in-from-top-2">
                                <div className="p-3 border-b border-zinc-800 flex items-center justify-between">
                                    <h3 className="text-sm font-semibold text-white">알림 센터</h3>
                                    {history.length > 0 && (
                                        <span className="text-xs text-zinc-500">{history.length}개</span>
                                    )}
                                </div>
                                <div className="max-h-80 overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-700">
                                    {history.length === 0 ? (
                                        <div className="p-6 text-center text-sm text-zinc-500">
                                            알림 내역이 없습니다.
                                        </div>
                                    ) : (
                                        <div className="flex flex-col">
                                            {history.map((item) => {
                                                const Icon = item.type === "success" ? CheckCircle : item.type === "error" ? AlertCircle : AlertTriangle;
                                                return (
                                                    <div key={item.id} className="p-3 border-b border-zinc-800/50 last:border-0 hover:bg-zinc-800/50 transition-colors">
                                                        <div className="flex gap-2">
                                                            <span className={clsx(
                                                                "shrink-0 mt-0.5",
                                                                item.type === "success" ? "text-green-400" :
                                                                item.type === "error" ? "text-red-400" : "text-yellow-400"
                                                            )}>
                                                                <Icon className="w-4 h-4" />
                                                            </span>
                                                            <div className="min-w-0 flex-1">
                                                                <p className="text-sm text-zinc-300 wrap-break-word leading-tight">{item.message}</p>
                                                                <p className="text-[10px] text-zinc-500 mt-1">
                                                                    {item.timestamp.toLocaleTimeString()}
                                                                </p>
                                                            </div>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>

                    {/* 모바일 닫기 버튼 */}
                    <button
                        onClick={() => setMobileOpen(false)}
                        className="lg:hidden p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors shrink-0"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>
            </div>

            {/* ── 네비게이션 ─── */}
            <nav className="flex-1 px-3 py-4 space-y-6 overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-700">
                {navGroups.map((group, idx) => (
                    <div key={idx}>
                        <h2 className="px-3 text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">
                            {group.title}
                        </h2>
                        <div className="space-y-1">
                            {group.items.map((item) => (
                                <NavLink
                                    key={item.to}
                                    to={item.to}
                                    end={item.to === "/"}
                                    onClick={() => setMobileOpen(false)}
                                    className={({ isActive }) =>
                                        clsx(
                                            "flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 text-sm font-medium",
                                            isActive
                                                ? "nav-active"
                                                : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"
                                        )
                                    }
                                >
                                    {({ isActive }) => (
                                        <>
                                            <item.icon
                                                className="w-4 h-4 shrink-0 transition-colors"
                                                style={isActive ? { color: "var(--primary)" } : undefined}
                                            />
                                            <span>{item.name}</span>
                                        </>
                                    )}
                                </NavLink>
                            ))}
                        </div>
                    </div>
                ))}
            </nav>

            {/* ── 하단 버전 ─── */}
            <div className="p-4 border-t border-zinc-800">
                <div className="flex flex-col items-center justify-center gap-1">
                    <div className="text-xs text-zinc-600 font-medium">
                        Signal Recorder
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-[10px] text-zinc-500 font-mono">
                            v{updateInfo?.current_version || "..."}
                        </span>
                        {updateInfo?.has_update && (
                            <NavLink to="/settings" className="flex items-center gap-1 px-1.5 py-0.5 bg-green-500/20 text-green-400 rounded-md hover:bg-green-500/30 transition-colors">
                                <Gift className="w-3 h-3" />
                                <span className="text-[10px] font-bold">Update</span>
                            </NavLink>
                        )}
                    </div>
                </div>
            </div>

            {/* ── 미니 다운로드 위젯 ─── */}
            {activeCount > 0 && primaryTask && (
                <div className="p-4 border-t border-zinc-800">
                    <div className="bg-zinc-800/50 rounded-lg p-3 cursor-pointer hover:bg-zinc-800 transition-colors">
                        <NavLink to="/vod" onClick={() => setMobileOpen(false)} className="block">
                            <div className="flex justify-between items-center mb-2">
                                <span className="text-xs font-semibold text-zinc-300 shrink-0">VOD 다운로드 ({activeCount})</span>
                                <span className="text-[10px] text-green-400 font-mono">{primaryTask.download_speed.toFixed(1)} MB/s</span>
                            </div>
                            <div className="text-xs text-zinc-400 truncate mb-2" title={primaryTask.title}>
                                {primaryTask.title}
                            </div>
                            <div className="w-full bg-zinc-700 h-1.5 rounded-full overflow-hidden">
                                <div className="bg-green-500 h-full transition-all duration-300" style={{ width: `${primaryTask.progress}%` }} />
                            </div>
                        </NavLink>
                    </div>
                </div>
            )}
        </>
    );

    return (
        <>
            {/* 모바일 햄버거 버튼 */}
            <button
                onClick={() => setMobileOpen(true)}
                className="fixed top-4 left-4 z-100 lg:hidden p-2 bg-zinc-900 border border-zinc-800 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
            >
                <Menu className="w-5 h-5" />
            </button>

            {/* 데스크톱 사이드바 */}
            <aside className="hidden lg:flex w-64 bg-zinc-900 border-r border-zinc-800 flex-col h-screen shrink-0">
                {navContent}
            </aside>

            {/* 모바일 오버레이 */}
            {mobileOpen && (
                <div className="fixed inset-0 z-99 lg:hidden">
                    <div
                        className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-backdrop"
                        onClick={() => setMobileOpen(false)}
                    />
                    <aside className="relative w-64 bg-zinc-900 border-r border-zinc-800 flex flex-col h-screen animate-slide-in-sidebar">
                        {navContent}
                    </aside>
                </div>
            )}
        </>
    );
}
