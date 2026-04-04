import Link from 'next/link';

export default function HomePage() {
  return (
    <main className="min-h-screen bg-slate-50 text-slate-900">
      <section className="mx-auto max-w-6xl px-6 py-20">
        <div className="max-w-3xl">
          <div className="text-sm font-semibold text-brand-600">順流 ClearFlow</div>
          <h1 className="mt-4 text-4xl font-bold tracking-tight sm:text-5xl">讓工作不再散亂的 AI 工作流助理</h1>
          <p className="mt-6 text-lg leading-8 text-slate-600">
            整合郵件、行程、文件與待辦，幫你先整理重點、減少混亂、少花時間找事情。
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/onboarding" className="rounded-xl bg-brand-600 px-5 py-3 text-sm font-semibold text-white hover:bg-brand-500">立即開始免費體驗</Link>
            <Link href="/pricing" className="rounded-xl border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-white">查看方案與價格</Link>
          </div>
        </div>
        <div className="mt-16 grid gap-4 md:grid-cols-3">
          <div className="card p-5"><h2 className="font-semibold">看懂今天要做什麼</h2><p className="mt-2 text-sm text-slate-600">每天先幫你整理今天的重點、行程、待辦與跟進事項。</p></div>
          <div className="card p-5"><h2 className="font-semibold">把零散資訊變成可執行項目</h2><p className="mt-2 text-sm text-slate-600">不是只有摘要，而是幫你整理出真正要做的事。</p></div>
          <div className="card p-5"><h2 className="font-semibold">用受控方式協助你</h2><p className="mt-2 text-sm text-slate-600">先整理、先建議，再由你確認，不亂碰高風險操作。</p></div>
        </div>
      </section>
    </main>
  );
}
