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

// 定義金鑰顯示名稱的映射 (繁體中文)
const KEY_DISPLAY_NAMES: Record<string, string> = {
  GOOGLE_API_KEY: "Google AI (Gemini) 金鑰",
  API_KEY_FRED: "FRED API 金鑰",
  API_KEY_FINMIND: "FinMind API 金鑰",
  API_KEY_FINNHUB: "Finnhub API 金鑰",
  API_KEY_FMP: "Financial Modeling Prep API 金鑰",
  ALPHA_VANTAGE_API_KEY: "Alpha Vantage API 金鑰",
  DEEPSEEK_API_KEY: "DeepSeek API 金鑰",
  // legacy_gemini_api_key_is_set, legacy_gemini_api_key_source, drive_service_account_loaded, gemini_service_configured 這些是狀態指示，不是用戶直接設定的key
};

// 定義哪些金鑰應該顯示在UI上供用戶輸入和查看狀態
// 順序也將決定渲染的順序
const MANAGED_API_KEYS: string[] = [
  "GOOGLE_API_KEY",
  "API_KEY_FRED",
  "API_KEY_FINMIND",
  "API_KEY_FINNHUB",
  "API_KEY_FMP",
  "ALPHA_VANTAGE_API_KEY",
  "DEEPSEEK_API_KEY",
];

// 新的 API 金鑰狀態類型，直接對應後端 /api/get_key_status 的回應
// 後端返回的是 Record<string, string>，其中 string 是 "已設定" 或 "未設定"
type ApiKeyOverallStatus = Record<string, string>;

// 前端用於追蹤每個金鑰詳細狀態的類型擴展 (如果需要顯示更多如來源等，但目前後端不直接提供這些細節給所有 key)
// 為簡化，我們主要依賴 ApiKeyOverallStatus 的字串狀態，並在前端補充輸入值
// interface ApiKeyDetailedInfo {
//   status: string; // "已設定" 或 "未設定"
//   value?: string; // 用戶在輸入框中輸入的值
//   source?: string; // 金鑰來源 (如果後端提供)
// }

