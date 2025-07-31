import React, { useState } from 'react';
import { 
  Box, 
  Button, 
  Card, 
  CardContent, 
  Typography, 
  TextField,
  Alert,
  CircularProgress,
  Stack,
  Divider
} from '@mui/material';
import { authService } from '@/services/auth/authService';

import { modelsService } from '@/services/api/models';

import { financialApi } from '@/services/api/financial';
import { analyticsService } from '@/services/api/analytics';

import { socketManager } from '@/services/socket/socketManager';

interface TestResult {
  service: string;
  endpoint: string;
  status: 'pending' | 'success' | 'error';
  message?: string;
  data?: any;
}

const ApiTestPage: React.FC = () => {
  const [results, setResults] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState('test@example.com');
  const [password, setPassword] = useState('password123');

  const addResult = (result: TestResult) => {
    setResults(prev => [...prev, result]);
  };

  const testAuth = async () => {
    // Test login
    try {
      const response = await authService.login({ email, password });
      addResult({
        service: 'Auth',
        endpoint: '/auth/login',
        status: 'success',
        message: 'Login successful',
        data: response,
      });
      return true;
    } catch (error: any) {
      addResult({
        service: 'Auth',
        endpoint: '/auth/login',
        status: 'error',
        message: error.response?.data?.detail || error.message,
      });
      return false;
    }
  };

  const testCurrentUser = async () => {
    try {
      const user = await authService.checkAuth();
      addResult({
        service: 'Auth',
        endpoint: '/auth/me',
        status: 'success',
        message: 'Current user retrieved',
        data: user,
      });
    } catch (error: any) {
      addResult({
        service: 'Auth',
        endpoint: '/auth/me',
        status: 'error',
        message: error.response?.data?.detail || error.message,
      });
    }
  };

  const testModels = async () => {
    // Test model sync status (requires model ID)
    try {
      const modelId = 'test-model-id'; // You'll need a real model ID
      const status = await modelsService.getSyncStatus(modelId);
      addResult({
        service: 'Models',
        endpoint: '/orchestration/sync/{model_id}/status',
        status: 'success',
        data: status,
      });
    } catch (error: any) {
      addResult({
        service: 'Models',
        endpoint: '/orchestration/sync/{model_id}/status',
        status: 'error',
        message: error.response?.data?.detail || error.message,
      });
    }
  };

  const testFinancial = async () => {
    try {
      const rules = await financialApi.getCommissionRules();
      addResult({
        service: 'Financial',
        endpoint: '/financial/commission/rules',
        status: 'success',
        data: rules,
      });
    } catch (error: any) {
      addResult({
        service: 'Financial',
        endpoint: '/financial/commission/rules',
        status: 'error',
        message: error.response?.data?.detail || error.message,
      });
    }
  };

  const testAnalytics = async () => {
    try {
      const modelId = 'test-model-id'; // You'll need a real model ID
      const summary = await analyticsService.getDashboardSummary(modelId, 'today');
      addResult({
        service: 'Analytics',
        endpoint: '/analytics/dashboard/{model_id}',
        status: 'success',
        data: summary,
      });
    } catch (error: any) {
      addResult({
        service: 'Analytics',
        endpoint: '/analytics/dashboard/{model_id}',
        status: 'error',
        message: error.response?.data?.detail || error.message,
      });
    }
  };

  const testSocketConnection = () => {
    socketManager.connect();
    
    socketManager.on('connect', () => {
      addResult({
        service: 'Socket.IO',
        endpoint: 'Main namespace',
        status: 'success',
        message: 'Connected to WebSocket',
      });
    });

    socketManager.on('error', (error) => {
      addResult({
        service: 'Socket.IO',
        endpoint: 'Main namespace',
        status: 'error',
        message: error.message || 'Connection error',
      });
    });

    socketManager.on('connected', (data) => {
      addResult({
        service: 'Socket.IO',
        endpoint: 'Authentication',
        status: 'success',
        message: 'Authenticated',
        data,
      });
    });

    // Check connection after a delay
    setTimeout(() => {
      if (!socketManager.isConnected()) {
        addResult({
          service: 'Socket.IO',
          endpoint: 'Connection check',
          status: 'error',
          message: 'Failed to establish connection',
        });
      }
    }, 5000);
  };

  const runAllTests = async () => {
    setLoading(true);
    setResults([]);

    // Test authentication first
    const authSuccess = await testAuth();
    
    if (authSuccess) {
      // Test other endpoints
      await testCurrentUser();
      await testModels();
      await testFinancial();
      await testAnalytics();
      testSocketConnection();
    }

    setLoading(false);
  };

  return (
    <Box sx={{ p: 3, maxWidth: 1200, mx: 'auto' }}>
      <Typography variant="h4" gutterBottom>
        API Connection Test
      </Typography>
      
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Test Credentials
          </Typography>
          <Stack spacing={2} sx={{ mb: 2 }}>
            <TextField
              label="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              fullWidth
            />
            <TextField
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              fullWidth
            />
          </Stack>
          <Button 
            variant="contained" 
            onClick={runAllTests}
            disabled={loading}
            fullWidth
          >
            {loading ? <CircularProgress size={24} /> : 'Run All Tests'}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Test Results
          </Typography>
          <Divider sx={{ mb: 2 }} />
          
          {results.length === 0 && (
            <Typography color="text.secondary">
              No tests run yet. Click "Run All Tests" to begin.
            </Typography>
          )}

          <Stack spacing={2}>
            {results.map((result, index) => (
              <Alert 
                key={index} 
                severity={result.status === 'success' ? 'success' : 'error'}
              >
                <Typography variant="subtitle2">
                  <strong>{result.service}</strong> - {result.endpoint}
                </Typography>
                {result.message && (
                  <Typography variant="body2">
                    {result.message}
                  </Typography>
                )}
                {result.data && (
                  <Typography variant="caption" component="pre" sx={{ mt: 1 }}>
                    {JSON.stringify(result.data, null, 2).substring(0, 200)}...
                  </Typography>
                )}
              </Alert>
            ))}
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
};

export default ApiTestPage;
