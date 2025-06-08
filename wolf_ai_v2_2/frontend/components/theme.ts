'use client';
import { createTheme } from '@mui/material/styles';
import { Roboto } from 'next/font/google';

const roboto = Roboto({
  weight: ['300', '400', '500', '700'],
  subsets: ['latin'],
  display: 'swap',
});

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#6750A4' },
    secondary: { main: '#625B71' },
    error: { main: '#B3261E' },
    background: { default: '#FFFBFE', paper: '#FFFBFE' },
  },
  typography: { fontFamily: roboto.style.fontFamily },
  shape: { borderRadius: 16 },
});

export default theme;
