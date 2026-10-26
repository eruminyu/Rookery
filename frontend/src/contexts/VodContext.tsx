import { createContext, useContext, useState, useEffect, ReactNode, useCallback, useRef } from "react";
import { api, VodTask } from "../api/client";
import { useToast } from "../components/ui/Toast";
import { VodErrorModal } from "../components/ui/VodErrorModal";
import { getErrorMessage } from "../utils/error";
import { diagnoseVodError } from "../utils/vodError";

export interface VodContextType {
    tasks: VodTask[];
    activeCount: number;
    defaultQuality: string;
    addTask: (url: string, quality?: string) => Promise<string>;
    cancelTask: (taskId: string) => Promise<void>;
    pauseTask: (taskId: string) => Promise<void>;
    resumeTask: (taskId: string) => Promise<void>;
    retryTask: (taskId: string) => Promise<string>;
    clearCompleted: () => Promise<void>;
    openFileLocation: (taskId: string) => Promise<void>;
    inspectTaskError: (task: VodTask) => void;
    refreshTasks: () => Promise<void>;
}

const VodContext = createContext<VodContextType | null>(null);

export function VodProvider({ children }: { children: ReactNode }) {
    const toast = useToast();
    const [tasks, setTasks] = useState<VodTask[]>([]);
    const [activeCount, setActiveCount] = useState(0);
    const [defaultQuality, setDefaultQuality] = useState("best");
    const [errorModalTask, setErrorModalTask] = useState<VodTask | null>(null);

    // 이전 폴링 주기의 작업별 상태를 기억해 진행 중이던 작업이 완료/오류로 바뀔 때만 알림·팝업을 띄운다.
    const prevStatesRef = useRef<Map<string, VodTask["state"]> | null>(null);

    useEffect(() => {
        api.getSettings()
            .then((s) => {
                if (s.vod_default_quality) {
                    setDefaultQuality(s.vod_default_quality);
                }
            })
            .catch(() => {});
    }, []);

    const applyStatus = useCallback((data: { tasks: VodTask[]; active_count: number; queued_count: number; total_count: number }) => {
        const prevMap = prevStatesRef.current;
        const nextMap = new Map<string, VodTask["state"]>();

        for (const task of data.tasks) {
            nextMap.set(task.task_id, task.state);
            if (!prevMap) continue;

            const prevState = prevMap.get(task.task_id);
            const wasActive =
                prevState === undefined ||
                prevState === "idle" ||
                prevState === "downloading" ||
                prevState === "paused";

            if (wasActive && task.state === "error") {
                const diagnosis = diagnoseVodError(task);
                const label = task.title && task.title !== "Unknown" ? task.title : task.url;
                toast.error(`VOD 다운로드 실패 (${diagnosis.category}): ${label}`);
                setErrorModalTask(task);
            } else if (
                prevState !== undefined &&
                prevState !== "completed" &&
                task.state === "completed"
            ) {
                toast.success(`VOD 다운로드 완료: ${task.title}`);
            }
        }

        prevStatesRef.current = nextMap;
        setTasks(data.tasks);
        setActiveCount(data.active_count);
    }, [toast]);

    const refreshTasks = useCallback(async () => {
        try {
            const data = await api.getAllVodStatus();
            applyStatus(data);
        } catch (e) {
            console.error("VOD 상태 갱신 실패:", e);
        }
    }, [applyStatus]);

    // 전역 폴링 (컴포넌트 언마운트와 무관하게 지속)
    useEffect(() => {
        refreshTasks();
        const interval = setInterval(refreshTasks, 2000);
        return () => clearInterval(interval);
    }, [refreshTasks]);

    const addTask = async (url: string, quality?: string) => {
        const { task_id } = await api.downloadVod(url, quality || defaultQuality || "best");
        await refreshTasks();
        return task_id;
    };

    const cancelTask = async (taskId: string) => {
        await api.cancelVodDownload(taskId);
        await refreshTasks();
    };

    const pauseTask = async (taskId: string) => {
        await api.pauseVodDownload(taskId);
        await refreshTasks();
    };

    const resumeTask = async (taskId: string) => {
        await api.resumeVodDownload(taskId);
        await refreshTasks();
    };

    const retryTask = async (taskId: string) => {
        const { new_task_id } = await api.retryVodDownload(taskId);
        await refreshTasks();
        return new_task_id;
    };

    const clearCompleted = async () => {
        await api.clearCompletedVodTasks();
        await refreshTasks();
    };

    const openFileLocation = async (taskId: string) => {
        try {
            await api.openVodFileLocation(taskId);
        } catch (e: unknown) {
            toast.error(getErrorMessage(e, "파일 위치를 열 수 없습니다."));
        }
    };

    const inspectTaskError = useCallback((task: VodTask) => {
        setErrorModalTask(task);
    }, []);

    return (
        <VodContext.Provider
            value={{
                tasks,
                activeCount,
                defaultQuality,
                addTask,
                cancelTask,
                pauseTask,
                resumeTask,
                retryTask,
                clearCompleted,
                openFileLocation,
                inspectTaskError,
                refreshTasks,
            }}
        >
            {children}
            {errorModalTask && (
                <VodErrorModal
                    task={errorModalTask}
                    onClose={() => setErrorModalTask(null)}
                    onRetry={async (taskId) => {
                        await retryTask(taskId);
                    }}
                />
            )}
        </VodContext.Provider>
    );
}

export function useVod() {
    const context = useContext(VodContext);
    if (!context) {
        throw new Error("useVod는 VodProvider 내부에서만 사용할 수 있습니다.");
    }
    return context;
}
