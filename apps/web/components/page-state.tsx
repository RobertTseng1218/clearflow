import { ReactNode } from 'react';

export function LoadingState({ message = '正在載入資料...' }: { message?: string }) {
  return <div className="card p-6 text-sm text-slate-500">{message}</div>;
}

export function ErrorState({ message, action }: { message: string; action?: ReactNode }) {
  return (
    <div className="card p-6">
      <div className="text-sm font-medium text-rose-600">{message}</div>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function EmptyState({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="card p-8 text-center">
      <div className="text-base font-semibold text-slate-900">{title}</div>
      {description ? <div className="mt-2 text-sm text-slate-600">{description}</div> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
