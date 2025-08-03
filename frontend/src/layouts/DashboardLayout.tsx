import { Outlet } from 'react-router-dom';
import { Box } from '@mui/material';
import { Header } from '@/components/layout/Header';
import { SocketProvider } from '@/providers/SocketProvider';

export const DashboardLayout = () => {
  return (
    <SocketProvider>
      <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
        <Header />
        <Box
          component="main"
          sx={{
            flexGrow: 1,
            backgroundColor: 'background.default',
            mt: '64px', // Header height
          }}
        >
          {/* Centered content container */}
          <Box
            sx={{
              maxWidth: 1400,
              margin: '0 auto',
              p: 3,
            }}
          >
            <Outlet />
          </Box>
        </Box>
      </Box>
    </SocketProvider>
  );
};
