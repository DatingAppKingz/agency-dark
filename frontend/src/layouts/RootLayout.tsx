import { useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { SkipLinks } from '@/components/accessibility/SkipLinks';
import { browserCompat } from '@/utils/browser-compat';
import { Box } from '@mui/material';

export const RootLayout = () => {
  const checkAuth = useAuthStore((state) => state.checkAuth);

  useEffect(() => {
    // Check authentication status on app load
    checkAuth();
    
    // Check browser compatibility
    const { supported, missing } = browserCompat.checkSupport();
    if (!supported) {
      console.warn('Missing browser features:', missing);
    }
    
    // Apply polyfills
    browserCompat.applyPolyfills();
  }, [checkAuth]);

  return (
    <>
      <SkipLinks />
      <Box component="main" id="main-content">
        <Outlet />
      </Box>
    </>
  );
};