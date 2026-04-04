'use client';

import { useEffect, useState } from 'react';
import { AppShell } from '@/components/app-shell';
import { ErrorState, LoadingState } from '@/components/page-state';
import { SectionCard } from '@/components/stat-card';
import { getSettings, updateNotifications } from '@/lib/api';

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

export default function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [settings, setSettings] = useState<any | null>(null);
  const [preferredHour, setPreferredHour] = useState(8);
  const [dailySummaryEnabled, setDailySummaryEnabled] = useState(true);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await getSettings();
      setSettings(result);
      setPreferredHour(result.notification_preferences?.preferred_hour ?? 8);
      setDailySummaryEnabled(result.notification_preferences?.daily_summary_enabled ?? true);
    } catch (err) {
      setError(err instanceof Error ? err.message : '設定載入失敗');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleSaveNotifications = async () => {
    try {
      setSaving(true);
      setError(null);
      await updateNotifications({
        daily_summary_enabled: dailySummaryEnabled,
        preferred_hour: preferredHour,
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : '通知設定儲存失敗');
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppShell title="設定" subtitle="管理個人資料、方案、通知與來源設定。">
      {loading ? <LoadingState message="正在載入設定..." /> : null}
      {error ? (
        <ErrorState
          message={error}
          action={
            <button onClick={load} className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
              重新載入
            </button>
          }
        />
      ) : null}

      {!loading && !error && settings ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <SectionCard title="個人資料">
            <div className="space-y-3 text-sm text-slate-700">
              <div><span className="font-medium">時區：</span>{settings.profile.timezone}</div>
              <div><span className="font-medium">語系：</span>{settings.profile.locale}</div>
              <div><span className="font-medium">模板：</span>{settings.profile.work_template_key || '未設定（第一版尚未正式保存）'}</div>
              <div><span className="font-medium">Onboarding：</span>{settings.profile.onboarding_completed ? '已完成' : '未完成'}</div>
              <div className="text-xs text-slate-500">
                第一版會在「成功連接第一個來源」或「成功生成第一份摘要」後，自動視為完成 onboarding。
              </div>
            </div>
          </SectionCard>

          <SectionCard title="目前方案">
            <div className="space-y-3 text-sm text-slate-700">
              <div><span className="font-medium">方案：</span>{settings.plan.plan_name}</div>
              <div><span className="font-medium">AI 額度：</span>{settings.usage.monthly_ai_usage} / {settings.usage.monthly_ai_quota}</div>
            </div>
          </SectionCard>

          <SectionCard title="通知偏好">
            <div className="space-y-4 text-sm text-slate-700">
              <label className="flex items-center gap-3">
                <input type="checkbox" checked={dailySummaryEnabled} onChange={(e) => setDailySummaryEnabled(e.target.checked)} />
                <span>啟用每日摘要</span>
              </label>
              <label className="block">
                <div className="mb-2 font-medium">偏好時間</div>
                <input
                  type="number"
                  min={0}
                  max={23}
                  value={preferredHour}
                  onChange={(e) => setPreferredHour(Number(e.target.value))}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 outline-none focus:border-brand-400"
                />
              </label>
              <button
                onClick={handleSaveNotifications}
                disabled={saving}
                className="rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {saving ? '儲存中...' : '儲存通知設定'}
              </button>
            </div>
          </SectionCard>

          <SectionCard title="已連接來源">
            <div className="space-y-3 text-sm text-slate-700">
              {settings.integrations.length === 0 ? (
                <div>尚未連接任何來源</div>
              ) : (
                settings.integrations.map((integration: any) => (
                  <div key={integration.id} className="rounded-xl border border-slate-200 p-3">
                    <div className="font-medium text-slate-900">{providerLabel(integration.provider_key)}</div>
                    <div className="mt-1 text-xs text-slate-500">狀態：{integration.status}</div>
                  </div>
                ))
              )}
            </div>
          </SectionCard>
        </div>
      ) : null}
    </AppShell>
  );
}
