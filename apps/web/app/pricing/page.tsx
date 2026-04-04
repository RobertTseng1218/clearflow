import Link from 'next/link';

const plans = [
  { name: '免費版', price: 'NT$0', desc: '體驗順流核心價值', cta: '免費開始' },
  { name: '個人版', price: 'NT$349 / 月', desc: '個人工作整理與提醒', cta: '選擇個人版' },
  { name: '專業個人版', price: 'NT$499 / 月', desc: '更高頻率與更深整理能力', cta: '升級專業版' },
  { name: '團隊 Lite', price: 'NT$299 / 人 / 月', desc: '3–5 人共享工作流', cta: '開始團隊 Lite' },
];

export default function PricingPage() {
  return (
    <main className="min-h-screen bg-slate-50 px-6 py-16">
      <div className="mx-auto max-w-6xl">
        <h1 className="text-4xl font-bold tracking-tight">選擇最適合你的順流 ClearFlow 方案</h1>
        <p className="mt-3 text-slate-600">從個人工作整理到小團隊共享工作流，依照你的需求選擇方案。</p>
        <div className="mt-10 grid gap-5 lg:grid-cols-4">
          {plans.map((plan) => (
            <div key={plan.name} className="card flex flex-col p-6">
              <h2 className="text-lg font-semibold">{plan.name}</h2>
              <div className="mt-3 text-2xl font-bold">{plan.price}</div>
              <p className="mt-3 flex-1 text-sm text-slate-600">{plan.desc}</p>
              <Link href="/onboarding" className="mt-6 rounded-xl bg-brand-600 px-4 py-3 text-center text-sm font-semibold text-white hover:bg-brand-500">{plan.cta}</Link>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
