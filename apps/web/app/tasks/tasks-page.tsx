'use client';

import { useEffect, useMemo, useState } from 'react';
import { AppShell } from '@/components/app-shell';
import { EmptyState, ErrorState, LoadingState } from '@/components/page-state';
import { SectionCard } from '@/components/stat-card';
import { bindDataUpdated, getTasks, notifyDataUpdated, patchTask } from '@/lib/api';

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

const DISPLAY_TIME_ZONE = 'Asia/Taipei';


const DATA_UPDATED_EVENT = 'clearflow:data-updated';
const DATA_UPDATED_STORAGE_KEY = 'clearflow:lastSyncSignal';

type DataUpdatedDetail = {
  reason?: 'sync' | 'task' | 'manual' | string;
  message?: string;
  value?: string;
  [key: string]: unknown;
};

function subscribeDataUpdated(listener: (detail?: DataUpdatedDetail) => void) {
  if (typeof window === 'undefined') {
    return () => {};
  }

  if (typeof bindDataUpdated === 'function') {
    try {
      return bindDataUpdated(listener as any);
    } catch {
      // fall through to local fallback
    }
  }

  const handleCustom = (event: Event) => {
    const customEvent = event as CustomEvent<DataUpdatedDetail | undefined>;
    listener(customEvent.detail);
  };

  const handleStorage = (event: StorageEvent) => {
    if (event.key !== DATA_UPDATED_STORAGE_KEY) return;
    listener({ reason: 'sync', value: event.newValue ?? undefined });
  };

  window.addEventListener(DATA_UPDATED_EVENT, handleCustom as EventListener);
  window.addEventListener('storage', handleStorage);

  return () => {
    window.removeEventListener(DATA_UPDATED_EVENT, handleCustom as EventListener);
    window.removeEventListener('storage', handleStorage);
  };
}

function publishDataUpdated(detail?: DataUpdatedDetail) {
  if (typeof notifyDataUpdated === 'function') {
    try {
      notifyDataUpdated(detail as any);
      return;
    } catch {
      // fall through to local fallback
    }
  }

  if (typeof window === 'undefined') return;

  const payload = detail || {};
  try {
    window.localStorage.setItem(DATA_UPDATED_STORAGE_KEY, String(Date.now()));
  } catch {
    // ignore localStorage availability issues
  }

  window.dispatchEvent(new CustomEvent<DataUpdatedDetail>(DATA_UPDATED_EVENT, { detail: payload }));
}

type TaskViewFilter = 'active' | 'snoozed' | 'done' | 'archived' | 'all';

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

function truncateText(value?: string | null, limit = 150) {
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

function taskKindLabel(taskKind?: string | null) {
  if (taskKind === 'calendar_reminder') return '行程提醒';
  if (taskKind === 'email_followup') return '郵件跟進';
  return null;
}

function priorityWeight(priority?: string | null) {
  if (priority === 'high') return 3;
  if (priority === 'medium') return 2;
  if (priority === 'low') return 1;
  return 0;
}

function priorityLabel(priority?: string | null) {
  if (priority === 'high') return '高優先';
  if (priority === 'medium') return '中優先';
  if (priority === 'low') return '低優先';
  return '未設定優先級';
}

function priorityBadgeClass(priority?: string | null) {
  if (priority === 'high') return 'bg-rose-50 text-rose-700 border-rose-200';
  if (priority === 'medium') return 'bg-amber-50 text-amber-700 border-amber-200';
  if (priority === 'low') return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  return 'bg-slate-100 text-slate-600 border-slate-200';
}

function statusLabel(status?: string | null) {
  if (status === 'open') return '進行中';
  if (status === 'in_progress') return '處理中';
  if (status === 'done') return '已完成';
  if (status === 'snoozed') return '稍後處理';
  if (status === 'archived') return '已封存';
  return '未知狀態';
}

function statusBadgeClass(status?: string | null) {
  if (status === 'open' || status === 'in_progress') return 'bg-sky-50 text-sky-700 border-sky-200';
  if (status === 'done') return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (status === 'snoozed') return 'bg-amber-50 text-amber-700 border-amber-200';
  if (status === 'archived') return 'bg-slate-100 text-slate-600 border-slate-200';
  return 'bg-slate-100 text-slate-600 border-slate-200';
}

function isNotificationLikeEmail(task: any) {
  if (task.source_type !== 'email') return false;
  if (task.email_signal === 'notification') return true;

  const text = `${task.title || ''} ${task.description || ''}`.toLowerCase();
  return LOW_SIGNAL_NOTIFICATION_KEYWORDS.some((keyword) => text.includes(keyword.toLowerCase()));
}

function sortTasks(items: any[]) {
  return [...items].sort((a, b) => {
    const aPriority = priorityWeight(a.priority);
    const bPriority = priorityWeight(b.priority);
    if (aPriority !== bPriority) return bPriority - aPriority;

    const aDue = a?.due_at ? new Date(a.due_at).getTime() : Number.MAX_SAFE_INTEGER;
    const bDue = b?.due_at ? new Date(b.due_at).getTime() : Number.MAX_SAFE_INTEGER;
    if (aDue !== bDue) return aDue - bDue;

    return (a?.title || '').localeCompare(b?.title || '', 'zh-Hant');
  });
}

function SectionEmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/70 px-4 py-4">
      <div className="text-sm font-medium text-slate-700">{title}</div>
      {description ? <div className="mt-1 text-sm leading-6 text-slate-500">{description}</div> : null}
    </div>
  );
}

