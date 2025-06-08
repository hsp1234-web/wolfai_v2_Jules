'use client'; // 標記為客戶端使用，儘管主題定義本身是配置，但在客戶端元件中使用
import { createTheme } from '@mui/material/styles'; // 從 MUI 導入 createTheme 函數
import { Roboto } from 'next/font/google'; // 從 Next.js 導入 Google 字體 'Roboto'

// 配置 Roboto 字體
const roboto = Roboto({
  weight: ['300', '400', '500', '700'], // 需要的字體粗細
  subsets: ['latin'], // 字體子集，'latin' 適用於英語等西方語言
  display: 'swap', // 字體顯示策略，'swap' 表示先顯示後備字體，字體加載完成後再替換
});

// 創建並配置 MUI 主題
const theme = createTheme({
  palette: { // 調色板配置
    mode: 'light', // 主題模式，可以是 'light' 或 'dark'
    primary: { main: '#6750A4' }, // 主色調 (示例：Material You 紫色)
    secondary: { main: '#625B71' }, // 次要色調 (示例)
    error: { main: '#B3261E' }, // 錯誤狀態顏色 (示例)
    background: { // 背景顏色配置
      default: '#FFFBFE', // 預設背景色
      paper: '#FFFBFE'    // Paper 元件 (如 Card) 的背景色
    },
  },
  typography: { // 排版配置
    fontFamily: roboto.style.fontFamily, // 設定應用程式的預設字體為 Roboto
  },
  shape: { // 形狀配置
    borderRadius: 16, // 元件 (如 Card, Button) 的邊框圓角半徑 (示例值)
  },
  // 可以在此處添加更多自訂主題選項，例如 components overrides
  // components: {
  //   MuiButton: {
  //     styleOverrides: {
  //       root: {
  //         textTransform: 'none', // 例如：按鈕文字不大寫
  //       }
  //     }
  //   }
  // }
});

// 導出配置好的主題
export default theme;
