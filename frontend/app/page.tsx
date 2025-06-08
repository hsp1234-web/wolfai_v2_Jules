// 'use client'; // 如果此頁面僅渲染客戶端元件，則 page.tsx 可以保持為伺服器元件。
// 如果有互動邏輯直接在此頁面，則需要取消註解 'use client'。

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import SettingsCard from '../components/SettingsCard'; // 使用相對路徑導入 SettingsCard 元件
import Container from '@mui/material/Container'; // MUI 容器元件，用於限制最大寬度並居中內容

// 導出預設的 HomePage 元件
export default function HomePage() {
  return (
    // 使用 Container 元件包裹頁面內容，設定最大寬度為 'lg'
    <Container maxWidth="lg">
      <Box
        sx={{
          my: 4, // 上下邊距 (margin top and bottom)
          display: 'flex', // 使用 Flexbox 佈局
          flexDirection: 'column', // 子項目垂直排列
          justifyContent: 'center', // 垂直方向居中對齊
          alignItems: 'center', // 水平方向居中對齊
        }}
      >
        {/* 頁面主標題 */}
        <Typography variant="h3" component="h1" gutterBottom sx={{
          textAlign: 'center', // 文字居中
          fontWeight: 'bold', // 字體加粗
          color: 'primary.main', // 使用佈景主題的主色
          mb: 4 // 下邊距 (margin bottom)
        }}>
          蒼狼 AI 可觀測性分析平台 V2.2
        </Typography>

        {/* 渲染 SettingsCard 元件 */}
        <SettingsCard />

      </Box>
    </Container>
  );
}
