import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Box, useTheme, useMediaQuery } from '@mui/material';
import { Header } from '@/components/layout/Header';
import { Sidebar } from '@/components/layout/Sidebar';
import { SocketProvider } from '@/providers/SocketProvider';

const DRAWER_WIDTH = 280;

export const DashboardLayout = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [sidebarOpen, setSidebarOpen] = useState(!isMobile);

  const handleSidebarToggle = () => {
    setSidebarOpen(!sidebarOpen);
  };

  return (
    <SocketProvider>
      <Box sx={{ display: 'flex', minHeight: '100vh' }}>
        <Header 
          onMenuClick={handleSidebarToggle} 
          drawerWidth={DRAWER_WIDTH}
        />
        <Sidebar
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          width={DRAWER_WIDTH}
        />
        <Box
          component="main"
          sx={{
            flexGrow: 1,
            p: 3,
            width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
            ml: { md: `${DRAWER_WIDTH}px` },
            mt: '64px', // Header height
            backgroundColor: 'background.default',
          }}
        >
          <Outlet />
        </Box>
      </Box>
    </SocketProvider>
  );
};
