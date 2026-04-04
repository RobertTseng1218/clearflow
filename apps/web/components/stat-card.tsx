import { ReactNode } from 'react';

export function StatCard({ title, value, note }: { title: string; value: string; note?: string }) {
  return (
    <div className="card p-5">
      <div className="card-title">{title}</div>
      <div className="mt-3 text-2xl font-bold text-slate-900">{value}</div>
      {note ? <p className="mt-2 text-sm text-slate-500">{note}</p> : null}
    </div>
  );
}

export function SectionCard({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="card p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-slate-900">{title}</h2>
        {action}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}
