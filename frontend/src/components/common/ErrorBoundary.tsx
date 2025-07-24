import { Box, Typography, Button } from '@mui/material';
import { useRouteError, useNavigate } from 'react-router-dom';

export const ErrorBoundary = () => {
  const error = useRouteError() as Error;
  const navigate = useNavigate();

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        p: 3,
        textAlign: 'center',
      }}
    >
      <Typography variant="h1" sx={{ fontSize: '4rem', mb: 2 }}>
        Oops!
      </Typography>
      <Typography variant="h5" color="text.secondary" sx={{ mb: 2 }}>
        Something went wrong
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 4, maxWidth: 500 }}>
        {error?.message || 'An unexpected error occurred. Please try again later.'}
      </Typography>
      <Box sx={{ display: 'flex', gap: 2 }}>
        <Button variant="contained" onClick={() => navigate('/')}>
          Go Home
        </Button>
        <Button variant="outlined" onClick={() => window.location.reload()}>
          Reload Page
        </Button>
      </Box>
    </Box>
  );
};