import { Box, Typography, Button, Container, Paper } from '@mui/material';
import { ErrorOutline, Refresh, Home } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';

interface ErrorFallbackProps {
  error: Error;
  resetError: () => void;
  showDetails?: boolean;
}

export const ErrorFallback = ({ error, resetError, showDetails = false }: ErrorFallbackProps) => {
  const navigate = useNavigate();

  return (
    <Container maxWidth="sm">
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '60vh',
          textAlign: 'center',
          py: 4,
        }}
      >
        <ErrorOutline sx={{ fontSize: 80, color: 'error.main', mb: 3 }} />
        
        <Typography variant="h4" gutterBottom>
          Oops! Something went wrong
        </Typography>
        
        <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
          We encountered an unexpected error. Please try refreshing the page or contact support if the problem persists.
        </Typography>

        {showDetails && import.meta.env.MODE === 'development' && (
          <Paper
            sx={{
              p: 2,
              mb: 3,
              backgroundColor: 'grey.100',
              maxWidth: '100%',
              overflow: 'auto',
            }}
          >
            <Typography variant="caption" component="pre" sx={{ textAlign: 'left' }}>
              {error.stack || error.message}
            </Typography>
          </Paper>
        )}

        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="contained"
            startIcon={<Refresh />}
            onClick={resetError}
          >
            Try Again
          </Button>
          
          <Button
            variant="outlined"
            startIcon={<Home />}
            onClick={() => navigate('/dashboard')}
          >
            Go to Dashboard
          </Button>
        </Box>
      </Box>
    </Container>
  );
};
