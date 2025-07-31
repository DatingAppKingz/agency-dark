import { useState, useEffect } from 'react';
import { Box, Button, Paper, Typography, CircularProgress } from '@mui/material';
import { analyticsService } from '@/services/api/analytics';
import apiClient from '@/services/api/client';

export const DebugAnalytics = () => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const testDashboardStats = async () => {
    setLoading(true);
    setError(null);
    setData(null);
    
    try {
      console.log('🚀 Testing dashboard stats...');
      const stats = await analyticsService.getDashboardStats();
      console.log('✅ Success:', stats);
      setData(stats);
    } catch (err: any) {
      console.error('❌ Error:', err);
      setError(err.message || 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const testDirectAPI = async () => {
    setLoading(true);
    setError(null);
    setData(null);
    
    try {
      console.log('🚀 Testing direct API call...');
      const response = await apiClient.get('/analytics/agency/dashboard-stats');
      console.log('✅ Direct API Success:', response.data);
      setData(response.data);
    } catch (err: any) {
      console.error('❌ Direct API Error:', err);
      setError(err.message || 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Log current auth state
    const token = localStorage.getItem('access_token');
    console.log('🔑 Current auth token:', token ? `${token.substring(0, 20)}...` : 'No token');
  }, []);

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Analytics Debug Page
      </Typography>
      
      <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
        <Button variant="contained" onClick={testDashboardStats} disabled={loading}>
          Test Analytics Service
        </Button>
        <Button variant="outlined" onClick={testDirectAPI} disabled={loading}>
          Test Direct API Call
        </Button>
      </Box>

      {loading && <CircularProgress />}
      
      {error && (
        <Paper sx={{ p: 2, mb: 2, backgroundColor: 'error.light' }}>
          <Typography color="error">Error: {error}</Typography>
        </Paper>
      )}
      
      {data && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>Response Data:</Typography>
          <pre style={{ overflow: 'auto' }}>
            {JSON.stringify(data, null, 2)}
          </pre>
        </Paper>
      )}
    </Box>
  );
};

export default DebugAnalytics;
