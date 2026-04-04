'use client';

import { ReactNode } from 'react';
import { AuthGuard } from '@/components/auth-guard';
import { Sidebar } from '@/components/sidebar';
import { Topbar } from '@/components/topbar';

export function AppShell({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <AuthGuard>
      <div className="min-h-screen bg-slate-50 xl:flex">
        <Sidebar />
        <div className="min-w-0 flex-1">
          <Topbar title={title} subtitle={subtitle} />
          <main className="p-6">{children}</main>
        </div>
      </div>
    </AuthGuard>
  );
}
