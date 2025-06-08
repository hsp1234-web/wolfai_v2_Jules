// 'use client'; // page.tsx can remain a Server Component if it only renders Client Components

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import SettingsCard from '../components/SettingsCard'; // Relative path
import Container from '@mui/material/Container';

export default function HomePage() {
  return (
    <Container maxWidth="lg">
      <Box
        sx={{
          my: 4, // margin top and bottom
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
        }}
      >
        <Typography variant="h3" component="h1" gutterBottom sx={{
          textAlign: 'center',
          fontWeight: 'bold',
          color: 'primary.main', // Uses theme's primary color
          mb: 4
        }}>
          Wolf AI 可觀測性分析平台 V2.2
        </Typography>

        <SettingsCard />

      </Box>
    </Container>
  );
}
