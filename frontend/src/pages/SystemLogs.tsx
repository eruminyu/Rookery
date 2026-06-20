import { useState, useEffect, useCallback, useRef } from "react";
import {
    Terminal,
    Search,
    RefreshCw,
    FileText,
    Loader2,
    ArrowDown,
    Play,
    Pause,
} from "lucide-react";
import { clsx } from "clsx";
import { api, SystemLogFile } from "../api/client";
import { useToast } from "../components/ui/Toast";
import { formatBytes, formatDate as _formatDate } from "../utils/format";

function formatDate(iso: string): string {
    return _formatDate(iso, true);
}

export default function SystemLogs() {
    const [selectedFile, setSelectedFile] = useState<SystemLogFile | null>(null);
    const toast = useToast();

    return (
        <div className="flex flex-col h-[calc(100vh-6rem)]">
            <div className="mb-6 shrink-0">
                <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                    <Terminal className="w-6 h-6 text-green-500" />
                    System Logs
                </h2>
                <p className="text-zinc-400">서버의 실시간 시스템 로그 및 일자별 백업 로그를 조회합니다.</p>
            </div>

            <div className="flex flex-1 gap-6 min-h-0">
                {/* 왼쪽 패널: 로그 파일 목록 */}
                <div className="w-1/3 flex flex-col bg-zinc-900/30 border border-zinc-800 rounded-xl overflow-hidden shadow-sm">
                    <LogFileListView 
                        selectedFile={selectedFile} 
                        onSelect={setSelectedFile} 
                        toast={toast} 
                    />
                </div>

                {/* 오른쪽 패널: 로그 컨텐츠 뷰어 */}
                <div className="w-2/3 flex flex-col bg-zinc-900/30 border border-zinc-800 rounded-xl overflow-hidden shadow-sm">
                    {selectedFile === null ? (
                        <div className="flex-1 flex flex-col items-center justify-center text-zinc-500">
                            <Terminal className="w-12 h-12 mb-4 opacity-30 animate-pulse text-green-500" />
                            <p className="text-sm">왼쪽 목록에서 조회할 시스템 로그 파일을 선택하세요.</p>
                        </div>
                    ) : (
                        <LogContentViewer
                            file={selectedFile}
                            toast={toast}
                        />
                    )}
                </div>
            </div>
        </div>
    );
}

// ── 로그 파일 목록 컴포넌트 ─────────────────────────────────

interface LogFileListViewProps {
    selectedFile: SystemLogFile | null;
    onSelect: (file: SystemLogFile) => void;
    toast: ReturnType<typeof useToast>;
}

