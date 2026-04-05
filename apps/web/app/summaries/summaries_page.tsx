'use client';

import { useEffect, useMemo, useState } from 'react';
import { AppShell } from '@/components/app-shell';
import { EmptyState, ErrorState, LoadingState } from '@/components/page-state';
import { SectionCard } from '@/components/stat-card';
import { getSummaries, getSummary } from '@/lib/api';

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

function fmtDate(value: string) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return new Intl.DateTimeFormat('zh-TW', {
    month: '2-digit',
    day: '2-digit',
  }).format(d);
}

function truncateText(value?: string | null, limit = 130) {
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

function breakdownText(sourceBreakdown?: Record<string, number>) {
  if (!sourceBreakdown) return null;

  const parts: string[] = [];
  if (sourceBreakdown.email) parts.push(`Gmail ${sourceBreakdown.email}`);
  if (sourceBreakdown.calendar_event) parts.push(`Calendar ${sourceBreakdown.calendar_event}`);

  return parts.length ? parts.join('｜') : null;
}

function filteredItemsPreview(items?: Array<any>) {
  if (!items || items.length === 0) return null;
  return items
    .slice(0, 4)
    .map((item) => `${item.display_label || '已壓低'}：${item.title}`)
    .join('｜');
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

function isNotificationLikeEmail(item: any) {
  const sourceType = item?.source_type || item?.meta?.source_type;
  if (sourceType !== 'email') return false;

  const sourceCategory = item?.source_category || item?.meta?.source_category;
  if (sourceCategory === 'notification') return true;

  const text = `${item?.title || ''} ${item?.description || ''}`.toLowerCase();
  return LOW_SIGNAL_NOTIFICATION_KEYWORDS.some((keyword) => text.includes(keyword.toLowerCase()));
}

function eventRank(item: any) {
  const label = item?.display_label || item?.meta?.display_label;
  if (label === '今日行程') return 0;
  if (label === '明日行程') return 1;
  return 2;
}

export default function SummariesPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summaries, setSummaries] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<any | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);

      const result = await getSummaries();
      const items = result.items || [];

      setSummaries(items);

      if (items.length > 0) {
        setSelectedId(items[0].id);
      } else {
        setSelectedId(null);
        setDetail(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '摘要載入失敗');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }

    let cancelled = false;

    const run = async () => {
      try {
        setDetailLoading(true);
        const result = await getSummary(selectedId);
        if (!cancelled) {
          setDetail(result);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : '摘要詳情載入失敗');
        }
      } finally {
        if (!cancelled) {
          setDetailLoading(false);
        }
      }
    };

    run();

    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const selectedSummary = useMemo(
    () => summaries.find((item) => item.id === selectedId),
    [summaries, selectedId]
  );

  const groupedItems = useMemo(() => {
    const detailItems = detail?.items || [];

    const emailItems = detailItems
      .filter((item: any) => {
        const sourceType = item.source_type || item.meta?.source_type;
        const sourceCategory = item.source_category || item.meta?.source_category;
        return sourceType === 'email' && sourceCategory === 'actionable' && !isNotificationLikeEmail(item);
      })
      .sort((a: any, b: any) => (b.priority_score || 0) - (a.priority_score || 0));

    const eventItems = detailItems
      .filter((item: any) => {
        const sourceType = item.source_type || item.meta?.source_type;
        const displayLabel = item.display_label || item.meta?.display_label;
        return sourceType === 'calendar_event' && displayLabel !== '已過行程';
      })
      .sort((a: any, b: any) => eventRank(a) - eventRank(b));

    return { emailItems, eventItems };
  }, [detail]);

  return (
    <AppShell
      title="摘要"
      subtitle="先看今天的整體脈絡，再往下展開真正需要留意的郵件與未來行程。"
    >
      {loading ? <LoadingState message="正在載入摘要..." /> : null}

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

      {!loading && !error ? (
        summaries.length === 0 ? (
          <EmptyState
            title="尚未生成摘要"
            description="先到來源頁同步資料，順流才會幫你整理出每日摘要。"
          />
        ) : (
          <div className="grid gap-6 xl:grid-cols-[0.95fr_1.25fr]">
            <SectionCard title="摘要列表">
              <div className="space-y-4">
                {summaries.map((summary) => {
                  const active = summary.id === selectedId;

                  return (
                    <button
                      key={summary.id}
                      type="button"
                      onClick={() => setSelectedId(summary.id)}
                      className={`w-full rounded-xl border p-4 text-left transition ${
                        active
                          ? 'border-brand-300 bg-brand-50/50'
                          : 'border-slate-200 hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="text-sm font-semibold text-slate-900">
                            {fmtDate(summary.summary_date)}
                          </div>
                          <div className="mt-1 text-xs uppercase tracking-wide text-slate-500">
                            {summary.summary_type}
                          </div>
                        </div>
                        <span className="text-xs font-medium text-brand-600">
                          查看詳情
                        </span>
                      </div>

                      <p className="mt-3 text-sm text-slate-600">
                        {truncateText(summary.summary_text_preview, 120)}
                      </p>

                      {breakdownText(summary.source_breakdown) ? (
                        <div className="mt-2 text-xs font-medium text-slate-500">
                          {breakdownText(summary.source_breakdown)}
                        </div>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            </SectionCard>

            <SectionCard
              title={
                selectedSummary
                  ? `摘要詳情｜${fmtDate(selectedSummary.summary_date)}`
                  : '摘要詳情'
              }
            >
              {detailLoading ? (
                <LoadingState message="正在載入摘要詳情..." />
              ) : detail ? (
                <div className="space-y-6">
                  <div className="rounded-xl border border-slate-200 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                        今日整理
                      </div>

                      <div className="flex flex-wrap items-center gap-2">
                        {breakdownText(detail.source_breakdown) ? (
                          <div className="text-xs font-medium text-slate-500">
                            {breakdownText(detail.source_breakdown)}
                          </div>
                        ) : null}

                        {signalBreakdownText(detail.signal_breakdown) ? (
                          <div className="text-xs font-medium text-slate-500">
                            {signalBreakdownText(detail.signal_breakdown)}
                          </div>
                        ) : null}
                      </div>
                    </div>

                    <p className="mt-2 text-sm leading-7 text-slate-700">
                      {detail.summary_text || '—'}
                    </p>

                    {filteredItemsPreview(detail.filtered_items) ? (
                      <div className="mt-3 rounded-xl border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-xs leading-6 text-slate-500">
                        <div className="font-semibold text-slate-600">已壓低內容</div>
                        <div className="mt-1">{filteredItemsPreview(detail.filtered_items)}</div>
                      </div>
                    ) : null}
                  </div>

                  <div className="grid gap-6 xl:grid-cols-2">
                    <SectionCard title="郵件重點">
                      <div className="space-y-3">
                        {groupedItems.emailItems.length === 0 ? (
                          <div className="text-sm text-slate-500">
                            今天沒有需要優先處理的郵件重點。
                          </div>
                        ) : (
                          groupedItems.emailItems.map((item: any) => (
                            <div key={item.id} className="rounded-xl border border-slate-200 p-4">
                              <div className="flex flex-wrap items-center gap-2">
                                <h3 className="font-semibold text-slate-900">
                                  {item.title}
                                </h3>
                                {sourceBadge(item.source_type || item.meta?.source_type, item.source_label || item.meta?.source_label)}
                                {displayBadge(item.display_label || item.meta?.display_label)}
                              </div>

                              <p className="mt-2 text-sm text-slate-600">
                                {truncateText(item.description, 140)}
                              </p>
                            </div>
                          ))
                        )}
                      </div>
                    </SectionCard>

                    <SectionCard title="行程 / 會議重點">
                      <div className="space-y-3">
                        {groupedItems.eventItems.length === 0 ? (
                          <div className="text-sm text-slate-500">
                            今天沒有需要特別留意的未來行程。
                          </div>
                        ) : (
                          groupedItems.eventItems.map((item: any) => (
                            <div key={item.id} className="rounded-xl border border-slate-200 p-4">
                              <div className="flex flex-wrap items-center gap-2">
                                <h3 className="font-semibold text-slate-900">
                                  {item.title}
                                </h3>
                                {sourceBadge(item.source_type || item.meta?.source_type, item.source_label || item.meta?.source_label)}
                                {displayBadge(item.display_label || item.meta?.display_label)}
                              </div>

                              <p className="mt-2 text-sm text-slate-600">
                                {truncateText(item.description, 120)}
                              </p>
                            </div>
                          ))
                        )}
                      </div>
                    </SectionCard>
                  </div>
                </div>
              ) : (
                <EmptyState
                  title="尚未選擇摘要"
                  description="請先從左側選擇一筆摘要。"
                />
              )}
            </SectionCard>
          </div>
        )
      ) : null}
    </AppShell>
  );
}
