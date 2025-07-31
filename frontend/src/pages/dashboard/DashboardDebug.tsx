import { useEffect, useState } from 'react';
import { Box, Paper, Typography, Button } from '@mui/material';
import { useAuthStore } from '@/store/authStore';
import { useDashboardStats, useModelPerformance } from '@/hooks/useAnalytics';
import apiClient from '@/services/api/client';

export const DashboardDebug = () => {
  const { user, token } = useAuthStore();
  const { data: stats, isPending: statsLoading, error: statsError } = useDashboardStats();
  const { data: models, isPending: modelsLoading, error: modelsError } = useModelPerformance('month');
  const [directAPIResult, setDirectAPIResult] = useState<any>(null);

  useEffect(() => {
    console.log('🔍 Debug Component Mounted');
    console.log('👤 Current User:', user);
    console.log('🔑 Auth Token:', token ? `${token.substring(0, 20)}...` : 'No token');
    console.log('📊 Stats Hook Data:', { stats, statsLoading, statsError });
    console.log('📈 Models Hook Data:', { models, modelsLoading, modelsError });
  }, [user, token, stats, statsLoading, statsError, models, modelsLoading, modelsError]);

  const testDirectAPI = async () => {
    try {
      console.log('🚀 Making direct API call...');
      const response = await apiClient.get('/analytics/agency/dashboard-stats');
      console.log('✅ Direct API Success:', response.data);
      setDirectAPIResult(response.data);
    } catch (error: any) {
      console.error('❌ Direct API Error:', error);
      setDirectAPIResult({ error: error.message });
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Dashboard Debug Information
      </Typography>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6">User Information</Typography>
        <pre>{JSON.stringify({ user, hasToken: !!token }, null, 2)}</pre>
      </Paper>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6">Stats Hook Result</Typography>
        <Typography>Loading: {statsLoading ? 'Yes' : 'No'}</Typography>
        <Typography>Error: {statsError ? JSON.stringify(statsError) : 'None'}</Typography>
        <pre>{JSON.stringify(stats, null, 2)}</pre>
      </Paper>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6">Models Hook Result</Typography>
        <Typography>Loading: {modelsLoading ? 'Yes' : 'No'}</Typography>
        <Typography>Error: {modelsError ? JSON.stringify(modelsError) : 'None'}</Typography>
        <pre>{JSON.stringify(models, null, 2)}</pre>
      </Paper>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6">Direct API Test</Typography>
        <Button variant="contained" onClick={testDirectAPI} sx={{ mb: 2 }}>
          Test Direct API Call
        </Button>
        {directAPIResult && (
          <pre>{JSON.stringify(directAPIResult, null, 2)}</pre>
        )}
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Typography variant="h6">Check Console</Typography>
        <Typography>
          Open your browser's Developer Tools Console (F12) to see detailed logs.
        </Typography>
      </Paper>
    </Box>
  );
};

export default DashboardDebug;
