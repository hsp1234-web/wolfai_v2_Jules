import React, { useState } from 'react';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Box from '@mui/material/Box';
import TextField from '@mui/material/TextField';

const dimensions = [
  { key: 'economic', label: '經濟數據' },
  { key: 'news', label: '市場新聞' },
  { key: 'options', label: '選擇權籌碼細節' },
  { key: 'experts', label: '高手觀點資料庫' },
];

const DataSelectionForm = () => {
  const [selectedChips, setSelectedChips] = useState<string[]>([]);

  const handleChipClick = (chipKey: string) => {
    setSelectedChips((prevSelected) =>
      prevSelected.includes(chipKey)
        ? prevSelected.filter((key) => key !== chipKey)
        : [...prevSelected, chipKey]
    );
  };

  return (
    <Paper elevation={3} sx={{ p: 2, mt: 2 }}>
      <Typography variant="h6" gutterBottom>
        設定分析情境
      </Typography>
      {/* More content will be added in subsequent steps */}
      <Box sx={{ mt: 2 }}>
        <Typography variant="subtitle1" gutterBottom component="div">
          選擇附加資料維度
        </Typography>
        <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
          {dimensions.map((dim) => (
            <Chip
              key={dim.key}
              label={dim.label}
              clickable
              onClick={() => handleChipClick(dim.key)}
              variant={selectedChips.includes(dim.key) ? 'filled' : 'outlined'}
              color={selectedChips.includes(dim.key) ? 'primary' : 'default'}
            />
          ))}
        </Stack>
      </Box>
      {/* More content will be added in subsequent steps */}
      <Box sx={{ mt: 3 }}> {/* Added mt for spacing */}
        <Typography variant="subtitle1" gutterBottom component="div">
          市場歷史地圖
        </Typography>
        <TextField
          fullWidth
          id="analysis-week"
          label="分析週次"
          variant="outlined"
          placeholder="例如：2023W20" // Optional: provide an example placeholder
          // This is a placeholder, so no complex state management for now.
          // A simple onChange could be added if needed for basic interaction,
          // but it's not strictly required for a placeholder.
        />
      </Box>
    </Paper>
  );
};

export default DataSelectionForm;
