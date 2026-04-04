'use client';

import Link from 'next/link';
import { onboardingTemplates } from '@/lib/mock-data';

export default function OnboardingPage() {
  return (
    <main className="min-h-screen bg-slate-50 px-6 py-12">
      <div className="mx-auto max-w-4xl">
        <div className="mb-8">
          <div className="text-sm font-semibold text-brand-600">Step 1 / 3</div>
          <h1 className="mt-2 text-3xl font-bold">選擇你的工作型態</h1>
          <p className="mt-2 text-slate-600">先套用一組最接近你的預設模板。第一版會先保留為前端選擇，後續會再正式寫回後端。</p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {onboardingTemplates.map((template) => (
            <div key={template.key} className="card p-5">
              <h2 className="text-lg font-semibold">{template.name}</h2>
              <p className="mt-2 text-sm text-slate-600">{template.description}</p>
              <div className="mt-5 flex justify-between gap-3">
                <span className="rounded-full bg-slate-100 px-3 py-2 text-xs font-medium text-slate-600">
                  目前先做畫面選擇，後續再正式保存模板
                </span>
                <Link href="/sources" className="rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-500">
                  套用並前往連接來源
                </Link>
              </div>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
