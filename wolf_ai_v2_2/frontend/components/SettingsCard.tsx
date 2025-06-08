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

interface ApiKeyStatus {
  is_set: boolean;
  source: string | null;
  drive_service_account_loaded?: boolean; // Added to match backend response for health/API status
}

const SettingsCard: React.FC = () => {
  // API 金鑰狀態
  const [apiKeyInput, setApiKeyInput] = useState<string>('');
  const [apiKeyStatus, setApiKeyStatus] = useState<ApiKeyStatus | null>(null);
  const [isKeyLoading, setIsKeyLoading] = useState<boolean>(true);
  const [keyError, setKeyError] = useState<string | null>(null);
  const [isSubmittingKey, setIsSubmittingKey] = useState<boolean>(false);

  // AI 模型選擇狀態
  const [selectedModel, setSelectedModel] = useState<string>('gemini-pro'); // 預設模型
  const availableModels = [
    { id: 'gemini-pro', name: 'Gemini Pro (Default)' },
    { id: 'gpt-4-turbo', name: 'GPT-4 Turbo' },
    { id: 'claude-3-opus', name: 'Claude 3 Opus' },
  ];

  const fetchApiKeyStatus = useCallback(async () => {
    setIsKeyLoading(true);
    setKeyError(null);
    try {
      const response = await fetch('/api/get_api_key_status'); // Next.js API 路由
      if (!response.ok) {
        throw new Error(`獲取金鑰狀態失敗: ${response.status} ${response.statusText}`);
      }
      const data: ApiKeyStatus = await response.json();
      setApiKeyStatus(data);
    } catch (error) {
      console.error('獲取 API 金鑰狀態錯誤:', error);
      setKeyError(error instanceof Error ? error.message : '獲取金鑰狀態時發生未知錯誤');
      setApiKeyStatus({ is_set: false, source: null, drive_service_account_loaded: false }); // 假設獲取失敗=未設定
    } finally {
      setIsKeyLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchApiKeyStatus();
  }, [fetchApiKeyStatus]);

  const handleSetApiKey = async () => {
    if (!apiKeyInput.trim()) {
      setKeyError('API 金鑰不能為空。');
      return;
    }
    setIsSubmittingKey(true);
    setKeyError(null);
    try {
      const response = await fetch('/api/set_api_key', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ api_key: apiKeyInput }),
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: '設定金鑰失敗，無法解析錯誤回應。' }));
        throw new Error(errorData.detail || `設定金鑰失敗: ${response.status} ${response.statusText}`);
      }
      setApiKeyInput('');
      await fetchApiKeyStatus();
      alert('API 金鑰設定成功！');
    } catch (error) {
      console.error('設定 API 金鑰錯誤:', error);
      setKeyError(error instanceof Error ? error.message : '設定金鑰時發生未知錯誤');
    } finally {
      setIsSubmittingKey(false);
    }
  };

  const handleModelChange = (event: SelectChangeEvent<string>) => {
    setSelectedModel(event.target.value);
  };

  return (
    <Card sx={{ maxWidth: 600, margin: 'auto', mt: 4 }}>
      <CardContent>
        <Typography variant="h5" component="div" gutterBottom sx={{ textAlign: 'center' }}>
          系統設定
        </Typography>

        {/* API 金鑰設定區 */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            Google API 金鑰 (Gemini等服務)
          </Typography>
          {isKeyLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', my: 2 }}><CircularProgress /></Box>
          ) : keyError && !apiKeyStatus?.is_set ? (
            <Alert severity="error" sx={{ mb: 1 }}>{keyError}</Alert>
          ) : null}

          {apiKeyStatus?.is_set ? (
            <Alert severity="success" sx={{ mb: 1 }}>
              Gemini API 金鑰已設定 (來源: {apiKeyStatus.source === 'environment' ? '環境變數' :
                                 apiKeyStatus.source === 'user_provided' ? '使用者提供' : '未知'})。
            </Alert>
          ) : (
            <>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                系統需要 Google API 金鑰 (例如 Gemini) 以進行 AI 分析。您可以從環境變數加載或在此處手動輸入。
              </Typography>
              <TextField
                fullWidth
                label="貼上您的 Google API 金鑰"
                variant="outlined"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                sx={{ mb: 1 }}
                disabled={isSubmittingKey}
                error={!!keyError && apiKeyInput.length > 0 && !apiKeyStatus?.is_set}
                helperText={!!keyError && apiKeyInput.length > 0 && !apiKeyStatus?.is_set ? keyError : ""}
              />
              <Button
                variant="contained"
                onClick={handleSetApiKey}
                disabled={isSubmittingKey || !apiKeyInput.trim()}
                startIcon={isSubmittingKey ? <CircularProgress size={20} color="inherit" /> : null}
              >
                {isSubmittingKey ? '設定中...' : '設定 Gemini API 金鑰'}
              </Button>
            </>
          )}
          {/* 顯示 Google Drive Service Account 狀態 */}
          { !isKeyLoading && apiKeyStatus && (
            apiKeyStatus.drive_service_account_loaded ? (
              <Alert severity="info" sx={{ mt: 1 }}>Google Drive 服務帳號已從後端正確加載。</Alert>
            ) : (
              <Alert severity="warning" sx={{ mt: 1 }}>Google Drive 服務帳號未加載。部分 Drive 功能可能受限，除非透過上述金鑰貼上服務帳號 JSON。</Alert>
            )
          )}
           {keyError && apiKeyStatus?.is_set && (
             <Alert severity="warning" sx={{ mt:1 }}>獲取金鑰狀態時遇到問題: {keyError}</Alert>
           )}
        </Box>

        {/* AI 模型選擇區 */}
        <Box>
          <Typography variant="h6" gutterBottom>
            AI 模型選擇
          </Typography>
          <FormControl fullWidth variant="outlined">
            <InputLabel id="ai-model-select-label">選擇模型</InputLabel>
            <Select
              labelId="ai-model-select-label"
              id="ai-model-select"
              value={selectedModel}
              label="選擇模型"
              onChange={handleModelChange}
            >
              {availableModels.map((model) => (
                <MenuItem key={model.id} value={model.id}>
                  {model.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Typography variant="caption" display="block" sx={{ mt: 1 }}>
            目前選擇: {availableModels.find(m => m.id === selectedModel)?.name}
          </Typography>
        </Box>

      </CardContent>
    </Card>
  );
};

export default SettingsCard;
