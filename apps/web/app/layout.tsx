import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: '順流 ClearFlow',
  description: '受控、安全的 AI 工作流助理',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-Hant">
      <body>{children}</body>
    </html>
  );
}