function filterLabel(view: TaskViewFilter) {
  return {
    active: '進行中',
    snoozed: '稍後處理',
    done: '已完成',
    archived: '已封存',
    all: '全部',
  }[view];
}

function emptyCopy(view: TaskViewFilter) {
  if (view === 'snoozed') {
    return {
      title: '目前沒有被暫時延後的待辦。',
      description: '若你先把某些事情往後放，這裡會幫你集中保留，之後再回來接手。',
    };
  }
  if (view === 'done') {
    return {
      title: '目前還沒有已完成的待辦。',
      description: '當你把待辦處理完成後，這裡會保留完成結果，方便你回頭確認。',
    };
  }
  if (view === 'archived') {
    return {
      title: '目前沒有已封存的待辦。',
      description: '當你判定某些項目暫時不需要再追蹤時，它們會被整理到這裡。',
    };
  }
  if (view === 'all') {
    return {
      title: '目前還沒有任何待辦資料。',
      description: '之後若有新的郵件跟進或行程提醒，這裡會幫你集中整理。',
    };
  }
  return {
    title: '目前沒有需要你立刻處理的待辦',
    description: '若只是通知或一般更新，系統會先收進摘要與觀測層，不會塞滿你的待辦清單。',
  };
}

function taskActionLabel(status: string, nextStatus: string) {
  if (nextStatus === 'done') return '標記完成';
  if (nextStatus === 'snoozed') return '稍後處理';
  if (nextStatus === 'archived') return '封存';
  if (nextStatus === 'open') return status === 'done' ? '恢復為進行中' : '恢復處理';
  return '更新狀態';
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [filter, setFilter] = useState<TaskViewFilter>('active');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshNotice, setRefreshNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const load = async (options?: { silent?: boolean; reason?: 'sync' | 'task' | 'manual' }) => {
    const silent = Boolean(options?.silent);

    try {
      if (silent) {
        setRefreshing(true);
      } else {
        setLoading(true);
        setError(null);
      }

      const result = await getTasks({ status: 'all' });
      setTasks(result.items || []);

      if (options?.reason === 'sync') {
        setRefreshNotice('待辦清單已更新為最新同步結果。');
      } else if (options?.reason === 'task') {
        setRefreshNotice('待辦狀態已更新。');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : '待辦載入失敗';

      if (silent && tasks.length > 0) {
        setRefreshNotice('待辦更新未完成，先顯示上次結果。');
      } else {
        setError(message);
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
    void load();
  }, []);

  useEffect(() => {
    const unbind = subscribeDataUpdated((detail) => {
      void load({ silent: true, reason: detail?.reason === 'task' ? 'task' : 'sync' });
    });

    return () => {
      unbind();
    };
  }, []);

  useEffect(() => {
    if (!refreshNotice) return undefined;

    const timer = window.setTimeout(() => {
      setRefreshNotice(null);
    }, 2600);

    return () => window.clearTimeout(timer);
  }, [refreshNotice]);

  const counts = useMemo(() => {
    return {
      active: tasks.filter((task) => task.status === 'open' || task.status === 'in_progress').length,
      snoozed: tasks.filter((task) => task.status === 'snoozed').length,
      done: tasks.filter((task) => task.status === 'done').length,
      archived: tasks.filter((task) => task.status === 'archived').length,
      all: tasks.length,
    };
  }, [tasks]);

  const filteredTasks = useMemo(() => {
    if (filter === 'all') return tasks;
    if (filter === 'active') {
      return tasks.filter((task) => task.status === 'open' || task.status === 'in_progress');
    }
    return tasks.filter((task) => task.status === filter);
  }, [filter, tasks]);

  const grouped = useMemo(() => {
    return {
      calendar: sortTasks(
        filteredTasks.filter((task) => task.source_type === 'calendar_event')
      ),
      email: sortTasks(
        filteredTasks.filter(
          (task) =>
            task.source_type === 'email' &&
            (task.email_signal === 'actionable' || filter !== 'active') &&
            !isNotificationLikeEmail(task)
        )
      ),
    };
  }, [filter, filteredTasks]);

  const applyTaskUpdate = async (task: any, nextStatus: 'open' | 'done' | 'snoozed' | 'archived') => {
    try {
      setUpdatingId(task.id);
      setError(null);

      const result = await patchTask(task.id, { status: nextStatus });
      const nextTask = result?.task || { ...task, status: nextStatus };
      const message = result?.message || `已更新待辦「${task.title}」的狀態。`;

      setTasks((prev) =>
        prev.map((item) => (item.id === task.id ? { ...item, ...nextTask } : item))
      );
      setRefreshNotice(message);
      publishDataUpdated({ reason: 'task', message });
    } catch (err) {
      setError(err instanceof Error ? err.message : '更新待辦失敗');
    } finally {
      setUpdatingId(null);
    }
  };

  const renderActions = (task: any) => {
    const disabled = updatingId === task.id;

    const renderAction = (
      nextStatus: 'open' | 'done' | 'snoozed' | 'archived',
      className?: string,
    ) => (
      <button
        key={`${task.id}-${nextStatus}`}
        onClick={() => void applyTaskUpdate(task, nextStatus)}
        disabled={disabled}
        className={`rounded-xl border px-3 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-60 ${className || 'border-slate-200 text-slate-700 hover:bg-slate-50'}`}
      >
        {disabled ? '更新中...' : taskActionLabel(task.status, nextStatus)}
      </button>
    );

    if (task.status === 'done') {
      return (
        <>
          {renderAction('open')}
          {renderAction('archived')}
        </>
      );
    }

    if (task.status === 'snoozed') {
      return (
        <>
          {renderAction('open')}
          {renderAction('done', 'border-emerald-200 text-emerald-700 hover:bg-emerald-50')}
          {renderAction('archived')}
        </>
      );
    }

    if (task.status === 'archived') {
      return <>{renderAction('open')}</>;
    }

    return (
      <>
        {renderAction('done', 'border-emerald-200 text-emerald-700 hover:bg-emerald-50')}
        {renderAction('snoozed', 'border-amber-200 text-amber-700 hover:bg-amber-50')}
        {renderAction('archived')}
      </>
    );
  };

  const renderTaskCard = (task: any) => (
    <div key={task.id} className="rounded-xl border border-slate-200 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold text-slate-900">{task.title}</h3>
            {sourceBadge(task.source_type, task.source_label)}
            {taskKindLabel(task.task_kind) ? (
              <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
                {taskKindLabel(task.task_kind)}
              </span>
            ) : null}
          </div>

          <p className="text-sm text-slate-600">{truncateText(task.description, 160)}</p>
        </div>

        <div className="flex flex-wrap gap-2 text-xs font-semibold">
          <span className={`rounded-full border px-2 py-1 ${priorityBadgeClass(task.priority)}`}>
            {task.priority_display || priorityLabel(task.priority)}
          </span>
          <span className={`rounded-full border px-2 py-1 ${statusBadgeClass(task.status)}`}>
            {task.status_display || statusLabel(task.status)}
          </span>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
        <span>到期：{fmtDateTime(task.due_at)}</span>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">{renderActions(task)}</div>
    </div>
  );

  const empty = emptyCopy(filter);

  return (
    <AppShell title="待辦" subtitle="把真正需要你出手的項目接住，處理後也能自然回到總覽。">
      {loading ? <LoadingState message="正在載入待辦..." /> : null}

      {!loading ? (
        <>
          {refreshNotice ? (
            <div className="mb-6 rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-700">
              {refreshNotice}
            </div>
          ) : null}

          {refreshing ? (
            <div className="mb-6 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              正在更新待辦內容，畫面會保留目前結果。
            </div>
          ) : null}

          {error ? (
            <ErrorState
              message={error}
              action={
                <button
                  onClick={() => void load()}
                  className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  重新載入
                </button>
              }
            />
          ) : null}

          {!error ? (
            <>
              <div className="mb-6 flex flex-wrap gap-2">
                {(['active', 'snoozed', 'done', 'archived', 'all'] as TaskViewFilter[]).map((view) => {
                  const active = filter === view;
                  return (
                    <button
                      key={view}
                      onClick={() => setFilter(view)}
                      className={`rounded-full border px-3 py-2 text-sm font-medium ${
                        active
                          ? 'border-sky-200 bg-sky-50 text-sky-700'
                          : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                      }`}
                    >
                      {filterLabel(view)} {counts[view]}
                    </button>
                  );
                })}
              </div>

              {filteredTasks.length === 0 ? (
                <EmptyState title={empty.title} description={empty.description} />
              ) : (
                <div className="grid gap-6 xl:grid-cols-2">
                  <SectionCard title="郵件跟進">
                    <div className="space-y-4">
                      {grouped.email.length === 0 ? (
                        <SectionEmptyState
                          title={`目前沒有屬於「${filterLabel(filter)}」的郵件待辦。`}
                          description="當這個狀態下有需要保留的郵件項目時，這裡會自動整理出來。"
                        />
                      ) : (
                        grouped.email.map(renderTaskCard)
                      )}
                    </div>
                  </SectionCard>

                  <SectionCard title="行程提醒">
                    <div className="space-y-4">
                      {grouped.calendar.length === 0 ? (
                        <SectionEmptyState
                          title={`目前沒有屬於「${filterLabel(filter)}」的行程提醒。`}
                          description="之後若有接近時間、需要你持續留意或延後處理的安排，這裡會整理出來。"
                        />
                      ) : (
                        grouped.calendar.map(renderTaskCard)
                      )}
                    </div>
                  </SectionCard>
                </div>
              )}
            </>
          ) : null}
        </>
      ) : null}
    </AppShell>
  );
}
