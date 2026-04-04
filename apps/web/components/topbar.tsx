'use client';

import { useEffect, useState } from 'react';
import { clearAccessToken } from '@/lib/auth';
import { getPlan, getUsage } from '@/lib/api';

type TopbarProps = {
  title: string;
  subtitle?: string;
};

export function Topbar({ title, subtitle }: TopbarProps) {
  const [planName, setPlanName] = useState('—');
  const [usageText, setUsageText] = useState('—');

  useEffect(() => {
    let mounted = true;
    Promise.allSettled([getPlan(), getUsage()]).then(([planRes, usageRes]) => {
      if (!mounted) return;
      if (planRes.status === 'fulfilled') setPlanName(planRes.value.plan_name || '—');
      if (usageRes.status === 'fulfilled') {
        setUsageText(`${usageRes.value.monthly_ai_usage} / ${usageRes.value.monthly_ai_quota}`);
      }
    });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <header className="flex flex-col gap-3 border-b border-slate-200 bg-white px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">{title}</h1>
        {subtitle ? <p className="mt-1 text-sm text-slate-500">{subtitle}</p> : null}
      </div>
      <div className="flex items-center gap-3">
        <span className="rounded-full bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-600">{planName}</span>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">AI {usageText}</span>
        <button
          onClick={() => {
            clearAccessToken();
            window.location.href = '/login';
          }}
          className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          登出
        </button>
      </div>
    </header>
  );
}
