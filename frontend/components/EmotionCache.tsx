'use client'; // 標記為客戶端元件，因為它涉及 React state 和 hooks
import * as React from 'react';
import type { EmotionCache, Options as OptionsOfCreateCache } from '@emotion/cache'; // Emotion 快取相關類型
import createCache from '@emotion/cache'; // Emotion 建立快取的函數
import { useServerInsertedHTML } from 'next/navigation'; // Next.js hook，用於在伺服器端插入 HTML
import { CacheProvider as EmotionCacheProvider } from '@emotion/react'; // Emotion 的 CacheProvider

// 定義 NextAppDirEmotionCacheProvider 元件的 props 類型
export type NextAppDirEmotionCacheProviderProps = {
  // Emotion 快取選項，移除了 'insertionPoint'，因為它將由 useServerInsertedHTML 自動處理
  options: Omit<OptionsOfCreateCache, 'insertionPoint'>;
  children: React.ReactNode; // 子元件
};

// NextAppDirEmotionCacheProvider 元件：用於在 Next.js App Directory 中設定 Emotion CSS-in-JS 庫
export default function NextAppDirEmotionCacheProvider(props: NextAppDirEmotionCacheProviderProps) {
  const { options, children } = props;

  // 使用 React.useState 創建和管理 Emotion 快取實例及 flush 函數
  // 這確保快取只在元件首次渲染時創建一次
  const [{ cache, flush }] = React.useState(() => {
    const cache = createCache(options); // 根據傳入的選項建立 Emotion 快取
    cache.compat = true; // 啟用相容模式，可能有助於解決一些與 React 18+ 的問題
    const prevInsert = cache.insert; // 保存原始的 insert 方法
    let inserted: string[] = []; // 用於追蹤已插入的樣式名稱
    // 重寫 cache.insert 方法以攔截插入的樣式
    cache.insert = (...args) => {
      const serialized = args[1]; // 第二個參數是序列化後的樣式對象
      if (cache.inserted[serialized.name] === undefined) { // 如果此樣式名稱之前未被插入
        inserted.push(serialized.name); // 將其添加到 inserted 陣列中
      }
      return prevInsert(...args); // 呼叫原始的 insert 方法
    };
    // flush 函數：返回已插入的樣式名稱列表，並清空列表
    const flush = () => {
      const prevInserted = inserted; // 保存當前已插入的列表
      inserted = []; // 清空列表
      return prevInserted; // 返回之前保存的列表
    };
    return { cache, flush }; // 返回快取實例和 flush 函數
  });

  // useServerInsertedHTML hook：用於在伺服器渲染期間收集 Emotion 生成的樣式，
  // 並將它們作為 <style> 標籤插入到 HTML 的 <head> 中。
  // 這對於伺服器端渲染 (SSR) 和靜態站點生成 (SSG) 至關重要，以確保初始頁面加載時樣式正確。
  useServerInsertedHTML(() => {
    const names = flush(); // 獲取自上次 flush 以來所有已插入的樣式名稱
    if (names.length === 0) { // 如果沒有新的樣式被插入，則不執行任何操作
      return null;
    }
    let styles = ''; // 用於累積樣式字串
    for (const name of names) { // 遍歷所有樣式名稱
      styles += cache.inserted[name]; // 從快取中獲取對應的 CSS 規則並附加到 styles 字串
    }
    return (
      // 返回一個 <style> 標籤，其中包含所有收集到的樣式
      <style
        key={cache.key} // 使用快取的 key 作為 React key
        data-emotion={`${cache.key} ${names.join(' ')}`} // data-emotion 屬性有助於 Emotion 在客戶端識別這些樣式
        dangerouslySetInnerHTML={{ // 直接設定 HTML 內容
          __html: styles, // 將累積的樣式字串作為 <style> 標籤的內容
        }}
      />
    );
  });

  // 使用 Emotion 的 CacheProvider 將創建的快取實例提供給子元件樹
  // 這樣，子元件中的 Emotion 相關操作（如 styled components）就能夠使用這個配置好的快取
  return <EmotionCacheProvider value={cache}>{children}</EmotionCacheProvider>;
}
