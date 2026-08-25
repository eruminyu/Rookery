/**
 * 알림 설정 탭.
 *
 * 백엔드 알림 파이프라인(큐 + 재시도 + 웹훅 폴백 + 종류별 필터)을
 * 화면에서 전부 제어한다. 이전에는 Bot 토큰과 채널 ID만 입력할 수 있어
 * 나머지는 .env를 직접 고쳐야 했다.
 */
import { useCallback, useEffect, useState } from "react";
import {
    Activity,
    AtSign,
    Bell,
    BellRing,
    Bot,
    CheckCircle2,
    RefreshCcw,
    Save,
    Send,
    Webhook,
} from "lucide-react";
import {
    api,
    type NotificationKindInfo,
    type NotificationStatus,
    type Settings as SettingsType,
} from "../../api/client";
import { useToast } from "../ui/Toast";
import { getErrorMessage } from "../../utils/error";
import {
    Badge,
    Button,
    Card,
    CardHeader,
    Divider,
    Field,
    Input,
    SettingRow,
    StatusDot,
    Switch,
} from "../ui/primitives";

/** 멘션 대상 프리셋. 역할 멘션은 직접 입력한다. */
const MENTION_PRESETS = [
    { value: "@here", label: "@here — 접속 중인 사람만" },
    { value: "@everyone", label: "@everyone — 서버 전체" },
];

/** 전송 채널 이름을 사람이 읽을 문구로. */
const TRANSPORT_LABELS: Record<string, string> = {
    discord_bot: "Discord Bot",
    webhook: "Webhook",
};

interface Props {
    settings: SettingsType | null;
    /** 저장 후 상위의 설정 상태를 갱신한다. */
    onSaved: () => void;
    /** 변경사항 유무를 상위 탭 전환 경고에 알린다. */
    onDirtyChange?: (dirty: boolean) => void;
}

