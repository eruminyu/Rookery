import { useState, useEffect } from "react";
import {
    FolderOpen, Shield, CheckCircle2,
    ChevronRight, ChevronLeft, Loader2, Eye, EyeOff,
} from "lucide-react";
import { DirInput } from "./ui/DirInput";

// ── Types ─────────────────────────────────────────────

interface SetupWizardProps {
    onComplete: () => void;
    isDocker?: boolean;
}

type Step = 1 | 2 | 3;

interface FormData {
    download_dir: string;
    output_format: string;
    recording_quality: string;
    nid_aut: string;
    nid_ses: string;
}

// ── API ──────────────────────────────────────────────

async function completeSetup(data: FormData): Promise<void> {
    const res = await fetch("/api/setup/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            download_dir: data.download_dir,
            output_format: data.output_format,
            recording_quality: data.recording_quality,
            nid_aut: data.nid_aut || null,
            nid_ses: data.nid_ses || null,
        }),
    });
    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "설정 저장 실패");
    }
}

// ── Step 인디케이터 ──────────────────────────────────

function StepIndicator({ current, total }: { current: Step; total: number }) {
    return (
        <div className="flex items-center gap-2 mb-8">
            {Array.from({ length: total }, (_, i) => i + 1).map((n) => (
                <div key={n} className="flex items-center gap-2">
                    <div
                        className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300 ${n < current
                            ? "bg-[#00FFA3] text-black"
                            : n === current
                                ? "bg-[#00FFA3]/20 border-2 border-[#00FFA3] text-[#00FFA3]"
                                : "bg-zinc-800 border border-zinc-700 text-zinc-500"
                            }`}
                    >
                        {n < current ? <CheckCircle2 className="w-4 h-4" /> : n}
                    </div>
                    {n < total && (
                        <div
                            className={`h-0.5 w-8 rounded transition-all duration-300 ${n < current ? "bg-[#00FFA3]" : "bg-zinc-700"
                                }`}
                        />
                    )}
                </div>
            ))}
        </div>
    );
}

// ── Step 1: 기본 설정 ────────────────────────────────

function Step1({ data, onChange, isDocker }: { data: FormData; onChange: (k: keyof FormData, v: string) => void; isDocker?: boolean }) {
    const qualities = ["best", "1080p", "720p", "480p"];
    const formats = ["ts", "mp4", "mkv"];

    return (
        <div className="space-y-6">
            {/* 저장 경로 */}
            <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">
                    <FolderOpen className="inline w-4 h-4 mr-1 text-[#00FFA3]" />
                    녹화 저장 경로 <span className="text-red-400">*</span>
                </label>
                {isDocker ? (
                    <div className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm text-zinc-500 font-mono cursor-not-allowed select-none">
                        /app/backend/recordings
                    </div>
                ) : (
                    <DirInput
                        value={data.download_dir}
                        onChange={(val) => onChange("download_dir", val)}
                        placeholder="예: C:\Recordings 또는 /home/user/recordings"
                    />
                )}
                <p className="text-xs text-zinc-500 mt-1.5 flex items-start gap-1">
                    {isDocker ? (
                        <>
                            <span className="text-yellow-400">⚠️</span>
                            <span>Docker 환경에서는 저장 경로를 <b className="text-zinc-300">docker-compose.yml</b>의 볼륨 설정으로 지정하세요.<br />
                            <span className="font-mono text-zinc-400">- /your/path:/app/backend/recordings</span></span>
                        </>
                    ) : (
                        "경로가 없으면 자동으로 생성됩니다."
                    )}
                </p>
            </div>

            {/* 녹화 품질 */}
            <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">녹화 품질</label>
                <div className="grid grid-cols-4 gap-2">
                    {qualities.map((q) => (
                        <button
                            key={q}
                            type="button"
                            onClick={() => onChange("recording_quality", q)}
                            className={`py-2 rounded-lg text-sm font-medium border transition-all ${data.recording_quality === q
                                ? "bg-[#00FFA3]/10 border-[#00FFA3] text-[#00FFA3]"
                                : "bg-zinc-800 border-zinc-700 text-zinc-400 hover:border-zinc-500"
                                }`}
                        >
                            {q}
                        </button>
                    ))}
                </div>
            </div>

            {/* 출력 포맷 */}
            <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">출력 포맷</label>
                <div className="grid grid-cols-3 gap-2">
                    {formats.map((f) => (
                        <button
                            key={f}
                            type="button"
                            onClick={() => onChange("output_format", f)}
                            className={`py-2 rounded-lg text-sm font-medium border transition-all ${data.output_format === f
                                ? "bg-[#00FFA3]/10 border-[#00FFA3] text-[#00FFA3]"
                                : "bg-zinc-800 border-zinc-700 text-zinc-400 hover:border-zinc-500"
                                }`}
                        >
                            .{f.toUpperCase()}
                        </button>
                    ))}
                </div>
                <p className="text-xs text-zinc-500 mt-1.5">
                    TS: 녹화 안정성 최우선 · MP4/MKV: 즉시 재생 가능
                </p>
            </div>
        </div>
    );
}

// ── Step 2: 치지직 인증 쿠키 ─────────────────────────

function Step2({ data, onChange }: { data: FormData; onChange: (k: keyof FormData, v: string) => void }) {
    const [showAut, setShowAut] = useState(false);
    const [showSes, setShowSes] = useState(false);

    return (
        <div className="space-y-5">
            <div className="bg-zinc-800/50 border border-zinc-700 rounded-xl p-4 text-sm text-zinc-400 leading-relaxed">
                <Shield className="inline w-4 h-4 mr-1 text-[#00FFA3]" />
                치지직 로그인 쿠키를 등록하면 <span className="text-white font-medium">성인 방송 녹화</span>와{" "}
                <span className="text-white font-medium">1080p 고화질</span>에 접근할 수 있습니다.
                <br />
                <span className="text-zinc-500 text-xs mt-1 block">
                    브라우저 개발자 도구 (F12) → Application → Cookies → naver.com에서 확인할 수 있습니다.
                    이 단계는 건너뛸 수 있으며 나중에 설정 페이지에서 변경 가능합니다.
                </span>
            </div>

            {/* NID_AUT */}
            <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">NID_AUT</label>
                <div className="relative">
                    <input
                        type={showAut ? "text" : "password"}
                        value={data.nid_aut}
                        onChange={(e) => onChange("nid_aut", e.target.value)}
                        placeholder="NID_AUT 쿠키 값"
                        className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2.5 pr-10 text-sm text-white placeholder-zinc-500 font-mono focus:outline-none focus:border-[#00FFA3] transition-colors"
                    />
                    <button
                        type="button"
                        onClick={() => setShowAut((v) => !v)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                    >
                        {showAut ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                </div>
            </div>

            {/* NID_SES */}
            <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">NID_SES</label>
                <div className="relative">
                    <input
                        type={showSes ? "text" : "password"}
                        value={data.nid_ses}
                        onChange={(e) => onChange("nid_ses", e.target.value)}
                        placeholder="NID_SES 쿠키 값"
                        className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2.5 pr-10 text-sm text-white placeholder-zinc-500 font-mono focus:outline-none focus:border-[#00FFA3] transition-colors"
                    />
                    <button
                        type="button"
                        onClick={() => setShowSes((v) => !v)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                    >
                        {showSes ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                </div>
            </div>
        </div>
    );
}

// ── Step 3: 확인 및 완료 ─────────────────────────────

function Step3({ data }: { data: FormData }) {
    const rows: { label: string; value: string }[] = [
        { label: "저장 경로", value: data.download_dir || "(미설정)" },
        { label: "녹화 품질", value: data.recording_quality },
        { label: "출력 포맷", value: `.${data.output_format.toUpperCase()}` },
        { label: "치지직 인증", value: data.nid_aut && data.nid_ses ? "✅ 설정됨" : "⏭️ 건너뜀 (나중에 설정 가능)" },
    ];

    return (
        <div className="space-y-4">
            <div className="bg-zinc-800/50 border border-zinc-700 rounded-xl overflow-hidden">
                {rows.map((row, i) => (
                    <div
                        key={row.label}
                        className={`flex items-center justify-between px-4 py-3 text-sm ${i < rows.length - 1 ? "border-b border-zinc-700/50" : ""
                            }`}
                    >
                        <span className="text-zinc-400">{row.label}</span>
                        <span className="text-white font-medium text-right max-w-[60%] truncate">{row.value}</span>
                    </div>
                ))}
            </div>
            <p className="text-xs text-zinc-500 text-center">
                모든 설정은 나중에 <span className="text-zinc-300">설정 페이지</span>에서 변경할 수 있습니다.
            </p>
        </div>
    );
}

// ── Main SetupWizard ─────────────────────────────────

export function SetupWizard({ onComplete, isDocker = false }: SetupWizardProps) {
    const [step, setStep] = useState<Step>(1);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [data, setData] = useState<FormData>({
        download_dir: isDocker ? "/app/recordings" : "",
        output_format: "ts",
        recording_quality: "best",
        nid_aut: "",
        nid_ses: "",
    });

    const onChange = (k: keyof FormData, v: string) =>
        setData((prev) => ({ ...prev, [k]: v }));

    const canNext = step === 1 ? (isDocker || data.download_dir.trim().length > 0) : true;

    const handleNext = () => {
        if (step < 3) setStep((s) => (s + 1) as Step);
    };

    const handleBack = () => {
        if (step > 1) setStep((s) => (s - 1) as Step);
    };

    const handleSave = async () => {
        setSaving(true);
        setError(null);
        try {
            await completeSetup(data);
            onComplete();
        } catch (e) {
            setError(e instanceof Error ? e.message : "알 수 없는 오류");
        } finally {
            setSaving(false);
        }
    };

    const stepTitles: Record<Step, { title: string; subtitle: string }> = {
        1: { title: "기본 설정", subtitle: "녹화 파일이 저장될 경로와 기본 품질을 설정하세요." },
        2: { title: "치지직 인증 쿠키 (선택)", subtitle: "성인 방송 및 1080p 녹화를 위한 로그인 쿠키를 입력하세요." },
        3: { title: "설정 확인", subtitle: "아래 내용을 확인하고 완료 버튼을 누르세요." },
    };

    return (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center animate-backdrop">
            {/* 배경 블러 */}
            <div className="absolute inset-0 bg-black/80 backdrop-blur-md" />

            {/* 카드 */}
            <div className="relative bg-[#1B1D24] border border-zinc-700/80 rounded-2xl shadow-2xl w-full max-w-lg mx-4 animate-modal-in overflow-hidden">
                {/* 상단 그라데이션 바 */}
                <div className="h-1 w-full bg-gradient-to-r from-[#00FFA3] via-[#00D689] to-emerald-400" />

                <div className="p-8">
                    {/* 헤더 */}
                    <div className="mb-6">
                        <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-semibold text-[#00FFA3] uppercase tracking-widest">
                                Signal-Recorder
                            </span>
                        </div>
                        <h2 className="text-2xl font-bold text-white">
                            {stepTitles[step].title}
                        </h2>
                        <p className="text-sm text-zinc-400 mt-1">{stepTitles[step].subtitle}</p>
                    </div>

                    {/* Step 인디케이터 */}
                    <StepIndicator current={step} total={3} />

                    {/* Step 콘텐츠 */}
                    <div className="min-h-[240px]">
                        {step === 1 && <Step1 data={data} onChange={onChange} />}
                        {step === 2 && <Step2 data={data} onChange={onChange} />}
                        {step === 3 && <Step3 data={data} />}
                    </div>

                    {/* 에러 */}
                    {error && (
                        <p className="mt-4 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2">
                            {error}
                        </p>
                    )}

                    {/* 버튼 */}
                    <div className="flex items-center justify-between mt-8">
                        <button
                            type="button"
                            onClick={handleBack}
                            disabled={step === 1}
                            className="flex items-center gap-1 px-4 py-2 rounded-lg text-sm font-medium text-zinc-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                        >
                            <ChevronLeft className="w-4 h-4" />
                            이전
                        </button>

                        {step < 3 ? (
                            <button
                                type="button"
                                onClick={handleNext}
                                disabled={!canNext}
                                className="flex items-center gap-1.5 px-6 py-2.5 rounded-xl text-sm font-bold bg-[#00FFA3] text-black hover:bg-[#00D689] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                            >
                                {step === 2 && !data.nid_aut ? "건너뛰기" : "다음"}
                                <ChevronRight className="w-4 h-4" />
                            </button>
                        ) : (
                            <button
                                type="button"
                                onClick={handleSave}
                                disabled={saving}
                                className="flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-bold bg-[#00FFA3] text-black hover:bg-[#00D689] disabled:opacity-60 transition-all"
                            >
                                {saving ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                    <CheckCircle2 className="w-4 h-4" />
                                )}
                                {saving ? "저장 중..." : "설정 완료"}
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