const SettingsCard: React.FC = () => {
  const { mode, isLoadingMode } = useOperationMode();

  // API 金鑰狀態
  // apiKeyInput: 儲存各個金鑰輸入框的值，key 是金鑰的 ID (如 GOOGLE_API_KEY)
  const [apiKeyInput, setApiKeyInput] = useState<Record<string, string>>({});
  // apiKeyStatus: 儲存從後端獲取的所有金鑰的狀態
  const [apiKeyStatus, setApiKeyStatus] = useState<ApiKeyOverallStatus | null>(null);
  // isKeyLoading: 控制整體金鑰列表的初始載入指示
  const [isKeyLoading, setIsKeyLoading] = useState<boolean>(true);
  // keyError: 顯示一般性錯誤
  const [keyError, setKeyError] = useState<string | null>(null);
  // isSubmittingKey: 儲存當前正在提交的金鑰的名稱，或 null (如果沒有金鑰在提交)
  const [isSubmittingKey, setIsSubmittingKey] = useState<string | null>(null);

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
    setKeyError(null);
    try {
      // 更新 API 端點
      const response = await fetch('/api/v1/get_key_status');
      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        const errorMessage = errorData?.detail || `HTTP 錯誤 ${response.status}: ${response.statusText}`;
        throw new Error(`獲取 API 金鑰狀態失敗：${errorMessage}`);
      }
      // data 的類型現在是 ApiKeyOverallStatus (Record<string, string>)
      const data: ApiKeyOverallStatus = await response.json();
      setApiKeyStatus(data);
    } catch (error) {
      console.error('獲取 API 金鑰狀態時發生錯誤 (繁體中文):', error);
      const displayError = error instanceof Error ? error.message : '獲取金鑰狀態時發生未知網路錯誤 (繁體中文)';
      setKeyError(displayError);
      setApiKeyStatus(null); // 出錯時設為 null
    } finally {
      setIsKeyLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchApiKeyStatus();
  }, [fetchApiKeyStatus]);

  // 新的金鑰提交邏輯
  const handleSaveKey = async (keyName: string) => {
    const valueToSave = apiKeyInput[keyName]?.trim() || ''; // 獲取特定金鑰的輸入值，trim處理

    if (!valueToSave) { // 如果用戶清空了輸入框並點擊儲存，也視為一次有效的提交 (清除金鑰)
      // 提示用戶是否真的要清除金鑰，因為這是一個有意的操作
      if (!confirm(`您確定要清除 ${KEY_DISPLAY_NAMES[keyName] || keyName} 嗎？此操作將移除已設定的金鑰。`)) {
        return;
      }
    }

    setIsSubmittingKey(keyName); // 設定正在提交的金鑰名稱
    setKeyError(null);

    try {
      const response = await fetch('/api/v1/set_keys', { // 更新 API 端點
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        // 請求體現在是 { [keyName]: valueToSave }
        body: JSON.stringify({ [keyName]: valueToSave }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: '設定金鑰失敗，無法解析伺服器錯誤原因。' }));
        throw new Error(errorData.detail || `設定 ${KEY_DISPLAY_NAMES[keyName] || keyName} 時發生伺服器錯誤：${response.status}`);
      }

      // 清除該金鑰的輸入框內容
      setApiKeyInput(prev => ({ ...prev, [keyName]: '' }));
      await fetchApiKeyStatus(); // 重新獲取所有金鑰的狀態
      alert(`${KEY_DISPLAY_NAMES[keyName] || keyName} 已成功更新！`);
    } catch (error) {
      console.error(`設定 ${KEY_DISPLAY_NAMES[keyName] || keyName} 時發生錯誤:`, error);
      const displayError = error instanceof Error ? error.message : `設定 ${KEY_DISPLAY_NAMES[keyName] || keyName} 時發生未知網路錯誤。`;
      setKeyError(displayError); // 顯示一般性錯誤，或可以擴展為 key-specific error
    } finally {
      setIsSubmittingKey(null); // 清除提交狀態
    }
  };

  const handleModelChange = (event: SelectChangeEvent<string>) => {
    setSelectedModel(event.target.value as string); // 更新選擇的模型 ID
  };

  return (
    <Card sx={{ maxWidth: 700, margin: 'auto', mt: 4 }}>
      <CardContent>
        <Typography variant="h5" component="div" gutterBottom sx={{ textAlign: 'center' }}>
          系統設定與 API 金鑰管理
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2, textAlign: 'center' }}>
          管理第三方服務的 API 金鑰及其他系統層級設定。部分金鑰可能已透過環境變數或 Colab Secrets 設定。
        </Typography>

        {/* 整體金鑰載入與錯誤提示 */}
        {isKeyLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', my: 2 }}><CircularProgress /></Box>
        ) : keyError && !apiKeyStatus ? ( // apiKeyStatus 為 null 表示完全無法獲取狀態
          <Alert severity="error" sx={{ mb: 2 }}>{keyError}</Alert>
        ) : null}

        {/* 通用錯誤提示 (如果不是針對特定金鑰的) */}
        {keyError && apiKeyStatus && (
           <Alert severity="error" sx={{ mb: 2 }}>{keyError}</Alert>
        )}

        {/* API 金鑰設定區塊 - 動態生成 */}
        {apiKeyStatus && MANAGED_API_KEYS.map((keyName) => (
          <Box key={keyName} sx={{ mb: 3, p: 2, border: '1px solid #e0e0e0', borderRadius: '4px' }}>
            <Typography variant="h6" gutterBottom>
              {KEY_DISPLAY_NAMES[keyName] || keyName}
            </Typography>

            {apiKeyStatus[keyName] === "已設定" ? (
              <Alert severity="success" sx={{ mb: 1 }}>
                {KEY_DISPLAY_NAMES[keyName] || keyName} 已設定。
                {/* 後端目前不提供來源資訊給所有key，若要顯示 "來源: Colab 環境" 等，需後端配合調整get_key_status回應 */}
              </Alert>
            ) : (
               <Alert severity="warning" sx={{ mb: 1 }}>
                {KEY_DISPLAY_NAMES[keyName] || keyName} 目前未設定或設定值無效。
              </Alert>
            )}

            <TextField
              fullWidth
              label={`輸入新的 ${KEY_DISPLAY_NAMES[keyName] || keyName}`}
              variant="outlined"
              value={apiKeyInput[keyName] || ''}
              onChange={(e) => setApiKeyInput(prev => ({ ...prev, [keyName]: e.target.value }))}
              sx={{ mb: 1 }}
              disabled={isSubmittingKey === keyName || !!isSubmittingKey} // 當此金鑰提交中，或有任何其他金鑰提交中時禁用
              placeholder={apiKeyStatus[keyName] === "已設定" ? "若要更新，請輸入新金鑰" : "貼上您的 API 金鑰"}
              helperText={`此金鑰將用於存取 ${KEY_DISPLAY_NAMES[keyName] || keyName} 相關服務。`}
            />
            <Button
              variant="contained"
              color="primary"
              onClick={() => handleSaveKey(keyName)}
              disabled={isSubmittingKey === keyName || !!isSubmittingKey}
              startIcon={isSubmittingKey === keyName ? <CircularProgress size={20} color="inherit" /> : null}
            >
              {isSubmittingKey === keyName ? '儲存中...' : `儲存 ${KEY_DISPLAY_NAMES[keyName] || keyName}`}
            </Button>
          </Box>
        ))}

        {/* Google Drive 服務帳號狀態顯示 (基於 apiKeyStatus 中的特定欄位) */}
        { !isKeyLoading && apiKeyStatus && (
          <Box sx={{ mb: 3, p: 2, border: '1px solid #e0e0e0', borderRadius: '4px' }}>
            <Typography variant="h6" gutterBottom>
              Google Drive 服務帳號狀態 (持久模式)
            </Typography>
            {isLoadingMode ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', my: 1 }}><CircularProgress size={24} /></Box>
            ) : mode === 'transient' ? (
              <Alert severity="info">
                目前為暫存模式，Google Drive 相關功能（如自動讀取週報、資料持久化）已停用。
              </Alert>
            ) : mode === 'persistent' ? (
              // 從 apiKeyStatus 中讀取 drive_service_account_loaded 的狀態
              // 後端 /api/get_key_status 需要包含 drive_service_account_loaded 和 gemini_service_configured
              // 這些鍵名在 MANAGED_API_KEYS 之外，但可能包含在 apiKeyStatus 回應中
              apiKeyStatus.drive_service_account_loaded === "已設定" || apiKeyStatus.drive_service_account_loaded === "true" ? ( // 後端可能返回 "true" 字串或 "已設定"
                <Alert severity="success">持久模式：Google Drive 服務帳號已成功加載並配置。</Alert>
              ) : (
                <Alert severity="warning">
                  持久模式：Google Drive 服務帳號未設定或加載失敗。部分 Drive 功能可能受限。
                  (提示: 可透過 Colab Secrets 設定 `GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT` 或在伺服器環境設定)
                </Alert>
              )
            ) : null}
          </Box>
        )}

        {/* AI 模型選擇區塊 */}
        <Box sx={{ mt:3, p: 2, border: '1px solid #e0e0e0', borderRadius: '4px' }}>
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
