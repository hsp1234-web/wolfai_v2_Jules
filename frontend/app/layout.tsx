import type { Metadata } from 'next'; // 從 Next.js 導入 Metadata 類型，用於定義頁面元數據
import './globals.css'; // 保留 Next.js 預設的全域樣式表
import ThemeRegistry from '../components/ThemeRegistry'; // 使用相對路徑導入 ThemeRegistry 元件，用於 MUI 主題設定

// 定義應用程式的元數據
export const metadata: Metadata = {
  title: '蒼狼 AI V2.2', // 應用程式標題
  description: '蒼狼 AI 可觀測性與週報分析平台', // 應用程式描述
};

// 定義根佈局 (RootLayout) 元件
export default function RootLayout({
  children, // 子元件，由 Next.js 自動傳入
}: {
  children: React.ReactNode; // 定義 children 的類型為 React 節點
}) {
  return (
    // 設定 HTML 根元素的語言為繁體中文
    <html lang="zh-TW">
      <body>
        {/* 使用 ThemeRegistry 元件包裹子內容，以應用 MUI 主題 */}
        <ThemeRegistry>
          {children}
        </ThemeRegistry>
      </body>
    </html>
  );
}
