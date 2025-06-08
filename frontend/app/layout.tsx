import type { Metadata } from 'next'; // 從 Next.js 導入 Metadata 類型，用於定義頁面元數據
import './globals.css'; // 保留 Next.js 預設的全域樣式表
import ThemeRegistry from '../components/ThemeRegistry'; // 使用相對路徑導入 ThemeRegistry 元件，用於 MUI 主題設定
// 導入操作模式相關的 Context Provider 和橫幅顯示元件
import { OperationModeProvider } from '../contexts/OperationModeContext';
import OperationModeBanner from '../components/OperationModeBanner';

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
        {/*
          OperationModeProvider 包裹整個應用程式或其主要部分。
          這使得所有子元件都能夠透過 useOperationMode Hook 存取操作模式的狀態。
        */}
        <OperationModeProvider>
          {/* 使用 ThemeRegistry 元件包裹子內容，以應用 MUI 主題 */}
          <ThemeRegistry>
            {/*
              OperationModeBanner 元件在此處被渲染，
              它會根據 OperationModeContext 中的狀態，在頁面頂部顯示相應的提示橫幅。
            */}
            <OperationModeBanner />
            {children} {/* 應用程式的主要頁面內容 */}
          </ThemeRegistry>
        </OperationModeProvider>
      </body>
    </html>
  );
}