function LogFileListView({ selectedFile, onSelect, toast }: LogFileListViewProps) {
    const [files, setFiles] = useState<SystemLogFile[]>([]);
    const [loading, setLoading] = useState(true);

    const loadFiles = useCallback(async (silent = false) => {
        if (!silent) setLoading(true);
        try {
            const data = await api.getSystemLogFiles();
            setFiles(data);
            // 만약 선택된 파일이 없고 파일 목록이 존재하면 자동으로 가장 첫번째 파일(보통 실시간 로그인 service.log)을 선택
            if (!selectedFile && data.length > 0) {
                onSelect(data[0]);
            }
        } catch {
            toast.error("로그 파일 목록을 불러오는 데 실패했습니다.");
        } finally {
            if (!silent) setLoading(false);
        }
    }, [selectedFile, onSelect, toast]);

    useEffect(() => {
        loadFiles();
    }, []);

    if (loading) {
        return (
            <div className="flex flex-1 items-center justify-center text-zinc-500">
                <Loader2 className="w-5 h-5 animate-spin mr-2" />
                <span className="text-sm">로그 목록 불러오는 중...</span>
            </div>
        );
    }

    if (files.length === 0) {
        return (
            <div className="flex flex-col flex-1 items-center justify-center p-8 text-center">
                <Terminal className="w-8 h-8 text-zinc-700 mb-3" />
                <p className="text-zinc-400 font-medium text-sm mb-1">시스템 로그 파일이 없습니다.</p>
            </div>
        );
    }

    return (
        <div className="flex-1 flex flex-col min-h-0">
            <div className="p-3 border-b border-zinc-800 bg-zinc-900/50 flex items-center justify-between shrink-0">
                <span className="text-xs font-semibold text-zinc-400">로그 파일 목록</span>
                <button 
                    onClick={() => loadFiles(false)} 
                    className="p-1 hover:bg-zinc-800 rounded transition-colors text-zinc-400 hover:text-white"
                    title="목록 새로고침"
                >
                    <RefreshCw className="w-3.5 h-3.5" />
                </button>
            </div>
            
            <div className="flex-1 overflow-y-auto divide-y divide-zinc-800/30 scrollbar-thin scrollbar-thumb-zinc-700">
                {files.map((file) => {
                    const isSelected = selectedFile?.filename === file.filename;
                    const isLive = file.filename === "service.log";
                    
                    return (
                        <div
                            key={file.filename}
                            onClick={() => onSelect(file)}
                            className={clsx(
                                "flex items-center gap-3 px-4 py-3.5 cursor-pointer transition-colors group",
                                isSelected ? "bg-green-500/10 hover:bg-green-500/20" : "hover:bg-zinc-800/40"
                            )}
                        >
                            <FileText className={clsx(
                                "w-4 h-4 shrink-0", 
                                isSelected ? "text-green-500" : "text-zinc-500 group-hover:text-green-500/70"
                            )} />

                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-0.5">
                                    <p className={clsx(
                                        "text-xs font-bold truncate transition-colors",
                                        isSelected ? "text-green-400" : "text-zinc-300 group-hover:text-white"
                                    )}>
                                        {file.filename}
                                    </p>
                                    {isLive && (
                                        <span className="px-1.5 py-0.5 bg-green-500/20 text-green-400 text-[9px] font-extrabold rounded uppercase tracking-wider animate-pulse">
                                            LIVE
                                        </span>
                                    )}
                                </div>
                                <p className="text-[10px] text-zinc-500">
                                    수정: {formatDate(file.modified_at)}
                                </p>
                            </div>

                            <span className="text-[10px] font-mono text-zinc-500 shrink-0">
                                {formatBytes(file.size_bytes)}
                            </span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

// ── 로그 내용 뷰어 컴포넌트 ─────────────────────────────────

interface LogContentViewerProps {
    file: SystemLogFile;
    toast: ReturnType<typeof useToast>;
}

function LogContentViewer({ file, toast }: LogContentViewerProps) {
    const [content, setContent] = useState("");
    const [totalLines, setTotalLines] = useState(0);
    const [linesLimit, setLinesLimit] = useState(1000); // 기본 1000줄
    const [searchTerm, setSearchTerm] = useState("");
    const [loading, setLoading] = useState(false);
    
    // 자동 스크롤 및 자동 갱신 상태
    const [autoScroll, setAutoScroll] = useState(true);
    const [autoRefresh, setAutoRefresh] = useState(false);
    
    const terminalRef = useRef<HTMLDivElement>(null);
    const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);

    const loadContent = useCallback(async (silent = false) => {
        if (!silent) setLoading(true);
        try {
            const data = await api.getSystemLogContent(file.filename, linesLimit);
            setContent(data.content);
            setTotalLines(data.total_lines);
        } catch {
            toast.error(`로그 내용을 불러오는 데 실패했습니다.`);
        } finally {
            if (!silent) setLoading(false);
        }
    }, [file.filename, linesLimit, toast]);

    // 파일이나 가져올 줄 수가 바뀌면 로그 다시 로드
    useEffect(() => {
        loadContent(false);
    }, [file.filename, linesLimit]);

    // 자동 갱신 타이머 관리
    useEffect(() => {
        if (autoRefresh) {
            refreshTimerRef.current = setInterval(() => {
                loadContent(true);
            }, 5000); // 5초 주기
        } else {
            if (refreshTimerRef.current) {
                clearInterval(refreshTimerRef.current);
                refreshTimerRef.current = null;
            }
        }
        
        return () => {
            if (refreshTimerRef.current) {
                clearInterval(refreshTimerRef.current);
            }
        };
    }, [autoRefresh, loadContent]);

    // 자동 스크롤 수행
    useEffect(() => {
        if (autoScroll && terminalRef.current) {
            terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
        }
    }, [content, autoScroll]);

    // 로그 한 줄을 파싱하여 레벨에 따른 색상 매핑
    const parseLogLine = (line: string) => {
        let colorClass = "text-zinc-300"; // 기본값
        
        if (line.includes(" | ERROR    |") || line.includes(" | ERROR |")) {
            colorClass = "text-red-400 font-semibold";
        } else if (line.includes(" | WARNING  |") || line.includes(" | WARNING |") || line.includes(" | WARN |")) {
            colorClass = "text-amber-400";
        } else if (line.includes(" | DEBUG    |") || line.includes(" | DEBUG |")) {
            colorClass = "text-zinc-500";
        } else if (line.includes(" | INFO     |") || line.includes(" | INFO |")) {
            colorClass = "text-zinc-300";
        }
        
        return colorClass;
    };

    // 검색어 강조 렌더링
    const renderLineWithHighlight = (line: string, colorClass: string, idx: number) => {
        if (!searchTerm) {
            return (
                <div key={idx} className={clsx("py-0.5 whitespace-pre-wrap breakdown-all", colorClass)}>
                    {line}
                </div>
            );
        }

        const parts = line.split(new RegExp(`(${searchTerm})`, "gi"));
        return (
            <div key={idx} className={clsx("py-0.5 whitespace-pre-wrap breakdown-all", colorClass)}>
                {parts.map((part, i) => 
                    part.toLowerCase() === searchTerm.toLowerCase() ? (
                        <mark key={i} className="bg-yellow-500/30 text-yellow-200 px-0.5 rounded border-b border-yellow-500/50">
                            {part}
                        </mark>
                    ) : (
                        part
                    )
                )}
            </div>
        );
    };

    const lines = content.split("\n");
    // 마지막 줄이 개행으로 끝나 분리되어 생긴 빈 줄 제거
    if (lines.length > 0 && lines[lines.length - 1] === "") {
        lines.pop();
    }

    return (
        <div className="flex-1 flex flex-col min-h-0 bg-zinc-950">
            {/* 상단 컨트롤바 */}
            <div className="p-3 border-b border-zinc-800 bg-zinc-900/50 flex flex-wrap items-center justify-between gap-3 shrink-0">
                <div className="flex items-center gap-3">
                    <span className="text-xs font-mono font-semibold text-zinc-400">
                        {file.filename} ({lines.length}/{totalLines} 줄)
                    </span>
                    
                    {/* 불러올 줄 수 버튼그룹 */}
                    <div className="flex bg-zinc-800 rounded p-0.5 border border-zinc-700">
                        {[100, 500, 1000, 0].map((val) => (
                            <button
                                key={val}
                                onClick={() => setLinesLimit(val)}
                                className={clsx(
                                    "px-2 py-1 text-[10px] font-bold rounded transition-colors",
                                    linesLimit === val
                                        ? "bg-green-500/20 text-green-400 border-zinc-600"
                                        : "text-zinc-400 hover:text-white"
                                )}
                            >
                                {val === 0 ? "전체" : `${val}줄`}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    {/* 검색 바 */}
                    <div className="relative">
                        <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
                        <input
                            type="text"
                            placeholder="로그 검색..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="bg-zinc-800/80 border border-zinc-700 text-xs text-white rounded-lg pl-8 pr-3 py-1 w-40 focus:outline-none focus:border-green-500/50 focus:bg-zinc-800 transition-all placeholder-zinc-500"
                        />
                    </div>

                    {/* 실시간 갱신 */}
                    <button
                        onClick={() => setAutoRefresh(!autoRefresh)}
                        className={clsx(
                            "flex items-center gap-1.5 px-2.5 py-1 text-xs font-bold rounded-lg border transition-all",
                            autoRefresh
                                ? "bg-green-500/10 text-green-400 border-green-500/30"
                                : "bg-zinc-800 text-zinc-400 border-zinc-700 hover:bg-zinc-700"
                        )}
                        title={autoRefresh ? "5초마다 자동 새로고침 중" : "자동 새로고침 켜기"}
                    >
                        {autoRefresh ? (
                            <>
                                <Loader2 className="w-3 h-3 animate-spin text-green-400" />
                                <Pause className="w-3 h-3" />
                            </>
                        ) : (
                            <>
                                <Play className="w-3 h-3 text-zinc-500" />
                                <span className="text-[10px]">자동 갱신</span>
                            </>
                        )}
                    </button>

                    {/* 자동 스크롤 */}
                    <button
                        onClick={() => setAutoScroll(!autoScroll)}
                        className={clsx(
                            "p-1.5 rounded-lg border transition-colors",
                            autoScroll
                                ? "bg-green-500/10 text-green-400 border-green-500/30"
                                : "bg-zinc-800 text-zinc-400 border-zinc-700 hover:bg-zinc-700 hover:text-white"
                        )}
                        title="자동 최하단 스크롤"
                    >
                        <ArrowDown className={clsx("w-3.5 h-3.5", autoScroll && "animate-bounce")} />
                    </button>

                    {/* 수동 새로고침 */}
                    <button
                        onClick={() => loadContent(false)}
                        disabled={loading}
                        className="p-1.5 bg-zinc-800 border border-zinc-700 hover:bg-zinc-700 text-zinc-300 hover:text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        title="새로고침"
                    >
                        <RefreshCw className={clsx("w-3.5 h-3.5", loading && "animate-spin")} />
                    </button>
                </div>
            </div>

            {/* 터미널 로그 출력창 */}
            <div 
                ref={terminalRef}
                className="flex-1 p-4 overflow-y-auto font-mono text-[11px] leading-relaxed select-text scrollbar-thin scrollbar-thumb-zinc-800 scrollbar-track-transparent"
            >
                {loading && content.length === 0 ? (
                    <div className="h-full flex items-center justify-center text-zinc-500">
                        <Loader2 className="w-6 h-6 animate-spin mr-2 text-green-500" />
                        <span>로그 로드 중...</span>
                    </div>
                ) : lines.length === 0 ? (
                    <div className="h-full flex items-center justify-center text-zinc-500">
                        <span>로그 기록이 없습니다.</span>
                    </div>
                ) : (
                    lines.map((line, idx) => {
                        const colorClass = parseLogLine(line);
                        return renderLineWithHighlight(line, colorClass, idx);
                    })
                )}
            </div>
        </div>
    );
}
