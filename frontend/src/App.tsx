import { useState, useEffect } from "react";
import { createBrowserRouter, RouterProvider, Outlet } from "react-router-dom";
import { Layout } from "./components/layout/Layout";
import { ToastProvider } from "./components/ui/Toast";
import { ConfirmProvider } from "./components/ui/ConfirmModal";
import { SetupWizard } from "./components/SetupWizard";
import { ThemeProvider } from "./context/ThemeContext";
import Dashboard from "./pages/Dashboard";
import VodDownload from "./pages/VodDownload";
import ArchivePage from "./pages/Archive";
import Settings from "./pages/Settings";
import ChatLogs from "./pages/ChatLogs";
import Stats from "./pages/Stats";
import SystemLogs from "./pages/SystemLogs";
import { CommandPalette } from "./components/ui/CommandPalette";

// Data Router 환경 안에서 렌더링되는 루트 레이아웃.
// SetupWizard 오버레이와 CommandPalette를 포함하며,
// 하위 라우트(<Layout />)는 <Outlet />으로 렌더링된다.
function RootLayout() {
    const [setupState, setSetupState] = useState<{ needsSetup: boolean; isDocker: boolean } | null>(null);

    useEffect(() => {
        fetch("/api/setup/status")
            .then((r) => r.json())
            .then((data) => setSetupState({ needsSetup: data.needs_setup, isDocker: data.is_docker }))
            .catch(() => setSetupState({ needsSetup: false, isDocker: false }));
    }, []);

    if (setupState === null) {
        return (
            <div className="fixed inset-0 flex items-center justify-center bg-chzzk-bg">
                <div className="w-8 h-8 border-2 border-chzzk border-t-transparent rounded-full animate-spin" />
            </div>
        );
    }

    return (
        <>
            {setupState.needsSetup && (
                <SetupWizard
                    onComplete={() => setSetupState((prev) => (prev ? { ...prev, needsSetup: false } : null))}
                    isDocker={setupState.isDocker}
                />
            )}
            <CommandPalette />
            <Outlet />
        </>
    );
}

const router = createBrowserRouter([
    {
        path: "/",
        element: <RootLayout />,
        children: [
            {
                element: <Layout />,
                children: [
                    { index: true, element: <Dashboard /> },
                    { path: "vod", element: <VodDownload /> },
                    { path: "archive", element: <ArchivePage /> },
                    { path: "chat", element: <ChatLogs /> },
                    { path: "stats", element: <Stats /> },
                    { path: "settings", element: <Settings /> },
                    { path: "system-logs", element: <SystemLogs /> },
                ],
            },
        ],
    },
]);

function App() {
    return (
        <ThemeProvider>
            <ToastProvider>
                <ConfirmProvider>
                    <RouterProvider router={router} />
                </ConfirmProvider>
            </ToastProvider>
        </ThemeProvider>
    );
}

export default App;
