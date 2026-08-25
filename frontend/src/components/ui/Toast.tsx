import { createContext, useContext, useState, useCallback, useRef } from "react";
import { CheckCircle, AlertCircle, AlertTriangle, X } from "lucide-react";
import { clsx } from "clsx";

// ── Types ────────────────────────────────────────────

export type ToastType = "success" | "error" | "warning";

export interface ToastHistoryItem {
    id: string;
    type: ToastType;
    message: string;
    timestamp: Date;
    read: boolean;
}

interface Toast {
    id: string;
    type: ToastType;
    message: string;
}

export interface ToastContextValue {
    toast: (type: ToastType, message: string) => void;
    success: (message: string) => void;
    error: (message: string) => void;
    warning: (message: string) => void;
    history: ToastHistoryItem[];
    markAllRead: () => void;
    clearHistory: () => void;
}

// ── Context ──────────────────────────────────────────

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
    const ctx = useContext(ToastContext);
    if (!ctx) throw new Error("useToast must be used within ToastProvider");
    return ctx;
}

// ── Provider ─────────────────────────────────────────

export function ToastProvider({ children }: { children: React.ReactNode }) {
    const [toasts, setToasts] = useState<Toast[]>([]);
    const [history, setHistory] = useState<ToastHistoryItem[]>([]);
    const counterRef = useRef(0);

    const removeToast = useCallback((id: string) => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
    }, []);

    const addToast = useCallback(
        (type: ToastType, message: string) => {
            const id = `toast-${++counterRef.current}`;
            setToasts((prev) => [...prev, { id, type, message }]);

            setHistory((prev) => {
                const newHistory = [{ id, type, message, timestamp: new Date(), read: false }, ...prev];
                return newHistory.slice(0, 50);
            });

            setTimeout(() => removeToast(id), 4000);
        },
        [removeToast],
    );

    const markAllRead = useCallback(() => {
        setHistory((prev) => prev.map((item) => ({ ...item, read: true })));
    }, []);

    const clearHistory = useCallback(() => {
        setHistory([]);
    }, []);

    const value: ToastContextValue = {
        toast: addToast,
        success: useCallback((m: string) => addToast("success", m), [addToast]),
        error: useCallback((m: string) => addToast("error", m), [addToast]),
        warning: useCallback((m: string) => addToast("warning", m), [addToast]),
        history,
        markAllRead,
        clearHistory,
    };

    return (
        <ToastContext.Provider value={value}>
            {children}
            {/* 토스트 컨테이너 */}
            <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none">
                {toasts.map((t) => (
                    <ToastItem key={t.id} toast={t} onClose={() => removeToast(t.id)} />
                ))}
            </div>
        </ToastContext.Provider>
    );
}

// ── Toast Item ───────────────────────────────────────

const iconMap = {
    success: CheckCircle,
    error: AlertCircle,
    warning: AlertTriangle,
};

const colorMap = {
    success: "border-ok/30 bg-ok/10 text-ok",
    error: "border-danger/30 bg-danger/10 text-danger",
    warning: "border-warn/30 bg-warn/10 text-warn",
};

function ToastItem({ toast, onClose }: { toast: Toast; onClose: () => void }) {
    const Icon = iconMap[toast.type];

    return (
        <div
            className={clsx(
                "pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-[var(--radius-card)] border backdrop-blur-xl shadow-lg",
                "min-w-[280px] max-w-[420px] animate-slide-in",
                colorMap[toast.type],
            )}
        >
            <Icon className="w-5 h-5 shrink-0" />
            <span className="flex-1 text-sm font-medium">{toast.message}</span>
            <button
                onClick={onClose}
                className="shrink-0 p-0.5 rounded hover:bg-white/10 transition-colors"
            >
                <X className="w-4 h-4" />
            </button>
        </div>
    );
}
