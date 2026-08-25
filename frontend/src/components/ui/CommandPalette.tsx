import { useEffect, useState } from "react";
import { Command } from "cmdk";
import { useNavigate } from "react-router-dom";
import { LayoutDashboard, Download, Settings, MessageSquare, Radio, BarChart2 } from "lucide-react";

export function CommandPalette() {
    const [open, setOpen] = useState(false);
    const navigate = useNavigate();

    // 토글 단축키: Ctrl+K 또는 Cmd+K
    useEffect(() => {
        const down = (e: KeyboardEvent) => {
            if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                setOpen((open) => !open);
            }
        };

        document.addEventListener("keydown", down);
        return () => document.removeEventListener("keydown", down);
    }, []);

    const runCommand = (command: () => void) => {
        setOpen(false);
        command();
    };

    if (!open) return null;

    return (
        <Command.Dialog
            open={open}
            onOpenChange={setOpen}
            className="fixed inset-0 z-[100] flex items-start justify-center pt-[18vh] bg-surface-0/75 backdrop-blur-md"
            label="Global Command Palette"
        >
            <div className="w-[calc(100%-2rem)] max-w-lg bg-surface-2 border border-line-strong shadow-[var(--shadow-pop)] rounded-[calc(var(--radius-card)+4px)] overflow-hidden pointer-events-auto">
                <Command.Input
                    placeholder="검색하거나 명령어를 입력하세요..."
                    className="w-full px-5 py-4 bg-transparent text-ink placeholder:text-ink-faint border-b border-line focus:outline-none focus:ring-0"
                />
                
                <Command.List className="max-h-[320px] overflow-y-auto p-2">
                    <Command.Empty className="py-6 text-center text-sm text-ink-faint">
                        검색 결과가 없습니다.
                    </Command.Empty>
                    
                    <Command.Group heading="이동 (Navigation)" className="px-2 py-1.5 text-xs font-semibold text-ink-faint">
                        <Command.Item
                            onSelect={() => runCommand(() => navigate("/"))}
                            className="flex items-center gap-2 px-3 py-2.5 mt-1 text-sm text-ink-muted rounded-[var(--radius-control)] cursor-pointer hover:bg-surface-3 aria-selected:bg-surface-3 aria-selected:text-ink transition-colors"
                        >
                            <LayoutDashboard className="w-4 h-4" /> Live Dashboard
                        </Command.Item>
                        <Command.Item
                            onSelect={() => runCommand(() => navigate("/vod"))}
                            className="flex items-center gap-2 px-3 py-2.5 mt-1 text-sm text-ink-muted rounded-[var(--radius-control)] cursor-pointer hover:bg-surface-3 aria-selected:bg-surface-3 aria-selected:text-ink transition-colors"
                        >
                            <Download className="w-4 h-4" /> VOD Download
                        </Command.Item>
                        <Command.Item
                            onSelect={() => runCommand(() => navigate("/archive"))}
                            className="flex items-center gap-2 px-3 py-2.5 mt-1 text-sm text-ink-muted rounded-[var(--radius-control)] cursor-pointer hover:bg-surface-3 aria-selected:bg-surface-3 aria-selected:text-ink transition-colors"
                        >
                            <Radio className="w-4 h-4" /> X Spaces
                        </Command.Item>
                        <Command.Item
                            onSelect={() => runCommand(() => navigate("/chat"))}
                            className="flex items-center gap-2 px-3 py-2.5 mt-1 text-sm text-ink-muted rounded-[var(--radius-control)] cursor-pointer hover:bg-surface-3 aria-selected:bg-surface-3 aria-selected:text-ink transition-colors"
                        >
                            <MessageSquare className="w-4 h-4" /> Chat Logs
                        </Command.Item>
                        <Command.Item
                            onSelect={() => runCommand(() => navigate("/stats"))}
                            className="flex items-center gap-2 px-3 py-2.5 mt-1 text-sm text-ink-muted rounded-[var(--radius-control)] cursor-pointer hover:bg-surface-3 aria-selected:bg-surface-3 aria-selected:text-ink transition-colors"
                        >
                            <BarChart2 className="w-4 h-4" /> Stats
                        </Command.Item>
                        <Command.Item
                            onSelect={() => runCommand(() => navigate("/settings"))}
                            className="flex items-center gap-2 px-3 py-2.5 mt-1 text-sm text-ink-muted rounded-[var(--radius-control)] cursor-pointer hover:bg-surface-3 aria-selected:bg-surface-3 aria-selected:text-ink transition-colors"
                        >
                            <Settings className="w-4 h-4" /> Settings
                        </Command.Item>
                    </Command.Group>
                </Command.List>
            </div>
        </Command.Dialog>
    );
}
