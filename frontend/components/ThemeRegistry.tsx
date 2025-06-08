'use client'; // 標記為客戶端元件，因為它使用了 React hooks 和上下文 (ThemeProvider)
import * as React from 'react';
import { ThemeProvider } from '@mui/material/styles'; // MUI 主題供應器
import CssBaseline from '@mui/material/CssBaseline'; // MUI CSS 基礎樣式重置
import NextAppDirEmotionCacheProvider from './EmotionCache'; // Emotion 快取供應器，用於 Next.js App Router
import theme from './theme'; // 導入自訂的 MUI 主題配置

// ThemeRegistry 元件：設定並提供 MUI 主題給應用程式
export default function ThemeRegistry({ children }: { children: React.ReactNode }) {
  return (
    // NextAppDirEmotionCacheProvider 用於處理 Emotion 在 Next.js App Router 中的樣式快取
    // options={{ key: 'mui' }} 指定 Emotion 快取的鍵名，通常保持為 'mui'
    <NextAppDirEmotionCacheProvider options={{ key: 'mui' }}>
      {/* ThemeProvider 將自訂的 theme 應用到其所有子元件 */}
      <ThemeProvider theme={theme}>
        {/* CssBaseline 提供一個優雅、一致的 HTML 元素基線樣式 */}
        <CssBaseline />
        {/* 渲染子元件 */}
        {children}
      </ThemeProvider>
    </NextAppDirEmotionCacheProvider>
  );
}
