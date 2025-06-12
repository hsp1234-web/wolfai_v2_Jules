'use client';

import { useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import SettingsCard from '../components/SettingsCard'; // 使用相對路徑導入 SettingsCard 元件
import DataSelectionForm from '../components/DataSelectionForm'; // Added DataSelectionForm
import Container from '@mui/material/Container'; // MUI 容器元件，用於限制最大寬度並居中內容
import ReportTabs from '../components/ReportTabs'; // Adjust path if necessary

// 導出預設的 HomePage 元件
export default function HomePage() {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleGenerateReport = async () => {
    setLoading(true);
    setReport(null); // Clear previous report
    try {
      const apiUrl = `${process.env.NEXT_PUBLIC_API_BASE_URL}/api/v1/reports/generate`;
      const response = await fetch(apiUrl, {
        method: 'POST',
        // Add headers if required by the API, e.g., Content-Type
        // headers: {
        //   'Content-Type': 'application/json',
        // },
        // Add body if required by the API
        // body: JSON.stringify({ /* your payload here */ }),
      });

      if (response.ok) {
        const data = await response.json();
        setReport(data);
      } else {
        console.error('Failed to generate report:', response.status, response.statusText);
        // Optionally, set an error state here to display to the user
        // For example: setError(`Error: ${response.status} ${response.statusText}`);
      }
    } catch (error) {
      console.error('Error during report generation:', error);
      // Optionally, set an error state here
      // For example: setError(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

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
        <DataSelectionForm /> {/* Added DataSelectionForm here */}

        {/* 生成報告按鈕 */}
        <Button
          variant="contained"
          onClick={handleGenerateReport}
          disabled={loading}
          sx={{ mt: 2 }} // 上邊距 (margin top)
        >
          {loading ? '報告生成中...' : '生成深度策略分析報告'}
        </Button>

        {/* 顯示報告內容 */}
        {report && (
          <Box sx={{ mt: 4, width: '100%' }}>
            {/* Typography for the section title can be kept or removed based on how ReportTabs itself handles titles */}
            {/* For instance, if ReportTabs has its own main title, this Typography might be redundant */}
            {/* <Typography variant="h5" component="h2" gutterBottom>
              分析報告:
            </Typography> */}
            <ReportTabs report={report} />
          </Box>
        )}
      </Box>
    </Container>
  );
}
