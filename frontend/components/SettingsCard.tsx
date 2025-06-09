'use client'; // 標記為客戶端元件

import React, { useState, useEffect, useCallback } from 'react';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import TextField from '@mui/material/TextField';
import Button from '@mui/material/Button';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Select, { SelectChangeEvent } from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import CircularProgress from '@mui/material/CircularProgress';
import Box from '@mui/material/Box';
import Alert from '@mui/material/Alert';
import { useOperationMode } from '../contexts/OperationModeContext'; // 導入用於獲取操作模式狀態的 Hook

interface ApiKeyStatus {
  is_set: boolean;
  source: string | null;
  drive_service_account_loaded?: boolean; // 新增此欄位以匹配後端回應 (用於健康檢查/API狀態)
}

const SettingsCard: React.FC = () => {
  // 從 OperationModeContext 獲取當前操作模式 (mode) 和模式加載狀態 (isLoadingMode)。
  // 這將決定是否顯示以及如何顯示 Google Drive 相關的設定狀態。
  const { mode, isLoadingMode } = useOperationMode();
  // API 金鑰狀態
  const [apiKeyInput, setApiKeyInput] = useState<string>('');
  const [apiKeyStatus, setApiKeyStatus] = useState<ApiKeyStatus | null>(null);
  const [isKeyLoading, setIsKeyLoading] = useState<boolean>(true);
  const [keyError, setKeyError] = useState<string | null>(null);
  const [isSubmittingKey, setIsSubmittingKey] = useState<boolean>(false);

  // AI 模型選擇狀態
  const [selectedModel, setSelectedModel] = useState<string>('gemini-pro'); // 預設選擇的模型
  const availableModels = [ // 可用的 AI 模型列表
    { id: 'gemini-pro', name: 'Gemini Pro (預設)' },
    { id: 'gpt-4-turbo', name: 'GPT-4 Turbo' }, // 示例：未來可能支援的模型
    { id: 'claude-3-opus', name: 'Claude 3 Opus' }, // 示例：未來可能支援的模型
  ];

  // useCallback 用於快取函數，避免不必要的重渲染
  const fetchApiKeyStatus = useCallback(async () => {
    setIsKeyLoading(true);
    setKeyError(null); // 清除先前的錯誤
    try {
      const response = await fetch('/api/get_api_key_status'); // 指向 Next.js 後端 API 路由
      if (!response.ok) {
        // 嘗試解析錯誤回應體，如果後端有提供 JSON 格式的錯誤細節
        const errorData = await response.json().catch(() => null);
        const errorMessage = errorData?.detail || `HTTP 錯誤 ${response.status}: ${response.statusText}`;
        throw new Error(`獲取 API 金鑰狀態失敗: ${errorMessage}`);
      }
      const data: ApiKeyStatus = await response.json();
      setApiKeyStatus(data);
    } catch (error) {
      console.error('獲取 API 金鑰狀態時發生錯誤:', error); // 詳細記錄錯誤到控制台
      const displayError = error instanceof Error ? error.message : '獲取金鑰狀態時發生未知網路錯誤';
      setKeyError(displayError);
      // 在發生錯誤時，可以設定一個表示錯誤狀態的 ApiKeyStatus
      setApiKeyStatus({ is_set: false, source: null, drive_service_account_loaded: false });
    } finally {
      setIsKeyLoading(false); // 無論成功或失敗，都結束加載狀態
    }
  }, []); // 空依賴數組表示此函數在元件的生命週期內不變

  useEffect(() => {
    fetchApiKeyStatus(); // 元件掛載時獲取一次 API 金鑰狀態
  }, [fetchApiKeyStatus]);

  const handleSetApiKey = async () => { // 處理設定 API 金鑰的邏輯
    if (!apiKeyInput.trim()) { // 簡單的前端驗證
      setKeyError('API 金鑰欄位不能為空。請貼上您的金鑰。');
      return;
    }
    setIsSubmittingKey(true); // 開始提交，禁用按鈕等
    setKeyError(null); // 清除舊的錯誤訊息
    try {
      const response = await fetch('/api/set_api_key', { // 發送 POST 請求到後端
        method: 'POST',
        headers: { // 設定請求標頭
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ api_key: apiKeyInput }), // 將金鑰包裝在請求體中
      });
      if (!response.ok) { // 檢查回應狀態碼
        // 嘗試解析後端返回的 JSON 錯誤訊息
        const errorData = await response.json().catch(() => ({ detail: '設定金鑰失敗，且無法從伺服器解析具體錯誤原因。' }));
        throw new Error(errorData.detail || `設定金鑰時發生伺服器錯誤: ${response.status} ${response.statusText}`);
      }
      // const result: ApiKeyStatus = await response.json(); // 後端 set_api_key 也返回 ApiKeyStatusResponse
      // setApiKeyStatus(result); // 可以用返回的狀態直接更新，或者重新獲取
      setApiKeyInput(''); // 清空輸入框
      await fetchApiKeyStatus(); // 重新獲取金鑰狀態以確認更新
      alert('API 金鑰已成功設定！'); // 簡單提示用戶成功
    } catch (error) {
      console.error('設定 API 金鑰時發生錯誤:', error);
      const displayError = error instanceof Error ? error.message : '設定金鑰過程中發生未知網路錯誤';
      setKeyError(displayError);
    } finally {
      setIsSubmittingKey(false); // 結束提交狀態
    }
  };

  const handleModelChange = (event: SelectChangeEvent<string>) => { // 處理模型選擇變更
    setSelectedModel(event.target.value as string); // 更新選擇的模型 ID
  };

  return (
    <Card sx={{ maxWidth: 600, margin: 'auto', mt: 4 }}>
      <CardContent>
        <Typography variant="h5" component="div" gutterBottom sx={{ textAlign: 'center' }}>
          系統設定
        </Typography>

        {/* API 金鑰設定區塊 */}
        <Box sx={{ mb: 3, p: 2, border: '1px solid #e0e0e0', borderRadius: '4px' }}>
          <Typography variant="h6" gutterBottom>
            Google API 金鑰管理 (用於 Gemini 等服務)
          </Typography>
          {isKeyLoading ? ( // 若正在加載金鑰狀態，顯示進度圈
            <Box sx={{ display: 'flex', justifyContent: 'center', my: 2 }}><CircularProgress /></Box>
          ) : keyError && !apiKeyStatus?.is_set ? ( // 若加載出錯且金鑰未設定，顯示錯誤提示
            <Alert severity="error" sx={{ mb: 1 }}>{keyError}</Alert>
          ) : null}

          {apiKeyStatus?.is_set ? ( // 若金鑰已設定，顯示成功提示
            <Alert severity="success" sx={{ mb: 1 }}>
              Google API 金鑰已設定 (來源: {apiKeyStatus.source === 'environment' ? '環境變數' :
                                 apiKeyStatus.source === 'user_provided' ? '使用者輸入' :
                                 apiKeyStatus.source ? apiKeyStatus.source : '未知'})。
            </Alert>
          ) : ( // 若金鑰未設定，顯示輸入區域
            <>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                系統需要有效的 Google API 金鑰 (例如用於 Gemini 模型) 以執行 AI 分析任務。
                此金鑰可以從您的 Google Cloud 控制台獲取。
                如果後端已配置環境變數，則此處無需手動設定。
                注意：貼上的金鑰將用於後續的 AI 請求。如果貼上的是 Google 服務帳號 JSON 內容，系統也會嘗試用其設定 Google Drive 存取權限（如果尚未從環境變數加載）。
              </Typography>
              {(!apiKeyStatus?.is_set || (apiKeyStatus?.is_set && apiKeyStatus?.source !== 'environment')) && (
                <Alert severity="info" sx={{ mb: 1 }}>
                  <strong>提示：</strong>為了增強安全性並避免重複輸入，建議您優先在 Colab 的「金鑰」(Secrets) 功能中設定名為 <code>COLAB_GOOGLE_API_KEY</code> 的金鑰。
                  在 Colab Notebook 頁面，點擊左側工具列的鑰匙圖示 (🔑) 即可找到金鑰管理介面。
                  如果已在此處設定，則無需在下方欄位手動輸入。
                </Alert>
              )}
              <TextField
                fullWidth
                label="貼上您的 Google API 金鑰或服務帳號 JSON"
                variant="outlined"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                sx={{ mb: 1 }}
                disabled={isSubmittingKey} // 提交時禁用輸入框
                error={!!keyError && apiKeyInput.length > 0 && !apiKeyStatus?.is_set} // 輸入時若有錯誤則標紅
                helperText={!!keyError && apiKeyInput.length > 0 && !apiKeyStatus?.is_set ? keyError : "此金鑰將安全地傳輸到後端進行儲存和使用。"}
              />
              <Button
                variant="contained"
                color="primary"
                onClick={handleSetApiKey}
                disabled={isSubmittingKey || !apiKeyInput.trim()} // 禁用按鈕的條件
                startIcon={isSubmittingKey ? <CircularProgress size={20} color="inherit" /> : null} // 提交時顯示小進度圈
              >
                {isSubmittingKey ? '設定中...' : '儲存並設定金鑰'}
              </Button>
            </>
          )}
          {/* 根據操作模式條件化顯示 Google Drive 服務帳號的狀態 */}
          {/* 步驟 1: 檢查操作模式是否仍在加載 */}
          {isLoadingMode ? (
            // 若正在加載操作模式，顯示進度指示器
            <Box sx={{ display: 'flex', justifyContent: 'center', my: 1 }}><CircularProgress size={24} /></Box>
          ) : mode === 'transient' ? (
            // 步驟 2: 若為「暫存模式」，則顯示 Drive 功能已停用的提示
            <Alert severity="info" sx={{ mt: 1 }}>
              目前為暫存模式，Google Drive 相關功能（如自動讀取週報、資料持久化）已停用。
            </Alert>
          ) : mode === 'persistent' && !isKeyLoading && apiKeyStatus ? (
            // 步驟 3: 若為「持久模式」，並且 API 金鑰狀態 (isKeyLoading, apiKeyStatus) 也已加載完成
            // 則根據 apiKeyStatus.drive_service_account_loaded 的值顯示 Drive 服務帳號的具體狀態
            apiKeyStatus.drive_service_account_loaded ? (
              <Alert severity="info" sx={{ mt: 1 }}>持久模式：Google Drive 服務帳號已從後端正確加載並初始化成功。</Alert>
            ) : (
              <Alert severity="warning" sx={{ mt: 1 }}>
                持久模式：Google Drive 服務帳號未從後端環境變數加載或初始化失敗。
                如果您剛才貼上的是服務帳號 JSON 內容且設定成功，此狀態應已更新。
                否則，部分 Google Drive 相關功能 (如自動讀取週報) 可能會受限。
              </Alert>
            )
          ) : null } {/* 其他情況 (例如 mode 為 null 但 isLoadingMode 為 false，或 isKeyLoading 為 true 但 isLoadingMode 為 false) 不顯示此區塊 */}

           {/* 如果金鑰本身已設定，但獲取狀態的過程中有其他非致命錯誤，也提示用戶 */}
           {keyError && apiKeyStatus?.is_set && (
             <Alert severity="warning" sx={{ mt:1 }}>金鑰狀態資訊可能不完整: {keyError}</Alert>
           )}
        </Box>

        {/* AI 模型選擇區塊 */}
        <Box sx={{ p: 2, border: '1px solid #e0e0e0', borderRadius: '4px' }}>
          <Typography variant="h6" gutterBottom>
            AI 分析模型選擇
          </Typography>
          <FormControl fullWidth variant="outlined" sx={{ mb: 1 }}>
            <InputLabel id="ai-model-select-label">選擇分析模型</InputLabel>
            <Select
              labelId="ai-model-select-label"
              id="ai-model-select"
              value={selectedModel}
              label="選擇分析模型" // 與 InputLabel 一致
              onChange={handleModelChange}
            >
              {availableModels.map((model) => (
                <MenuItem key={model.id} value={model.id}>
                  {model.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 1 }}>
            當前選定模型: {availableModels.find(m => m.id === selectedModel)?.name || '未選擇'}。此設定將影響 AI 分析的品質和特性。
          </Typography>
        </Box>

      </CardContent>
    </Card>
  );
};

export default SettingsCard;
