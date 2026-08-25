import { LayoutGrid, List, RefreshCw, Square } from "lucide-react";
import { TagManager } from "../ui/TagManager";
import { Button } from "../ui/primitives";

export type StatusFilter = "all" | "recording" | "live" | "offline";
export type ViewMode = "grid" | "list";

const FILTERS: { value: StatusFilter; label: string; selectedClass: string }[] = [
    { value: "all", label: "전체", selectedClass: "text-ink" },
    { value: "recording", label: "녹화 중", selectedClass: "text-ok" },
    { value: "live", label: "라이브", selectedClass: "text-live" },
    { value: "offline", label: "오프라인", selectedClass: "text-ink-muted" },
];

interface Props {
    filter: StatusFilter;
    onFilterChange: (filter: StatusFilter) => void;
    globalTags: string[];
    selectedTags: string[];
    onSelectedTagsChange: (tags: string[]) => void;
    onCreateTag: (tag: string) => void;
    viewMode: ViewMode;
    onViewModeChange: (mode: ViewMode) => void;
    recordingCount: number;
    onScanNow: () => void;
    onStopAll: () => void;
}

export function DashboardFilters({
    filter,
    onFilterChange,
    globalTags,
    selectedTags,
    onSelectedTagsChange,
    onCreateTag,
    viewMode,
    onViewModeChange,
    recordingCount,
    onScanNow,
    onStopAll,
}: Props) {
    return (
        <div className="flex flex-col gap-3 border-b border-line pb-4">
            <div className="flex items-center justify-between gap-3 overflow-x-auto">
                <div className="flex gap-2">
                    {FILTERS.map((option) => (
                        <button
                            key={option.value}
                            onClick={() => onFilterChange(option.value)}
                            className={`px-3 py-1.5 rounded-[var(--radius-control)] text-sm font-medium transition-colors whitespace-nowrap ${filter === option.value ? `bg-surface-4 ${option.selectedClass}` : "text-ink-faint hover:bg-surface-3 hover:text-ink-muted"}`}
                        >
                            {option.label}
                        </button>
                    ))}
                </div>

                <div className="flex gap-2 shrink-0">
                    <Button icon={RefreshCw} onClick={onScanNow} className="px-3 py-1.5">즉시 스캔</Button>
                    <Button variant="danger" icon={Square} onClick={onStopAll} disabled={recordingCount === 0} className="px-3 py-1.5">전체 중지</Button>
                    <div className="flex bg-surface-2 border border-line rounded-[var(--radius-control)] p-1">
                        <button
                            type="button"
                            onClick={() => onViewModeChange("grid")}
                            className={`p-1.5 rounded-md transition-colors ${viewMode === "grid" ? "bg-surface-4 text-ink" : "text-ink-faint hover:text-ink"}`}
                            title="그리드 뷰"
                        >
                            <LayoutGrid className="w-4 h-4" />
                        </button>
                        <button
                            type="button"
                            onClick={() => onViewModeChange("list")}
                            className={`p-1.5 rounded-md transition-colors ${viewMode === "list" ? "bg-surface-4 text-ink" : "text-ink-faint hover:text-ink"}`}
                            title="리스트 뷰"
                        >
                            <List className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            </div>

            <div className="flex items-center">
                <span className="text-xs font-semibold text-ink-faint mr-3 shrink-0">태그 필터</span>
                <TagManager
                    availableTags={globalTags}
                    selectedTags={selectedTags}
                    onAddTag={(tag) => onSelectedTagsChange([...selectedTags, tag])}
                    onRemoveTag={(tag) => onSelectedTagsChange(selectedTags.filter((item) => item !== tag))}
                    onCreateTag={onCreateTag}
                />
            </div>
        </div>
    );
}
