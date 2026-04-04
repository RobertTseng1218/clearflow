'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { hasAccessToken } from '@/lib/auth';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const tokenExists = hasAccessToken();
    if (!tokenExists) {
      router.replace(`/login?next=${encodeURIComponent(pathname || '/dashboard')}`);
      return;
    }
    setChecked(true);
  }, [pathname, router]);

  if (!checked) {
    return <div className="card p-6 text-sm text-slate-500">正在檢查登入狀態...</div>;
  }

  return <>{children}</>;
}
