'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const items = [
  { href: '/dashboard', label: '總覽' },
  { href: '/summaries', label: '摘要' },
  { href: '/tasks', label: '待辦' },
  { href: '/sources', label: '來源' },
  { href: '/settings', label: '設定' },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-64 shrink-0 border-r border-slate-200 bg-white xl:block">
      <div className="px-6 py-6">
        <div className="text-lg font-bold text-brand-600">順流 ClearFlow</div>
        <p className="mt-1 text-sm text-slate-500">AI 工作流助理</p>
      </div>
      <nav className="space-y-1 px-3 pb-6">
        {items.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`block rounded-xl px-4 py-3 text-sm font-medium transition ${
                active ? 'bg-brand-50 text-brand-700' : 'text-slate-700 hover:bg-slate-100'
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
