import type { Metadata } from 'next';
import './globals.css'; // Keep Next.js default global styles
import ThemeRegistry from '../components/ThemeRegistry'; // Relative path

export const metadata: Metadata = {
  title: 'Wolf AI V2.2',
  description: 'AI 報告分析平台',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-TW">
      <body>
        <ThemeRegistry>
          {children}
        </ThemeRegistry>
      </body>
    </html>
  );
}
