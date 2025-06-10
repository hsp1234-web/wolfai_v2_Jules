'use client'; // Though Jest runs in Node, RTL renders components in a JSDOM env.

import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom'; // jest.setup.js should handle this, but explicit import is fine.
import HealthDashboardPage from './page'; // Assuming default export from page.tsx

// Mock global fetch
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock MUI icons to avoid rendering issues in tests if not needed for assertions
jest.mock('@mui/icons-material/Refresh', () => () => <div data-testid="refresh-icon" />);
jest.mock('@mui/icons-material/CheckCircleOutline', () => () => <div data-testid="check-icon" />);
jest.mock('@mui/icons-material/ErrorOutline', () => () => <div data-testid="error-icon" />);
jest.mock('@mui/icons-material/WarningAmberOutlined', () => () => <div data-testid="warning-icon" />);
jest.mock('@mui/icons-material/HelpOutline', () => () => <div data-testid="help-icon" />);


describe('HealthDashboardPage - 健康儀表板頁面', () => {
  beforeEach(() => {
    mockFetch.mockClear(); // Clear mock usage history before each test
    // Reset mock implementation to a default successful response for tests that don't specify otherwise
    mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
            overall_status: "全部正常",
            database_status: { status: "正常", details: "資料庫連接成功" },
            gemini_api_status: { status: "已配置", details: "API 金鑰已設定" },
            google_drive_status: { status: "已初始化", details: "DriveService 已在持久模式下初始化" },
            scheduler_status: { status: "運行中", details: "排程器運行正常", next_run_time: new Date().toISOString() },
            filesystem_status: { status: "可讀寫", temp_dir_path: "/tmp/test", details: "暫存目錄權限正常" },
            frontend_service_status: { status: "可達", frontend_url: "http://localhost:3000", details: "前端服務回應正常" },
            timestamp: new Date().toISOString(),
        }),
    } as Response);
  });

  test('應正確渲染中文標題和初始加載狀態', async () => {
    /** 測試初始加載時是否顯示 "正在載入..." 和標題。 */
    // Override default mock for this specific test to ensure loading state is visible
    mockFetch.mockImplementationOnce(() => new Promise(() => {})); // A promise that never resolves to keep it in loading

    render(<HealthDashboardPage />);

    expect(screen.getByText('系統健康狀態儀表板')).toBeInTheDocument();
    // The loading.tsx content is "正在載入系統健康狀態..."
    // However, the page itself also has a loading state. We'll check for the page's specific loading.
    expect(screen.getByText('正在載入健康狀態...')).toBeInTheDocument(); // This is from the page itself
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  test('成功獲取數據後應顯示各組件狀態卡片', async () => {
    /** 測試成功獲取並解析數據後，是否正確渲染各個狀態卡片及其內容。 */
    const mockData = {
      overall_status: "全部正常",
      database_status: { status: "正常", details: "資料庫連接良好" },
      gemini_api_status: { status: "已配置且可連線", details: "Gemini API 連線測試成功" },
      google_drive_status: { status: "已初始化 (持久模式)", details: "Drive Service 運作中" },
      scheduler_status: { status: "運行中", next_run_time: new Date().toISOString(), details: "排程正常" },
      filesystem_status: { status: "可讀寫", temp_dir_path: "/data/temp", details: "暫存目錄權限OK" },
      frontend_service_status: { status: "可達", frontend_url: "http://localhost:3000", details: "前端自我探測成功" },
      timestamp: new Date().toISOString(),
    };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockData,
    } as Response);

    render(<HealthDashboardPage />);

    // Wait for loading to disappear and data to be rendered
    await waitFor(() => {
      expect(screen.queryByText('正在載入健康狀態...')).not.toBeInTheDocument();
    });

    // Check for titles of cards or key elements
    expect(screen.getByText('總體狀態:')).toBeInTheDocument();
    expect(screen.getByText(mockData.overall_status)).toBeInTheDocument();

    expect(screen.getByText('資料庫狀態')).toBeInTheDocument();
    expect(screen.getByText(mockData.database_status.status)).toBeInTheDocument();
    expect(screen.getByText(mockData.database_status.details!)).toBeInTheDocument();

    expect(screen.getByText('Gemini AI 服務')).toBeInTheDocument();
    expect(screen.getByText(mockData.gemini_api_status.status)).toBeInTheDocument();
    expect(screen.getByText(mockData.gemini_api_status.details!)).toBeInTheDocument();

    expect(screen.getByText('Google Drive 服務')).toBeInTheDocument();
    // ... add more assertions for other cards as needed
    expect(screen.getByText('排程器狀態')).toBeInTheDocument();
    expect(screen.getByText('檔案系統 (暫存區)')).toBeInTheDocument();
    expect(screen.getByText('前端服務 (自身探測)')).toBeInTheDocument();

    // Check timestamp (might need a more robust way if format is tricky)
    // For now, just check if "最後更新時間" part is there
    expect(screen.getByText(/最後更新時間/)).toBeInTheDocument();
  });

  test('API請求失敗時應顯示中文錯誤訊息', async () => {
    /** 測試當 API 請求失敗 (例如網路錯誤或伺服器返回錯誤狀態) 時，是否顯示相應的中文錯誤提示。 */
    const errorMessage = "網路連線中斷，無法連接至伺服器。";
    mockFetch.mockRejectedValueOnce(new Error(errorMessage));

    render(<HealthDashboardPage />);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent(`獲取健康狀態時發生錯誤: ${errorMessage}`);
    expect(alert).toHaveClass('MuiAlert-standardError'); // MUI class for error severity
  });

  test('API請求返回非OK狀態時應顯示中文錯誤訊息', async () => {
    /** 測試當 API 請求返回非 200 OK 狀態時，是否顯示包含狀態文字的中文錯誤提示。 */
    const statusText = "內部伺服器錯誤";
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: statusText,
      json: async () => ({ error: "server error detail" }), // Mock error response body if needed
      text: async () => `{"error": "server error detail"}` // Mock text response
    } as Response);

    render(<HealthDashboardPage />);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent(`獲取健康狀態失敗: 500 ${statusText}`);
  });

  test('手動刷新按鈕應能觸發資料重新獲取', async () => {
    /** 測試點擊手動刷新按鈕時，是否會再次調用 fetchHealthData。 */
    render(<HealthDashboardPage />);

    // Wait for initial load to complete
    await waitFor(() => expect(screen.queryByText('正在載入健康狀態...')).not.toBeInTheDocument());

    mockFetch.mockClear(); // Clear previous calls
    // Setup a new mock response for the refresh
    const refreshedData = { ... (await mockFetch.mock.results[0].value.json()), overall_status: "部分異常" };
    mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => refreshedData,
    } as Response);

    const refreshButton = screen.getByRole('button', { name: /手動刷新/i });
    act(() => {
      refreshButton.click();
    });

    // Expect fetch to be called again
    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(1)); // Called once after clear for the refresh

    // And new data should be displayed
    await waitFor(() => {
        expect(screen.getByText(refreshedData.overall_status)).toBeInTheDocument();
    });
  });

  // Test for interval refresh could be more complex, involving jest.useFakeTimers()
  // For now, we assume the setInterval in useEffect works as intended.
});
