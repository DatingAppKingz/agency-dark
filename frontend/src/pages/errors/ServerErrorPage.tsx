import React from 'react';
import { Box, Typography, Button } from '@mui/material';
import { useNavigate } from 'react-router-dom';

const ServerErrorPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        p: 3,
      }}
    >
      <Typography variant="h1" sx={{ fontSize: '6rem', fontWeight: 'bold' }}>
        500
      </Typography>
      <Typography variant="h4" sx={{ mt: 2, mb: 4 }}>
        Server Error
      </Typography>
      <Typography variant="body1" sx={{ mb: 4, textAlign: 'center' }}>
        Something went wrong. Please try again later.
      </Typography>
      <Button variant="contained" onClick={() => navigate('/dashboard')}>
        Go to Dashboard
      </Button>
    </Box>
  );
};

export default ServerErrorPage;