// frontend/contexts/OperationModeContext.tsx
// 這個 Context 用於管理和提供整個應用程式的操作模式狀態 (例如 "transient" 或 "persistent")。
// 它允許子元件存取當前操作模式，並根據模式調整其行為或顯示。
'use client'; // 標記為客戶端元件，因為使用了 React Hooks (useState, useEffect, useContext)

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

// 定義 Context 提供的狀態類型
interface OperationModeContextType {
  mode: string | null; // 當前操作模式 ("transient", "persistent", 或 null 如果尚未加載)
  isLoadingMode: boolean; // 布林值，表示是否正在從後端加載操作模式
}

// 創建 Context，初始值為 undefined
const OperationModeContext = createContext<OperationModeContextType | undefined>(undefined);

// OperationModeProvider 元件：
// 這個 Provider 元件包裹了應用程式的部分或全部內容，
// 使其子元件能夠透過 useOperationMode Hook 訂閱和存取操作模式的狀態。
export const OperationModeProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [mode, setMode] = useState<string | null>(null); // 存儲操作模式字串，初始為 null
  const [isLoadingMode, setIsLoadingMode] = useState<boolean>(true); // 存儲加載狀態，初始為 true (正在加載)

  // useEffect Hook：在元件掛載後執行一次，用於從後端 API 獲取操作模式。
  useEffect(() => {
    const fetchMode = async () => {
      setIsLoadingMode(true); // 開始獲取數據，設定為正在加載狀態
      try {
        // 向後端的 /api/health 端點發送請求，該端點會返回包含操作模式的 JSON。
        const response = await fetch('/api/health');
        if (!response.ok) {
          // 如果請求失敗 (例如網路錯誤或伺服器錯誤)，則拋出錯誤。
          throw new Error('無法獲取操作模式');
        }
        const data = await response.json();
        // 從回應數據中獲取 'mode' 欄位。如果未提供，則預設為 'transient'。
        // 這樣可以確保在 API 未正確返回模式時，應用程式有一個合理的預設行為。
        setMode(data.mode || 'transient');
      } catch (error) {
        // 如果在獲取過程中發生任何錯誤 (包括網路錯誤和上面拋出的錯誤)，
        // 則在控制台記錄錯誤訊息，並將模式預設為 'transient'。
        console.error("獲取操作模式失敗 (繁體中文):", error); // 使用繁體中文記錄錯誤
        setMode('transient'); // 出錯時預設為 'transient'，以確保應用程式能繼續運行。
      } finally {
        // 無論成功或失敗，最後都將 isLoadingMode 設定為 false，表示加載過程結束。
        setIsLoadingMode(false);
      }
    };
    fetchMode(); // 執行獲取模式的函數
  }, []); // 空依賴數組 [] 表示此 useEffect 僅在元件首次掛載和卸載時執行一次。

  // OperationModeContext.Provider 將 mode 和 isLoadingMode 的當前值提供給其所有子元件。
  return (
    <OperationModeContext.Provider value={{ mode, isLoadingMode }}>
      {children}
    </OperationModeContext.Provider>
  );
};

// useOperationMode Hook：
// 這是一個自定義 Hook，用於簡化在子元件中存取 OperationModeContext 的過程。
// 它確保了 context 被正確使用 (即在 OperationModeProvider 內部)。
export const useOperationMode = (): OperationModeContextType => {
  const context = useContext(OperationModeContext); // 使用 React 的 useContext Hook 來獲取 context 的當前值。
  if (context === undefined) {
    // 如果 context 為 undefined，表示 useOperationMode 在 OperationModeProvider 外部被調用。
    // 這是一個開發時錯誤，應拋出錯誤以提醒開發者。
    throw new Error('useOperationMode 必須在 OperationModeProvider 內部使用 (繁體中文)');
  }
  return context; // 返回 context 的值 ({ mode, isLoadingMode })。
};
