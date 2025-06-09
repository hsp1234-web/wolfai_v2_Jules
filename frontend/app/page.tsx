'use client'; // 需要客戶端互動，故標記為 client component

import { useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Container from '@mui/material/Container';
import Fade from '@mui/material/Fade';
import MainMenu from '../components/MainMenu'; // 假設我們創建一個新的選單元件

// 導出預設的 HomePage 元件
export default function HomePage() {
  const [showMenu, setShowMenu] = useState(false);

  const handleStartClick = () => {
    setShowMenu(true);
  };

  return (
    // 使用 Container 元件包裹頁面內容，設定最大寬度為 'lg'
    <Container maxWidth="lg">
      <Box
        sx={{
          my: 4, // 上下邊距
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '80vh', // 讓內容垂直居中
        }}
      >
        <Fade in={!showMenu} timeout={500}>
          <Box sx={{ textAlign: 'center', display: showMenu ? 'none' : 'block' }}>
            {/* 歡迎畫面 */}
            <Typography variant="h2" component="h1" gutterBottom sx={{
              fontWeight: 'bold',
              color: 'primary.main',
              mb: 2
            }}>
              歡迎使用 蒼狼 AI
            </Typography>
            <Typography variant="h5" color="text.secondary" sx={{ mb: 4 }}>
              您的專屬報告分析與可觀測性平台
            </Typography>
            <Button
              variant="contained"
              color="primary"
              size="large"
              onClick={handleStartClick}
              sx={{ py: 2, px: 6, fontSize: '1.2rem' }}
            >
              點 我 開 始
            </Button>
          </Box>
        </Fade>

        <Fade in={showMenu} timeout={500}>
           {/* showMenu 為 true 時，顯示主選單 */}
           <Box sx={{ display: showMenu ? 'block' : 'none', width: '100%' }}>
              <MainMenu />
           </Box>
        </Fade>

      </Box>
    </Container>
  );
}
