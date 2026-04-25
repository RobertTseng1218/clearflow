'use client';

import { useEffect, useMemo, useState } from 'react';
import { AppShell } from '@/components/app-shell';
import { ErrorState, LoadingState } from '@/components/page-state';
import { SectionCard, StatCard } from '@/components/stat-card';
import { getDashboard, getIntegrations, getPlan, getUsage } from '@/lib/api';

const LOW_SIGNAL_NOTIFICATION_KEYWORDS = [
  '已送達',
  '已寄達',
  '配送',
  '出貨',
  '已出貨',
  '已完成',
  '已確認',
  '付款已確認',
  '登入成功',
  '登入成功通知',
  '發票',
  '扣繳',
  '信用卡',
  '刷卡',
  '帳單',
  'receipt',
  'invoice',
  'statement',
  'shipment',
  'tracking',
  'login success',
];

function fmtDateTime(value?: string | null) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return new Intl.DateTimeFormat('zh-TW', {
    timeZone: 'Asia/Taipei',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(d);
}

function truncateText(value?: string | null, limit = 110) {
  const text = (value || '').replace(/\s+/g, ' ').trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trimEnd()}…` : text || '—';
}

function sourceBadge(sourceType?: string, sourceLabel?: string) {
  const label =
    sourceLabel ||
    (sourceType === 'calendar_event'
      ? 'Google Calendar'
      : sourceType === 'email'
        ? 'Gmail'
        : '未知來源');

  const className =
    sourceType === 'calendar_event'
      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
      : sourceType === 'email'
        ? 'bg-sky-50 text-sky-700 border-sky-200'
        : 'bg-slate-50 text-slate-700 border-slate-200';

  return (
    <span className={`rounded-full border px-2 py-1 text-xs font-semibold ${className}`}>
      {label}
    </span>
  );
}

function displayBadge(label?: string | null) {
  if (!label) return null;
  return (
    <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
      {label}
    </span>
  );
}

function sourceBreakdownText(sourceBreakdown?: Record<string, number>) {
  if (!sourceBreakdown) return null;

  const parts: string[] = [];
  if (sourceBreakdown.email) parts.push(`Gmail ${sourceBreakdown.email}`);
  if (sourceBreakdown.calendar_event) parts.push(`Calendar ${sourceBreakdown.calendar_event}`);

  return parts.length ? parts.join('｜') : null;
}

function signalBreakdownText(signalBreakdown?: Record<string, number>) {
  if (!signalBreakdown) return null;

  const parts: string[] = [];
  if (signalBreakdown.actionable_email) {
    parts.push(`待處理郵件 ${signalBreakdown.actionable_email}`);
  }
  if (signalBreakdown.notification_email) {
    parts.push(`通知郵件 ${signalBreakdown.notification_email}`);
  }
  if (signalBreakdown.marketing_email) {
    parts.push(`已降權促銷 ${signalBreakdown.marketing_email}`);
  }

  return parts.length ? parts.join('｜') : null;
}

const SUPPRESSED_PREVIEW_LIMIT = 3;

function suppressedItems(items?: Array<any>) {
  return (items || []).filter((item) => item?.title || item?.description);
}

function suppressedTotalCount(items?: Array<any>, counts?: Record<string, number>) {
  const total = counts?.suppressed_total;
  if (typeof total === 'number' && Number.isFinite(total) && total >= 0) {
    return total;
  }
  return suppressedItems(items).length;
}

function SuppressedItemsPreview({
  items,
  counts,
}: {
  items?: Array<any>;
  counts?: Record<string, number>;
}) {
  const normalizedItems = suppressedItems(items);
  if (normalizedItems.length === 0) return null;

  const visibleItems = normalizedItems.slice(0, SUPPRESSED_PREVIEW_LIMIT);
  const totalCount = suppressedTotalCount(items, counts);
  const hiddenCount = Math.max(totalCount - visibleItems.length, 0);

  return (
    <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-xs leading-6 text-slate-500">
      <div className="font-semibold text-slate-600">已壓低內容</div>
      <ul className="mt-2 space-y-1.5">
        {visibleItems.map((item, idx) => (
          <li
            key={item.dedupe_identity || item.thread_id || `${item.title || item.description}-${idx}`}
            className="flex gap-2"
          >
            <span className="mt-[9px] h-1.5 w-1.5 flex-none rounded-full bg-slate-300" />
            <span>
              <span className="font-medium text-slate-600">
                {item.display_label || '已壓低'}：
              </span>
              {truncateText(item.title || item.description, 64)}
            </span>
          </li>
        ))}
      </ul>
      {hiddenCount > 0 ? (
        <div className="mt-2 text-slate-400">另有 {hiddenCount} 筆已壓低內容。</div>
      ) : null}
    </div>
  );
}

function itemSourceType(item: any) {
  return item?.source_type || item?.meta?.source_type;
}

function itemSourceLabel(item: any) {
  return item?.source_label || item?.meta?.source_label;
}

function itemDisplayLabel(item: any) {
  return item?.display_label || item?.meta?.display_label;
}

function isNotificationLikeEmail(item: any) {
  const sourceType = itemSourceType(item);
  if (sourceType !== 'email') return false;

  const sourceCategory = item?.source_category || item?.meta?.source_category;
  if (sourceCategory === 'notification') return true;

  const text = `${item?.title || ''} ${item?.description || ''}`.toLowerCase();
  return LOW_SIGNAL_NOTIFICATION_KEYWORDS.some((keyword) => text.includes(keyword.toLowerCase()));
}

function isFutureCalendar(item: any) {
  const sourceType = itemSourceType(item);
  if (sourceType !== 'calendar_event') return false;
  return itemDisplayLabel(item) !== '已過行程';
}

function highlightRank(item: any) {
  const sourceType = itemSourceType(item);
  const displayLabel = itemDisplayLabel(item);

  if (sourceType === 'calendar_event' && displayLabel === '今日行程') return 0;
  if (sourceType === 'email' && displayLabel === '郵件跟進') return 1;
  if (sourceType === 'calendar_event' && displayLabel === '明日行程') return 2;
  if (sourceType === 'calendar_event') return 3;
  if (sourceType === 'email') return 4;
  return 9;
}

function sortByHighlightRank(items: any[]) {
  return [...items].sort((a, b) => {
    const rankDiff = highlightRank(a) - highlightRank(b);
    if (rankDiff !== 0) return rankDiff;
    const aPriority = typeof a?.priority_score === 'number' ? a.priority_score : 0;
    const bPriority = typeof b?.priority_score === 'number' ? b.priority_score : 0;
    if (aPriority !== bPriority) return bPriority - aPriority;
    return (a?.title || '').localeCompare(b?.title || '', 'zh-Hant');
  });
}

function priorityWeight(priority?: string | null) {
  if (priority === 'high') return 3;
  if (priority === 'medium') return 2;
  if (priority === 'low') return 1;
  return 0;
}

function sortTaskPreview(items: any[]) {
  return [...items].sort((a, b) => {
    const aSource = itemSourceType(a);
    const bSource = itemSourceType(b);

    const aGroupRank = aSource === 'calendar_event' ? 0 : 1;
    const bGroupRank = bSource === 'calendar_event' ? 0 : 1;
    if (aGroupRank !== bGroupRank) return aGroupRank - bGroupRank;

    const aPriority = priorityWeight(a?.priority);
    const bPriority = priorityWeight(b?.priority);
    if (aPriority !== bPriority) return bPriority - aPriority;

    const aDue = a?.due_at ? new Date(a.due_at).getTime() : Number.MAX_SAFE_INTEGER;
    const bDue = b?.due_at ? new Date(b.due_at).getTime() : Number.MAX_SAFE_INTEGER;
    return aDue - bDue;
  });
}

function taipeiDayKey(value?: string | null) {
  if (!value) return 'unknown-day';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return 'unknown-day';

  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Taipei',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(d);

  const year = parts.find((p) => p.type === 'year')?.value || '0000';
  const month = parts.find((p) => p.type === 'month')?.value || '00';
  const day = parts.find((p) => p.type === 'day')?.value || '00';

  return `${year}-${month}-${day}`;
}

function dedupeRecentActivities(items: any[]) {
  const sorted = [...items].sort((a, b) => {
    const aTime = a?.created_at ? new Date(a.created_at).getTime() : 0;
    const bTime = b?.created_at ? new Date(b.created_at).getTime() : 0;
    return bTime - aTime;
  });

  const seen = new Set<string>();

  return sorted.filter((activity) => {
    const message = (activity?.message || '').trim();
    if (!message) return false;

    const key = `${taipeiDayKey(activity?.created_at)}__${message}`;
    if (seen.has(key)) return false;

    seen.add(key);
    return true;
  });
}

function EmptyNote({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <div className="section-empty-note">
      <div className="text-sm font-medium text-slate-600">{title}</div>
      {description ? (
        <p className="mt-2 text-sm leading-6 text-slate-500">{description}</p>
      ) : null}
    </div>
  );
}

function HighlightCard({ item }: { item: any }) {
  return (
    <div className="rounded-xl border border-slate-200 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold text-slate-900">{item.title}</h3>
            {sourceBadge(itemSourceType(item), itemSourceLabel(item))}
            {displayBadge(itemDisplayLabel(item))}
          </div>
          <p className="text-sm text-slate-600">{truncateText(item.description, 120)}</p>
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dashboard, setDashboard] = useState<any>(null);
  const [plan, setPlan] = useState<any>(null);
  const [usage, setUsage] = useState<any>(null);
  const [integrations, setIntegrations] = useState<any[]>([]);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);

      const [dashboardRes, planRes, usageRes, integrationRes] = await Promise.all([
        getDashboard(),
        getPlan(),
        getUsage(),
        getIntegrations(),
      ]);

      setDashboard(dashboardRes);
      setPlan(planRes);
      setUsage(usageRes);
      setIntegrations(integrationRes.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : '資料載入失敗');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const todayHighlights = useMemo(() => {
    const rawItems = dashboard?.today_highlights || [];
    return sortByHighlightRank(
      rawItems.filter(
        (item: any) =>
          !isNotificationLikeEmail(item) &&
          (itemSourceType(item) !== 'calendar_event' || isFutureCalendar(item))
      )
    );
  }, [dashboard]);

  const emailHighlights = useMemo(() => {
    const rawItems = dashboard?.email_highlights || [];
    return sortByHighlightRank(
      rawItems.filter((item: any) => !isNotificationLikeEmail(item) && itemSourceType(item) === 'email')
    );
  }, [dashboard]);

  const eventHighlights = useMemo(() => {
    const rawItems = dashboard?.event_highlights || [];
    return sortByHighlightRank(rawItems.filter((item: any) => isFutureCalendar(item)));
  }, [dashboard]);

  const taskPreviewItems = useMemo(() => {
    const rawItems = dashboard?.task_preview?.items || [];
    return sortTaskPreview(rawItems.filter((item: any) => !isNotificationLikeEmail(item)));
  }, [dashboard]);

  const recentActivities = useMemo(() => {
    return dedupeRecentActivities(dashboard?.recent_activity_preview?.items || []).slice(0, 5);
  }, [dashboard]);

  return (
    <AppShell title="總覽" subtitle="先處理真正需要你出手的內容，把通知、促銷與已過資訊留在後面。">
      {loading ? <LoadingState message="正在載入 Dashboard..." /> : null}

      {error ? (
        <ErrorState
          message={error}
          action={
            <button
              onClick={load}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              重新載入
            </button>
          }
        />
      ) : null}

      {!loading && !error && dashboard && usage && plan ? (
        <>
          <div className="grid gap-4 xl:grid-cols-4">
            <StatCard
              title="目前方案"
              value={plan.plan_name}
              note="可隨時升級使用更多整合與 AI 次數"
            />
            <StatCard
              title="本月 AI 使用"
              value={`${usage.monthly_ai_usage} / ${usage.monthly_ai_quota}`}
              note="接近額度時會提醒你"
            />
            <StatCard
              title="開啟待辦"
              value={`${dashboard.task_preview?.open_count ?? 0}`}
              note="只保留較像真正待處理的項目"
            />
            <StatCard
              title="今日資料來源"
              value={`${dashboard.source_overview?.active_sources ?? integrations.length}`}
              note={
                sourceBreakdownText(dashboard.daily_summary_preview?.source_breakdown) ||
                '今天納入總覽與摘要的資料'
              }
            />
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr_1fr]">
            <SectionCard title="今天先看什麼">
              <div className="space-y-3 min-h-[180px]">
                {todayHighlights.length === 0 ? (
                  <EmptyNote
                    title="目前沒有需要優先處理的重點。"
                    description="今天的整理結果已經放在右側摘要與下方待辦，你可以從那裡接著看。"
                  />
                ) : (
                  todayHighlights.map((item: any, idx: number) => (
                    <HighlightCard key={`${item.related_id || item.id}-${idx}`} item={item} />
                  ))
                )}
              </div>
            </SectionCard>

            <div className="space-y-6">
              <SectionCard title="今日摘要">
                <div className="space-y-2">
                  <p className="text-sm text-slate-700">
                    {dashboard.daily_summary_preview?.summary_text_preview || '尚未生成今日摘要。'}
                  </p>

                  {sourceBreakdownText(dashboard.daily_summary_preview?.source_breakdown) ? (
                    <div className="text-xs font-medium text-slate-500">
                      納入來源：{sourceBreakdownText(dashboard.daily_summary_preview?.source_breakdown)}
                    </div>
                  ) : null}

                  {signalBreakdownText(dashboard.daily_summary_preview?.signal_breakdown) ? (
                    <div className="text-xs font-medium text-slate-500">
                      {signalBreakdownText(dashboard.daily_summary_preview?.signal_breakdown)}
                    </div>
                  ) : null}

                  <SuppressedItemsPreview
                    items={dashboard.daily_summary_preview?.filtered_items}
                    counts={dashboard.daily_summary_preview?.filtered_counts}
                  />
                </div>
              </SectionCard>

              <SectionCard title="提醒">
                <div className="space-y-3">
                  {(dashboard.reminder_preview?.items || []).length === 0 ? (
                    <EmptyNote
                      title="目前沒有即將到時的提醒。"
                      description="若之後有接近時間、需要你提前留意的安排，這裡會先提醒你。"
                    />
                  ) : (
                    (dashboard.reminder_preview?.items || []).map((reminder: any, idx: number) => (
                      <div
                        key={`${reminder.title}-${idx}`}
                        className="rounded-xl border border-slate-200 p-3"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <div className="font-medium text-slate-900">{reminder.title}</div>
                          {sourceBadge(reminder.source_type, reminder.source_label)}
                        </div>
                        <div className="mt-1 text-sm text-slate-600">
                          {truncateText(reminder.message, 80)}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </SectionCard>
            </div>
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-2">
            <SectionCard title="郵件重點">
              <div className="space-y-3">
                {emailHighlights.length === 0 ? (
                  <EmptyNote
                    title="目前沒有需要你立刻處理的郵件重點。"
                    description="今天有同步到郵件，但暫時沒有被判定為高優先內容。"
                  />
                ) : (
                  emailHighlights.map((item: any, idx: number) => (
                    <HighlightCard key={`email-${item.related_id || item.id}-${idx}`} item={item} />
                  ))
                )}
              </div>
            </SectionCard>

            <SectionCard title="行程 / 會議重點">
              <div className="space-y-3">
                {eventHighlights.length === 0 ? (
                  <EmptyNote
                    title="今天暫時沒有需要特別留意的行程安排。"
                    description="未來行程仍會保留在摘要或提醒區，接近時間時再優先顯示。"
                  />
                ) : (
                  eventHighlights.map((item: any, idx: number) => (
                    <HighlightCard key={`event-${item.related_id || item.id}-${idx}`} item={item} />
                  ))
                )}
              </div>
            </SectionCard>
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-2">
            <SectionCard title="現在最該處理的待辦">
              <div className="space-y-3">
                {taskPreviewItems.length === 0 ? (
                  <EmptyNote
                    title="目前沒有需要處理的待辦。"
                    description="如果之後有新的跟進郵件或行程提醒，這裡會先整理給你。"
                  />
                ) : (
                  taskPreviewItems.map((task: any) => (
                    <div key={task.id} className="rounded-xl border border-slate-200 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="font-semibold text-slate-900">{task.title}</h3>
                            {sourceBadge(task.source_type, task.source_label)}
                            {displayBadge(
                              task.task_kind === 'calendar_reminder'
                                ? '行程提醒'
                                : task.task_kind === 'email_followup'
                                  ? '郵件跟進'
                                  : undefined
                            )}
                          </div>

                          <p className="text-sm text-slate-600">
                            {truncateText(task.description, 120)}
                          </p>

                          {task.display_hint ? (
                            <div className="text-xs text-slate-500">{task.display_hint}</div>
                          ) : null}
                        </div>
                      </div>

                      <div className="mt-3 flex gap-3 text-xs text-slate-500">
                        <span>到期：{fmtDateTime(task.due_at)}</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </SectionCard>

            <SectionCard title="最近活動">
              <div className="space-y-3">
                {recentActivities.length === 0 ? (
                  <EmptyNote
                    title="目前還沒有新的活動紀錄。"
                    description="當同步、摘要整理或待辦更新完成後，這裡會顯示最新結果。"
                  />
                ) : (
                  recentActivities.map((activity: any, idx: number) => (
                    <div
                      key={`${activity.created_at}-${activity.message}-${idx}`}
                      className="rounded-xl border border-slate-200 p-4"
                    >
                      <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                        {fmtDateTime(activity.created_at)}
                      </div>
                      <div className="mt-1 text-sm text-slate-700">{activity.message}</div>
                    </div>
                  ))
                )}
              </div>
            </SectionCard>
          </div>
        </>
      ) : null}
    </AppShell>
  );
}