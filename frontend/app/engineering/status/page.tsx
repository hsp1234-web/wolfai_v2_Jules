'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Container from '@mui/material/Container';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Button from '@mui/material/Button';
import Alert from '@mui/material/Alert';
import RefreshIcon from '@mui/icons-material/Refresh';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline'; // 用於未知狀態的圖示

// 基於後端 Pydantic 模型定義的 TypeScript 介面
interface ComponentStatus {
  status: string;
  details?: string;
}

interface SchedulerComponentStatus extends ComponentStatus {
  next_run_time?: string; // ISO 格式的時間字串
}

interface FilesystemComponentStatus extends ComponentStatus {
  temp_dir_path?: string;
}

interface FrontendComponentStatus extends ComponentStatus {
  frontend_url?: string;
}

interface VerboseHealthData {
  overall_status: string;
  database_status: ComponentStatus;
  gemini_api_status: ComponentStatus;
  google_drive_status: ComponentStatus;
  scheduler_status: SchedulerComponentStatus;
  filesystem_status: FilesystemComponentStatus;
  frontend_service_status: FrontendComponentStatus;
  timestamp: string; // ISO 格式的時間字串
}

// 用於渲染狀態 Chip 的輔助元件
const StatusChip: React.FC<{ status: string, details?: string }> = ({ status, details }) => {
  let color: 'success' | 'error' | 'warning' | 'info' | 'default' = 'default';
  let icon: React.ReactElement | undefined = <HelpOutlineIcon />; // 預設為未知狀態圖示

  const lowerStatus = status.toLowerCase();

  if (lowerStatus.includes('正常') || lowerStatus.includes('已配置') || lowerStatus.includes('已初始化') || lowerStatus.includes('運行中') || lowerStatus.includes('可讀寫') || lowerStatus.includes('可達')) {
    color = 'success';
    icon = <CheckCircleOutlineIcon />;
  } else if (lowerStatus.includes('異常') || lowerStatus.includes('失敗') || lowerStatus.includes('錯誤') || lowerStatus.includes('嚴重故障') || lowerStatus.includes('權限異常') || lowerStatus.includes('無法連線') || lowerStatus.includes('未配置') || lowerStatus.includes('未運行')) {
    color = 'error';
    icon = <ErrorOutlineIcon />;
  } else if (lowerStatus.includes('警告') || lowerStatus.includes('部分異常') || lowerStatus.includes('回應異常') || lowerStatus.includes('請求超時') || lowerStatus.includes('設定錯誤')) {
    color = 'warning';
    icon = <WarningAmberOutlinedIcon />;
  } else if (lowerStatus.includes('未知') || lowerStatus.includes('未初始化')) {
    color = 'info';
  }

  return <Chip icon={icon} label={status} color={color} variant="outlined" title={details}/>;
};


