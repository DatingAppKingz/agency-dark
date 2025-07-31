import { Navigate, Outlet } from 'react-router-dom';
import { Box, Container, Paper } from '@mui/material';
import { useAuthStore } from '@/store/authStore';

export const AuthLayout = () => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  // Redirect to dashboard if already authenticated
  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        backgroundColor: 'background.default',
        py: 4,
      }}
    >
      <Container maxWidth="sm">
        <Paper
          elevation={3}
          sx={{
            p: 4,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
          }}
        >
          <Outlet />
        </Paper>
      </Container>
    </Box>
  );
};
