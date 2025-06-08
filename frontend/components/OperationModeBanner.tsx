// frontend/components/OperationModeBanner.tsx
// 此元件用於根據應用程式的當前操作模式，在頁面頂部顯示一個提示橫幅。
'use client'; // 標記為客戶端元件

import React from 'react';
import { useOperationMode } from '../contexts/OperationModeContext'; // 導入用於獲取操作模式的 Hook
import Alert from '@mui/material/Alert'; // MUI Alert 元件，用於顯示提示訊息
import Box from '@mui/material/Box'; // MUI Box 元件，用於佈局
import CircularProgress from '@mui/material/CircularProgress'; // MUI 進度指示器元件
import Typography from '@mui/material/Typography'; // MUI 文字排版元件

const OperationModeBanner: React.FC = () => {
  // 使用 useOperationMode Hook 從 Context 中獲取操作模式 (mode) 和加載狀態 (isLoadingMode)。
  const { mode, isLoadingMode } = useOperationMode();

  // 情況 1: 如果正在加載操作模式 (isLoadingMode 為 true)
  // 顯示一個包含進度圈和文字的輕量級提示。
  if (isLoadingMode) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', p: 1, backgroundColor: 'rgba(0, 0, 0, 0.05)' }}>
        <CircularProgress size={20} sx={{ mr: 1 }} /> {/* 小尺寸的進度圈 */}
        <Typography variant="body2">正在偵測操作模式...</Typography> {/* 提示文字 */}
      </Box>
    );
  }

  // 情況 2: 如果操作模式為 "transient" (暫存模式)
  // 顯示一個警告橫幅，提醒使用者資料不會被保存。
  if (mode === 'transient') {
    return (
      // Alert 元件：嚴重性為 "warning"，無圓角 (borderRadius: 0)，無底部外邊距 (mb: 0)，文字居中。
      <Alert severity="warning" sx={{ borderRadius: 0, mb: 0, textAlign: 'center' }}>
        您目前處於 **暫存模式**，所有資料將在連線階段結束後遺失。如需永久保存，請返回 Colab 筆記本並選擇「持久模式」重新啟動服務。
      </Alert>
    );
  }

  // 情況 3: 操作模式為 "persistent" (持久模式) 或其他情況 (例如 mode 為 null 但 isLoadingMode 為 false)
  // 在持久模式下，可以選擇顯示一個成功訊息的橫幅 (如下面註解掉的程式碼所示)，
  // 或者，如此處實現，不顯示任何橫幅，以保持介面簡潔。
  // else if (mode === 'persistent') {
  //   return (
  //     <Alert severity="success" sx={{ borderRadius: 0, mb: 0, textAlign: 'center' }}>
  //       您目前處於 **持久模式**，資料將會保存。
  //     </Alert>
  //   );
  // }

  // 預設情況下 (例如，持久模式或 mode 尚未確定但已結束加載)，不渲染任何內容。
  return null;
};

export default OperationModeBanner;