export default function HealthDashboardPage() {
  const [healthData, setHealthData] = useState<VerboseHealthData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealthData = useCallback(async (isManualRefresh = false) => {
    // 除非是首次加載，否則不要顯示主加載動畫 (用於背景刷新)
    if (!isManualRefresh) {
        if(healthData === null) setLoading(true);
    } else {
        setLoading(true); // 手動刷新時，總是顯示加載動畫
    }
    setError(null);

    try {
      // 在實際部署中，此 URL 可能需要是絕對路徑或通過環境變數配置
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL || ''}/api/v1/health/verbose`);
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`獲取健康狀態失敗：${response.status} ${response.statusText} - ${errorText}`);
      }
      const data: VerboseHealthData = await response.json();
      setHealthData(data);
    } catch (e: any) {
      logger.error(`獲取健康狀態時發生錯誤：${e.message}`);
      setError(`獲取健康狀態時發生錯誤：${e.message}`);
      // 可選：發生錯誤時清除舊數據，或使其保持過時狀態
      // setHealthData(null);
    } finally {
      setLoading(false);
    }
  }, [healthData]); // healthData 在依賴項中，以正確控制初始加載

  useEffect(() => {
    fetchHealthData(true); // 初始獲取數據，loading 設為 true
    const intervalId = setInterval(() => fetchHealthData(false), 10000); // 每 10 秒刷新一次

    return () => clearInterval(intervalId); // 組件卸載時清除定時器
  }, [fetchHealthData]); // fetchHealthData 已使用 useCallback 記憶

  const formatTimestamp = (isoString?: string) => {
    if (!isoString) return '不適用';
    try {
      return new Date(isoString).toLocaleString('zh-TW', { timeZone: 'Asia/Taipei' });
    } catch {
      return isoString; // 如果解析失敗，返回原始字串
    }
  };

  // 客戶端日誌記錄器 (可選，用於在瀏覽器控制台中調試)
  const logger = {
    info: (...args: any[]) => console.log('[健康儀表板]', ...args),
    error: (...args: any[]) => console.error('[健康儀表板]', ...args),
  };


  if (loading && !healthData) { // 僅在初始加載時顯示全頁加載動畫
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '80vh' }}>
        <CircularProgress size={60} />
        <Typography variant="h6" sx={{ ml: 2 }}>正在載入健康狀態...</Typography>
      </Box>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h4" component="h1">
          系統健康狀態儀表板
        </Typography>
        <Button
          variant="contained"
          onClick={() => fetchHealthData(true)}
          startIcon={<RefreshIcon />}
          disabled={loading && healthData !== null} // 僅在背景加載時禁用
        >
          {loading && healthData !== null ? '刷新中...' : '手動刷新'}
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {!healthData && !loading && !error && (
         <Alert severity="info" sx={{ mb: 2 }}>暫無健康狀態資料可顯示。可能是首次載入或系統無回應。</Alert>
      )}

      {healthData && (
        <Box>
          <Grid container spacing={1} alignItems="center" sx={{ mb: 2 }}>
            <Grid item>
              <Typography variant="h6">總體狀態:</Typography>
            </Grid>
            <Grid item>
              <StatusChip status={healthData.overall_status} />
            </Grid>
            <Grid item xs={12} sm>
               <Typography variant="body2" color="textSecondary" sx={{textAlign: {sm: 'right'}}}>
                最後更新時間 (台北): {formatTimestamp(healthData.timestamp)}
              </Typography>
            </Grid>
          </Grid>

          <Grid container spacing={3}>
            {/* 資料庫狀態 */}
            <Grid item xs={12} sm={6} md={4}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>資料庫狀態</Typography>
                  <StatusChip status={healthData.database_status.status} details={healthData.database_status.details} />
                  {healthData.database_status.details && <Typography variant="body2" sx={{ mt: 1 }}>{healthData.database_status.details}</Typography>}
                </CardContent>
              </Card>
            </Grid>

            {/* Gemini AI 服務狀態 */}
            <Grid item xs={12} sm={6} md={4}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>Gemini AI 服務</Typography>
                  <StatusChip status={healthData.gemini_api_status.status} details={healthData.gemini_api_status.details} />
                  {healthData.gemini_api_status.details && <Typography variant="body2" sx={{ mt: 1 }}>{healthData.gemini_api_status.details}</Typography>}
                </CardContent>
              </Card>
            </Grid>

            {/* Google Drive 服務狀態 */}
            <Grid item xs={12} sm={6} md={4}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>Google Drive 服務</Typography>
                  <StatusChip status={healthData.google_drive_status.status} details={healthData.google_drive_status.details} />
                  {healthData.google_drive_status.details && <Typography variant="body2" sx={{ mt: 1 }}>{healthData.google_drive_status.details}</Typography>}
                </CardContent>
              </Card>
            </Grid>

            {/* 排程器狀態 */}
            <Grid item xs={12} sm={6} md={4}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>排程器狀態</Typography>
                  <StatusChip status={healthData.scheduler_status.status} details={healthData.scheduler_status.details} />
                  {healthData.scheduler_status.details && <Typography variant="body2" sx={{ mt: 1 }}>{healthData.scheduler_status.details}</Typography>}
                  {healthData.scheduler_status.next_run_time && (
                    <Typography variant="body2" sx={{ mt: 1 }}>下次運行 (UTC): {formatTimestamp(healthData.scheduler_status.next_run_time)}</Typography>
                  )}
                </CardContent>
              </Card>
            </Grid>

            {/* 檔案系統狀態 */}
            <Grid item xs={12} sm={6} md={4}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>檔案系統 (暫存區)</Typography>
                  <StatusChip status={healthData.filesystem_status.status} details={healthData.filesystem_status.details} />
                  {healthData.filesystem_status.temp_dir_path && <Typography variant="body2" sx={{ mt: 1 }}>路徑: {healthData.filesystem_status.temp_dir_path}</Typography>}
                  {healthData.filesystem_status.details && <Typography variant="body2" sx={{ mt: 1 }}>{healthData.filesystem_status.details}</Typography>}
                </CardContent>
              </Card>
            </Grid>

            {/* 前端服務狀態 */}
            <Grid item xs={12} sm={6} md={4}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>前端服務 (自身探測)</Typography>
                  <StatusChip status={healthData.frontend_service_status.status} details={healthData.frontend_service_status.details} />
                   {healthData.frontend_service_status.frontend_url && <Typography variant="body2" sx={{ mt: 1 }}>探測 URL: {healthData.frontend_service_status.frontend_url}</Typography>}
                  {healthData.frontend_service_status.details && <Typography variant="body2" sx={{ mt: 1 }}>{healthData.frontend_service_status.details}</Typography>}
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Box>
      )}
    </Container>
  );
}
