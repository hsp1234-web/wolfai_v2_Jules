// 這是一個概念性元件，工程師需要建立此檔案並填充內容
import React from 'react';
import { Card, CardActionArea, CardContent, Grid, Typography, Box } from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import HistoryIcon from '@mui/icons-material/History';
import SettingsIcon from '@mui/icons-material/Settings';

const MainMenu = () => {
  return (
    <Box>
      <Typography variant="h4" align="center" gutterBottom>您想做什麼？</Typography>
      <Grid container spacing={4} justifyContent="center">
        {/* 選項一：上傳分析 */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardActionArea sx={{ p: 3, textAlign: 'center' }}>
              <UploadFileIcon sx={{ fontSize: 60 }} color="primary" />
              <CardContent>
                <Typography variant="h5">上傳報告進行分析</Typography>
                <Typography color="text.secondary">選擇一份文件，讓我為您總結與洞察。</Typography>
              </CardContent>
            </CardActionArea>
          </Card>
        </Grid>
        {/* 選項二：歷史紀錄 */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardActionArea sx={{ p: 3, textAlign: 'center' }}>
              <HistoryIcon sx={{ fontSize: 60 }} color="action" />
              <CardContent>
                <Typography variant="h5">查看歷史報告</Typography>
                <Typography color="text.secondary">瀏覽過去的分析與對話紀錄。</Typography>
              </CardContent>
            </CardActionArea>
          </Card>
        </Grid>
        {/* 選項三：系統設定 */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardActionArea sx={{ p: 3, textAlign: 'center' }}>
              <SettingsIcon sx={{ fontSize: 60 }} color="action" />
              <CardContent>
                <Typography variant="h5">系統與金鑰設定</Typography>
                <Typography color="text.secondary">管理您的 API 金鑰與其他系統選項。</Typography>
              </CardContent>
            </CardActionArea>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default MainMenu;
