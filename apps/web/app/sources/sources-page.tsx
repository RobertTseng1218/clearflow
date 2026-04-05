'use client';

import { useEffect, useMemo, useState } from 'react';
import { AppShell } from '@/components/app-shell';
import { EmptyState, ErrorState, LoadingState } from '@/components/page-state';
import { SectionCard } from '@/components/stat-card';
import { setAccessToken } from '@/lib/auth';
import {
  connectIntegration,
  deleteIntegration,
  getIntegrations,
  notifyDataUpdated,
  syncIntegration,
} from '@/lib/api';

const DISPLAY_TIME_ZONE = 'Asia/Taipei';

type FeedbackState = {
  tone: 'success' | 'info' | 'error';
  message: string;
};

function providerLabel(providerKey: string) {
  switch (providerKey) {
    case 'gmail':
      return 'Gmail';
    case 'gcal':
      return 'Google Calendar';
    default:
      return providerKey;
  }
}

function providerDisplay(providerKey?: string | null) {
  if (!providerKey) return '來源';
  return providerLabel(providerKey);
}

function fmtDateTime(value?: string | null) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return new Intl.DateTimeFormat('zh-TW', {
    timeZone: DISPLAY_TIME_ZONE,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(d);
}

function feedbackClassName(tone: FeedbackState['tone']) {
  if (tone === 'success') {
    return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  }

  if (tone === 'error') {
    return 'border-rose-200 bg-rose-50 text-rose-700';
  }

  return 'border-sky-200 bg-sky-50 text-sky-700';
}

function statusBadgeLabel(integration: any) {
  const syncResult = integration.last_sync_result;
  if (syncResult === 'success') return '已同步';
  if (syncResult === 'no_change') return '最新';
  if (integration.status === 'connected') return '已連接';
  return integration.status;
}

function statusBadgeClassName(integration: any) {
  const syncResult = integration.last_sync_result;
  if (syncResult === 'success') {
    return 'bg-emerald-50 text-emerald-700';
  }

  if (syncResult === 'no_change') {
    return 'bg-sky-50 text-sky-700';
  }

  return 'bg-brand-50 text-brand-600';
}

function buildSyncSummary(integration: any) {
  const fetched = Number(integration.last_sync_fetched_count || 0);
  const created = Number(integration.last_sync_created_count || 0);
  const updated = Number(integration.last_sync_updated_count || 0);
  const unchanged = Number(integration.last_sync_unchanged_count || 0);
  const changed = created + updated;

  if (fetched === 0) {
    return '最近一次同步沒有抓到可更新的資料。';
  }

  if (changed === 0) {
    return `最近一次同步檢查 ${fetched} 筆資料，沒有新的重點變化。`;
  }

  const parts: string[] = [];
  if (created > 0) parts.push(`新增 ${created}`);
  if (updated > 0) parts.push(`更新 ${updated}`);
  if (unchanged > 0) parts.push(`略過 ${unchanged}`);

  return `最近一次同步檢查 ${fetched} 筆資料，${parts.join('、')}。`;
}

function statusHintText(integration: any) {
  if (integration.last_sync_result === 'success') {
    return integration.last_sync_message || buildSyncSummary(integration);
  }

  if (integration.last_sync_result === 'no_change') {
    return integration.last_sync_message || '已確認最新狀態，目前沒有新的重點變化。';
  }

  return '已完成連接，現在可以開始同步資料。';
}

export default function SourcesPage() {
  const [integrations, setIntegrations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [oauthNotice, setOauthNotice] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<FeedbackState | null>(null);

  const oauthResult = useMemo(() => {
    if (typeof window === 'undefined') return null;
    const raw = window.location.hash?.replace(/^#/, '') || '';
    if (!raw) return null;
    const params = new URLSearchParams(raw);
    const accessToken = params.get('access_token');
    const provider = params.get('provider');
    const oauth = params.get('oauth');
    if (!accessToken && !oauth) return null;
    return { accessToken, provider, oauth };
  }, []);

  useEffect(() => {
    if (!feedback) return undefined;

    const timer = window.setTimeout(() => {
      setFeedback(null);
    }, 3200);

    return () => window.clearTimeout(timer);
  }, [feedback]);

  const load = async (options?: { silent?: boolean }) => {
    const silent = Boolean(options?.silent);

    try {
      if (silent) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      setPageError(null);

      const result = await getIntegrations();
      setIntegrations(result.items || []);
    } catch (err) {
      const message = err instanceof Error ? err.message : '來源載入失敗';

      if (silent && integrations.length > 0) {
        setFeedback({
          tone: 'error',
          message: '來源列表更新未完成，先顯示上次結果。',
        });
      } else {
        setPageError(message);
      }
    } finally {
      if (silent) {
        setRefreshing(false);
      } else {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    if (!oauthResult) {
      void load();
      return;
    }

    if (oauthResult.accessToken) {
      setAccessToken(oauthResult.accessToken);
    }

    if (oauthResult.oauth === 'success') {
      setOauthNotice(`${providerDisplay(oauthResult.provider)} 已成功連接，你現在可以開始同步資料。`);
    }

    window.history.replaceState({}, '', '/sources');
    void load();
  }, [oauthResult]);

  const handleConnect = async (providerKey: 'gmail' | 'gcal') => {
    try {
      setBusy(providerKey);
      setFeedback(null);

      const result = await connectIntegration(providerKey);

      if (result.redirect_url) {
        window.location.href = result.redirect_url;
        return;
      }

      throw new Error('找不到授權跳轉網址，請稍後再試。');
    } catch (err) {
      setFeedback({
        tone: 'error',
        message: err instanceof Error ? err.message : '連接失敗，請稍後再試。',
      });
      setBusy(null);
    }
  };

  const handleSync = async (integrationId: string) => {
    try {
      setBusy(integrationId);
      setFeedback(null);

      const result = await syncIntegration(integrationId);
      notifyDataUpdated({ reason: 'sync', message: result.message });
      await load({ silent: true });

      setFeedback({
        tone: result.sync_status === 'no_change' ? 'info' : 'success',
        message:
          result.message ||
          (result.sync_status === 'no_change'
            ? `${providerDisplay(result.provider_key)} 已完成同步，目前沒有新的重點變化。`
            : `${providerDisplay(result.provider_key)} 同步完成，本次檢查 ${result.fetched_count || result.saved_count} 筆資料。`),
      });
    } catch (err) {
      setFeedback({
        tone: 'error',
        message: err instanceof Error ? err.message : '同步失敗，請稍後再試。',
      });
    } finally {
      setBusy(null);
    }
  };

  const handleDelete = async (integrationId: string) => {
    try {
      setBusy(integrationId);
      setFeedback(null);
      await deleteIntegration(integrationId);
      await load({ silent: true });

      setFeedback({
        tone: 'success',
        message: '來源已移除。',
      });
    } catch (err) {
      setFeedback({
        tone: 'error',
        message: err instanceof Error ? err.message : '移除來源失敗，請稍後再試。',
      });
    } finally {
      setBusy(null);
    }
  };

  return (
    <AppShell title="來源" subtitle="管理目前已連接的工作來源與同步狀態；總覽頁的「今日資料來源」則代表今天實際有資料進來的來源。">
      {loading ? <LoadingState message="正在載入來源..." /> : null}

      {!loading ? (
        <>
          {oauthNotice ? (
            <div className="mb-6 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              {oauthNotice}
            </div>
          ) : null}

          {feedback ? (
            <div className={`mb-6 rounded-2xl border px-4 py-3 text-sm ${feedbackClassName(feedback.tone)}`}>
              {feedback.message}
            </div>
          ) : null}

          {refreshing ? (
            <div className="mb-6 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              正在更新來源列表，畫面會保留目前內容。
            </div>
          ) : null}

          {pageError ? (
            <ErrorState
              message={pageError}
              action={
                <button onClick={() => void load()} className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
                  重新載入
                </button>
              }
            />
          ) : null}

          {!pageError ? (
            <>
              <SectionCard title="快速連接來源">
                <div className="space-y-3">
                  <p className="text-sm text-slate-600">
                    這裡顯示的是你目前已連接的來源。免費版目前最多只能連接 1 個來源；若要同時使用 Gmail 與 Google Calendar，後續可升級個人版。
                  </p>
                  <div className="flex flex-wrap gap-3">
                    <button
                      onClick={() => handleConnect('gmail')}
                      disabled={busy === 'gmail'}
                      className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {busy === 'gmail' ? '連接中...' : '連接 Gmail'}
                    </button>

                    <button
                      onClick={() => handleConnect('gcal')}
                      disabled={busy === 'gcal'}
                      className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {busy === 'gcal' ? '連接中...' : '連接 Google Calendar'}
                    </button>
                  </div>
                </div>
              </SectionCard>

              <div className="mt-6">
                {integrations.length === 0 ? (
                  <EmptyState title="尚未連接任何來源" description="先連接 Gmail 或 Google Calendar，順流才能開始幫你整理工作。" />
                ) : (
                  <SectionCard title="已連接來源">
                    <div className="mb-3 text-sm text-slate-500">
                      這裡顯示的是目前已完成授權並可同步的來源，與總覽頁的「今日資料來源」屬於不同統計口徑。
                    </div>
                    <div className="space-y-4">
                      {integrations.map((integration) => (
                        <div key={integration.id} className="rounded-xl border border-slate-200 p-4">
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div className="space-y-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <h3 className="font-semibold text-slate-900">{providerLabel(integration.provider_key)}</h3>
                                <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusBadgeClassName(integration)}`}>
                                  {statusBadgeLabel(integration)}
                                </span>
                              </div>

                              <p className="text-sm text-slate-600">
                                最後同步：{fmtDateTime(integration.last_synced_at)}
                              </p>

                              <p className="text-xs text-slate-500">
                                {busy === integration.id ? '正在抓取最新資料，請稍候...' : statusHintText(integration)}
                              </p>
                            </div>

                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => handleSync(integration.id)}
                                disabled={busy === integration.id}
                                className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                              >
                                {busy === integration.id ? '同步中...' : '立即同步'}
                              </button>
                              <button
                                onClick={() => handleDelete(integration.id)}
                                disabled={busy === integration.id}
                                className="rounded-xl border border-rose-200 px-3 py-2 text-sm font-medium text-rose-600 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60"
                              >
                                移除
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </SectionCard>
                )}
              </div>
            </>
          ) : null}
        </>
      ) : null}
    </AppShell>
  );
}
