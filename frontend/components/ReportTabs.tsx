import React, { useState } from 'react';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Paper from '@mui/material/Paper'; // Often used to wrap tables

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`report-tabpanel-${index}`}
      aria-labelledby={`report-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

function a11yProps(index: number) {
  return {
    id: `report-tab-${index}`,
    'aria-controls': `report-tabpanel-${index}`,
  };
}

interface ReportTabsProps {
  report: any; // Replace 'any' with a more specific type if available
}

const ReportTabs: React.FC<ReportTabsProps> = ({ report }) => {
  const [value, setValue] = useState(0);

  const handleChange = (event: React.SyntheticEvent, newValue: number) => {
    setValue(newValue);
  };

  if (!report) {
    return <Typography>No report data to display.</Typography>;
  }

  return (
    <Box sx={{ width: '100%' }}>
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={value} onChange={handleChange} aria-label="report tabs">
          <Tab label="情境分析總結" {...a11yProps(0)} />
          <Tab label="高手觀點碰撞" {...a11yProps(1)} />
          <Tab label="AI 推薦策略" {...a11yProps(2)} />
        </Tabs>
      </Box>
      <TabPanel value={value} index={0}>
        <Typography variant="h5" component="h3" gutterBottom>
          情境分析總結
        </Typography>
        {report.quantitative_summary ? (
          typeof report.quantitative_summary === 'object' && !Array.isArray(report.quantitative_summary) ? (
            Object.entries(report.quantitative_summary).map(([key, value]) => (
              <Box key={key} sx={{ mb: 2 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
                  {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}:
                </Typography>
                <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
                  {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                </Typography>
              </Box>
            ))
          ) : (
            <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
              {JSON.stringify(report.quantitative_summary, null, 2)}
            </Typography>
          )
        ) : (
          <Typography>此部分沒有可顯示的資料。</Typography>
        )}
      </TabPanel>
      <TabPanel value={value} index={1}>
        <Typography variant="h5" component="h3" gutterBottom>
          高手觀點碰撞
        </Typography>
        {report.expert_opinions && Array.isArray(report.expert_opinions) && report.expert_opinions.length > 0 ? (
          <TableContainer component={Paper} sx={{ mt: 2 }}>
            <Table sx={{ minWidth: 650 }} aria-label="expert opinions table">
              <TableHead sx={{ backgroundColor: 'action.hover' }}>
                <TableRow>
                  <TableCell sx={{ fontWeight: 'bold' }}>觀點來源</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>核心觀點</TableCell>
                  <TableCell sx={{ fontWeight: 'bold' }}>主要依據</TableCell>
                  {/* Add more TableCell headers if needed */}
                </TableRow>
              </TableHead>
              <TableBody>
                {report.expert_opinions.map((opinion: any, index: number) => (
                  <TableRow
                    key={index}
                    sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
                  >
                    <TableCell component="th" scope="row" sx={{ verticalAlign: 'top' }}>
                      {opinion.expertName || opinion.source || 'N/A'}
                    </TableCell>
                    <TableCell sx={{ verticalAlign: 'top', whiteSpace: 'pre-wrap' }}>
                      {opinion.viewpoint || opinion.opinion || 'N/A'}
                    </TableCell>
                    <TableCell sx={{ verticalAlign: 'top', whiteSpace: 'pre-wrap' }}>
                      {opinion.evidence || opinion.reasoning || 'N/A'}
                    </TableCell>
                    {/* Add more TableCells if needed */}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        ) : (
          <Typography>此部分沒有可顯示的資料，或資料格式不符預期。</Typography>
        )}
      </TabPanel>
      <TabPanel value={value} index={2}>
        <Typography variant="h5" component="h3" gutterBottom>
          AI 推薦策略
        </Typography>
        {report.ai_recommendations && Array.isArray(report.ai_recommendations) && report.ai_recommendations.length > 0 ? (
          report.ai_recommendations.map((strategy: any, index: number) => (
            <Box key={index} sx={{ mb: 3, p: 2, border: '1px solid #eee', borderRadius: '4px' }}>
              {strategy.strategy_name && (
                <Typography variant="h6" component="h4" gutterBottom>
                  策略 {index + 1}: {strategy.strategy_name}
                </Typography>
              )}
              {strategy.parameters && typeof strategy.parameters === 'object' && Object.keys(strategy.parameters).length > 0 && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>操作參數:</Typography>
                  {Object.entries(strategy.parameters).map(([paramKey, paramValue]: [string, any]) => (
                    <Typography key={paramKey} variant="body2" sx={{ ml: 2 }}>
                      - {paramKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}: {String(paramValue)}
                    </Typography>
                  ))}
                </Box>
              )}
              {strategy.see && (
                <Box sx={{ mb: 1 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>看到 (See):</Typography>
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{strategy.see}</Typography>
                </Box>
              )}
              {strategy.think && (
                <Box sx={{ mb: 1 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>想到 (Think):</Typography>
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{strategy.think}</Typography>
                </Box>
              )}
              {strategy.do && (
                <Box sx={{ mb: 1 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>做到 (Do):</Typography>
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{strategy.do}</Typography>
                </Box>
              )}
              {!strategy.strategy_name && !strategy.parameters && !strategy.see && !strategy.think && !strategy.do && (
                <Typography variant="body2">此策略條目無詳細內容。</Typography>
              )}
            </Box>
          ))
        ) : (
          <Typography>此部分沒有可顯示的資料，或資料格式不符預期。</Typography>
        )}
      </TabPanel>
    </Box>
  );
};

export default ReportTabs;