export function NotificationsTab({ settings, onSaved, onDirtyChange }: Props) {
    const toast = useToast();

    // ── 폼 상태 ──────────────────────────────────────
    const [botToken, setBotToken] = useState("");
    const [channelId, setChannelId] = useState("");
    const [webhookUrl, setWebhookUrl] = useState("");
    const [enabledKinds, setEnabledKinds] = useState<Set<string>>(new Set());
    const [mentionKinds, setMentionKinds] = useState<Set<string>>(new Set());
    const [mentionTarget, setMentionTarget] = useState("@here");
    const [ttlMinutes, setTtlMinutes] = useState(60);

    const [saving, setSaving] = useState(false);
    const [testing, setTesting] = useState(false);
    const [status, setStatus] = useState<NotificationStatus | null>(null);
    const [dirty, setDirty] = useState(false);

    const kinds: NotificationKindInfo[] = settings?.notification_kinds ?? [];

    // ── 서버 값으로 폼 초기화 ────────────────────────
    useEffect(() => {
        if (!settings) return;

        const allValues = (settings.notification_kinds ?? []).map((k) => k.value);
        const notify = settings.discord_notify_events ?? ["all"];
        // "all"은 전체 선택으로 펼쳐서 체크박스에 반영한다.
        setEnabledKinds(
            new Set(notify.includes("all") ? allValues : notify.filter((v) => v !== "none")),
        );
        setMentionKinds(new Set(settings.discord_mention_events ?? []));
        setMentionTarget(settings.discord_mention_target || "@here");
        setTtlMinutes(Math.round((settings.discord_notify_ttl ?? 3600) / 60));
        setDirty(false);
    }, [settings]);

    const markDirty = useCallback(() => {
        setDirty(true);
        onDirtyChange?.(true);
    }, [onDirtyChange]);

    // ── 파이프라인 상태 조회 ─────────────────────────
    const refreshStatus = useCallback(async () => {
        try {
            setStatus(await api.getNotificationStatus());
        } catch {
            setStatus({ available: false, reason: "상태를 불러오지 못했습니다." });
        }
    }, []);

    useEffect(() => {
        refreshStatus();
        // 큐가 비워지는 걸 볼 수 있도록 주기적으로 갱신한다.
        const timer = setInterval(refreshStatus, 5000);
        return () => clearInterval(timer);
    }, [refreshStatus]);

    // ── 핸들러 ───────────────────────────────────────
    const toggleKind = (value: string, set: Set<string>, apply: (s: Set<string>) => void) => {
        const next = new Set(set);
        next.has(value) ? next.delete(value) : next.add(value);
        apply(next);
        markDirty();
    };

    const handleSave = async () => {
        setSaving(true);
        try {
            const allSelected = kinds.length > 0 && enabledKinds.size === kinds.length;
            await api.updateDiscordSettings({
                // 토큰과 웹훅 URL은 입력했을 때만 보낸다 (빈 값으로 덮어쓰지 않도록).
                ...(botToken.trim() ? { discord_bot_token: botToken.trim() } : {}),
                ...(webhookUrl.trim() ? { discord_webhook_url: webhookUrl.trim() } : {}),
                discord_notification_channel_id: channelId.trim() || undefined,
                discord_notify_events: allSelected ? ["all"] : [...enabledKinds],
                discord_mention_events: [...mentionKinds],
                discord_mention_target: mentionTarget,
                discord_notify_ttl: Math.max(60, ttlMinutes * 60),
            });
            setBotToken("");
            setWebhookUrl("");
            setDirty(false);
            onDirtyChange?.(false);
            toast.success("알림 설정을 저장했습니다.");
            onSaved();
            refreshStatus();
        } catch (e) {
            toast.error(getErrorMessage(e, "알림 설정 저장에 실패했습니다."));
        } finally {
            setSaving(false);
        }
    };

    const handleTest = async () => {
        setTesting(true);
        try {
            const res = await api.sendTestNotification();
            toast.success(res.message);
            refreshStatus();
        } catch (e) {
            toast.error(getErrorMessage(e, "테스트 알림 전송에 실패했습니다."));
        } finally {
            setTesting(false);
        }
    };

    const botReady = settings?.discord_bot_configured && !!settings?.discord_notification_channel_id;
    const anyTransport = botReady || settings?.discord_webhook_configured;

    return (
        <div className="space-y-5">
            {/* ══ 연결 상태 ══════════════════════════════ */}
            <Card>
                <CardHeader
                    icon={Activity}
                    title="연결 상태"
                    description="알림이 실제로 나가고 있는지 여기서 확인합니다."
                    action={
                        <div className="flex items-center gap-2">
                            <Button
                                variant="ghost"
                                icon={RefreshCcw}
                                onClick={refreshStatus}
                                aria-label="상태 새로고침"
                            />
                            <Button
                                variant="primary"
                                icon={Send}
                                loading={testing}
                                disabled={!anyTransport}
                                onClick={handleTest}
                            >
                                테스트 발송
                            </Button>
                        </div>
                    }
                />

                {!anyTransport && (
                    <p className="text-[13px] text-warn bg-warn/10 border border-warn/20 rounded-[var(--radius-control)] px-3 py-2.5 mb-4">
                        Bot 토큰 + 채널 ID 또는 Webhook URL 중 하나는 설정해야 알림이 전송됩니다.
                    </p>
                )}

                <div className="grid gap-3 sm:grid-cols-2">
                    {(status?.transports ?? []).map((t) => (
                        <div
                            key={t.name}
                            className="flex items-center justify-between gap-3 bg-surface-3 border border-line rounded-[var(--radius-control)] px-3.5 py-3"
                        >
                            <span className="text-[13px] font-medium text-ink">
                                {TRANSPORT_LABELS[t.name] ?? t.name}
                            </span>
                            {!t.configured ? (
                                <Badge tone="neutral">미설정</Badge>
                            ) : t.available ? (
                                <Badge tone="ok">
                                    <CheckCircle2 className="w-3 h-3" />
                                    연결됨
                                </Badge>
                            ) : (
                                <Badge tone="warn">대기 중</Badge>
                            )}
                        </div>
                    ))}
                </div>

                {status?.available && (
                    <>
                        <Divider className="my-4" />
                        <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                            {[
                                { label: "대기", value: status.pending ?? 0, tone: (status.pending ?? 0) > 0 ? "warn" : undefined },
                                { label: "전송됨", value: status.delivered ?? 0 },
                                { label: "폐기", value: status.dropped ?? 0, tone: (status.dropped ?? 0) > 0 ? "danger" : undefined },
                                { label: "만료", value: status.expired ?? 0 },
                            ].map((s) => (
                                <div key={s.label}>
                                    <dt className="text-[11px] uppercase tracking-wide text-ink-faint">
                                        {s.label}
                                    </dt>
                                    <dd
                                        className="text-lg font-semibold mt-0.5"
                                        style={{
                                            color:
                                                s.tone === "danger" ? "var(--color-danger)"
                                                : s.tone === "warn" ? "var(--color-warn)"
                                                : "var(--color-ink)",
                                        }}
                                    >
                                        {s.value}
                                    </dd>
                                </div>
                            ))}
                        </dl>
                        <p className="text-xs text-ink-faint mt-3 leading-relaxed">
                            대기 중인 알림은 연결이 복구되면 자동으로 전송됩니다. 앱을 재시작해도 유지됩니다.
                        </p>
                    </>
                )}
            </Card>

            {/* ══ Discord Bot ═══════════════════════════ */}
            <Card>
                <CardHeader
                    icon={Bot}
                    title="Discord Bot"
                    description="원격에서 녹화를 제어하고 알림을 받습니다."
                    action={
                        <StatusDot
                            active={!!botReady}
                            label={botReady ? "설정됨" : "미설정"}
                            tone={botReady ? "ok" : "warn"}
                        />
                    }
                />

                <div className="space-y-4">
                    <Field
                        label="Bot 토큰"
                        htmlFor="bot-token"
                        hint="비워두면 기존 토큰을 유지합니다. Discord Developer Portal에서 발급받으세요. 토큰 변경은 재시작 후 적용됩니다."
                    >
                        <Input
                            id="bot-token"
                            type="password"
                            autoComplete="off"
                            value={botToken}
                            onChange={(e) => {
                                setBotToken(e.target.value);
                                markDirty();
                            }}
                            placeholder={settings?.discord_bot_configured ? "설정됨 — 변경하려면 입력" : "Bot 토큰"}
                        />
                    </Field>

                    <Field
                        label="알림 채널 ID"
                        htmlFor="channel-id"
                        hint="Discord에서 개발자 모드를 켠 뒤 채널 우클릭 → 'ID 복사'로 얻은 숫자입니다."
                    >
                        <Input
                            id="channel-id"
                            inputMode="numeric"
                            value={channelId || settings?.discord_notification_channel_id || ""}
                            onChange={(e) => {
                                setChannelId(e.target.value);
                                markDirty();
                            }}
                            placeholder="예: 1234567890123456789"
                        />
                    </Field>
                </div>
            </Card>

            {/* ══ Webhook 폴백 ══════════════════════════ */}
            <Card>
                <CardHeader
                    icon={Webhook}
                    title="Webhook 폴백"
                    description="Bot 연결이 끊겨도 이 경로로 알림이 전달됩니다."
                    action={
                        <StatusDot
                            active={!!settings?.discord_webhook_configured}
                            label={settings?.discord_webhook_configured ? "설정됨" : "미설정"}
                            tone={settings?.discord_webhook_configured ? "ok" : "warn"}
                        />
                    }
                />

                <Field
                    label="Webhook URL"
                    htmlFor="webhook-url"
                    hint="Discord 채널 설정 → 연동 → 웹후크에서 만듭니다. Bot 없이 이것만 설정해도 알림은 정상 동작합니다."
                >
                    <Input
                        id="webhook-url"
                        type="password"
                        autoComplete="off"
                        value={webhookUrl}
                        onChange={(e) => {
                            setWebhookUrl(e.target.value);
                            markDirty();
                        }}
                        placeholder={
                            settings?.discord_webhook_configured
                                ? "설정됨 — 변경하려면 입력"
                                : "https://discord.com/api/webhooks/..."
                        }
                    />
                </Field>
            </Card>

            {/* ══ 알림 종류 ═════════════════════════════ */}
            <Card>
                <CardHeader
                    icon={Bell}
                    title="받을 알림"
                    description="꺼둔 종류는 아예 전송되지 않습니다."
                    action={
                        <div className="flex gap-2">
                            <Button
                                variant="ghost"
                                className="px-3 py-1.5 text-[13px]"
                                onClick={() => {
                                    setEnabledKinds(new Set(kinds.map((k) => k.value)));
                                    markDirty();
                                }}
                            >
                                전체 선택
                            </Button>
                            <Button
                                variant="ghost"
                                className="px-3 py-1.5 text-[13px]"
                                onClick={() => {
                                    setEnabledKinds(new Set());
                                    markDirty();
                                }}
                            >
                                전체 해제
                            </Button>
                        </div>
                    }
                />

                <div className="divide-y divide-line">
                    {kinds.map((kind) => (
                        <SettingRow
                            key={kind.value}
                            label={kind.label}
                            control={
                                <Switch
                                    label={kind.label}
                                    checked={enabledKinds.has(kind.value)}
                                    onChange={() =>
                                        toggleKind(kind.value, enabledKinds, setEnabledKinds)
                                    }
                                />
                            }
                        />
                    ))}
                </div>
            </Card>

            {/* ══ 멘션 ══════════════════════════════════ */}
            <Card>
                <CardHeader
                    icon={AtSign}
                    title="멘션"
                    description="놓치면 안 되는 알림에만 멘션을 붙이세요."
                />

                <div className="space-y-4">
                    <Field
                        label="멘션 대상"
                        htmlFor="mention-target"
                        hint="역할을 멘션하려면 <@&역할ID> 형식으로 직접 입력합니다."
                    >
                        <div className="flex flex-wrap gap-2 mb-2">
                            {MENTION_PRESETS.map((p) => (
                                <button
                                    key={p.value}
                                    type="button"
                                    onClick={() => {
                                        setMentionTarget(p.value);
                                        markDirty();
                                    }}
                                    className={
                                        "px-3 py-1.5 rounded-[var(--radius-control)] text-[13px] font-medium border transition-colors " +
                                        (mentionTarget === p.value
                                            ? "btn-ghost-primary border-transparent"
                                            : "bg-surface-3 border-line-strong text-ink-faint hover:text-ink-muted")
                                    }
                                >
                                    {p.label}
                                </button>
                            ))}
                        </div>
                        <Input
                            id="mention-target"
                            value={mentionTarget}
                            onChange={(e) => {
                                setMentionTarget(e.target.value);
                                markDirty();
                            }}
                            placeholder="@here"
                        />
                    </Field>

                    <Divider />

                    <div>
                        <p className="text-[13px] font-medium text-ink-muted mb-1">
                            멘션을 붙일 알림
                        </p>
                        <p className="text-xs text-ink-faint mb-3">
                            아무것도 고르지 않으면 멘션 없이 전송됩니다.
                        </p>
                        <div className="flex flex-wrap gap-2">
                            {kinds.map((kind) => {
                                const on = mentionKinds.has(kind.value);
                                const disabled = !enabledKinds.has(kind.value);
                                return (
                                    <button
                                        key={kind.value}
                                        type="button"
                                        disabled={disabled}
                                        title={disabled ? "이 알림이 꺼져 있습니다" : undefined}
                                        onClick={() =>
                                            toggleKind(kind.value, mentionKinds, setMentionKinds)
                                        }
                                        className={
                                            "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[13px] font-medium border transition-colors disabled:opacity-35 disabled:cursor-not-allowed " +
                                            (on
                                                ? "btn-ghost-primary border-transparent"
                                                : "bg-surface-3 border-line-strong text-ink-faint hover:text-ink-muted")
                                        }
                                    >
                                        {on && <BellRing className="w-3 h-3" />}
                                        {kind.label}
                                    </button>
                                );
                            })}
                        </div>
                    </div>
                </div>
            </Card>

            {/* ══ 고급 ══════════════════════════════════ */}
            <Card>
                <CardHeader
                    icon={RefreshCcw}
                    title="고급"
                    description="전송이 밀렸을 때의 동작을 조정합니다."
                />

                <Field
                    label="알림 유효 시간 (분)"
                    htmlFor="ttl"
                    hint="이 시간을 넘긴 알림은 뒷북이 되므로 전송하지 않고 버립니다. 연결이 오래 끊겼다가 복구됐을 때 지난 알림이 쏟아지는 걸 막습니다."
                >
                    <Input
                        id="ttl"
                        type="number"
                        min={1}
                        max={1440}
                        value={ttlMinutes}
                        onChange={(e) => {
                            setTtlMinutes(Number(e.target.value));
                            markDirty();
                        }}
                        className="max-w-[160px]"
                    />
                </Field>
            </Card>

            {/* ══ 저장 ══════════════════════════════════ */}
            <div className="sticky bottom-0 -mx-1 px-1 pb-1 pt-3 bg-gradient-to-t from-surface-0 via-surface-0 to-transparent">
                <Button
                    variant="primary"
                    icon={Save}
                    loading={saving}
                    onClick={handleSave}
                    className="w-full"
                >
                    {dirty ? "변경사항 저장" : "저장됨"}
                </Button>
            </div>
        </div>
    );
}
