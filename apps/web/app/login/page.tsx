'use client';

import { useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { devLogin } from '@/lib/api';
import { setAccessToken } from '@/lib/auth';

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams.get('next') || '/dashboard';
  const [devCode, setDevCode] = useState('dev_clearflow_user');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDevLogin = async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await devLogin(devCode.trim() || 'dev_clearflow_user');
      setAccessToken(result.access_token);
      router.replace(nextPath);
    } catch (err) {
      setError(err instanceof Error ? err.message : '登入失敗，請稍後再試。');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 px-6 py-12">
      <div className="mx-auto max-w-md rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="text-sm font-semibold text-brand-600">順流 ClearFlow</div>
        <h1 className="mt-3 text-3xl font-bold text-slate-900">開始使用順流</h1>
        <p className="mt-2 text-sm text-slate-600">先用開發模式登入，驗證前後端第一版串接流程。</p>

        <label className="mt-6 block text-sm font-medium text-slate-700">開發模式代碼</label>
        <input
          value={devCode}
          onChange={(e) => setDevCode(e.target.value)}
          className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-brand-400"
          placeholder="dev_clearflow_user"
        />

        <p className="mt-2 text-xs text-slate-500">後端需啟用 DEV_OAUTH_BYPASS=true。</p>

        {error ? <div className="mt-4 rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-600">{error}</div> : null}

        <button
          onClick={handleDevLogin}
          disabled={loading}
          className="mt-6 w-full rounded-2xl bg-brand-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-brand-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? '登入中...' : '使用開發模式登入'}
        </button>
      </div>
    </main>
  );
}
