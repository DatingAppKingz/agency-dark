import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  Skeleton,
  Alert,
  Chip } from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  AccessTime as TimeIcon,
  Error as ErrorIcon,
  CheckCircle as SuccessIcon } from '@mui/icons-material';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar } from 'recharts';
import { format } from 'date-fns';
import { ApiKey } from '@/types/apiKeys';
import { useApiKeyUsageStats } from '@/hooks/useApiKeys';

interface ApiKeyStatsDialogProps {
  open: boolean;
  onClose: () => void;
  apiKey: ApiKey;
}

const ApiKeyStatsDialog: React.FC<ApiKeyStatsDialogProps> = ({
  open,
  onClose,
  apiKey }) => {
  const { data: stats, isPending, error } = useApiKeyUsageStats(apiKey.id);

  const formatNumber = (num: number): string => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
    return num.toString();
  };

  const getSuccessRate = () => {
    if (!stats) return 0;
    const total = stats.total_requests;
    const errors = stats.total_errors;
    if (total === 0) return 100;
    return ((total - errors) / total * 100).toFixed(1);
  };

  const getTrend = () => {
    if (!stats?.daily_usage || stats.daily_usage.length < 2) return 0;
    const recent = stats.daily_usage.slice(-7);
    const previous = stats.daily_usage.slice(-14, -7);
    
    const recentTotal = recent.reduce((sum, day) => sum + day.count, 0);
    const previousTotal = previous.reduce((sum, day) => sum + day.count, 0);
    
    if (previousTotal === 0) return 100;
    return ((recentTotal - previousTotal) / previousTotal * 100).toFixed(0);
  };

  const trend = getTrend();

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">API Key Usage Statistics</Typography>
          <Chip label={apiKey.provider} size="small" color="primary" />
        </Box>
      </DialogTitle>
      
      <DialogContent>
        {isPending && (
          <Box>
            <Grid container spacing={3}>
              {[1, 2, 3, 4].map((i) => (
                <Grid item xs={12} sm={6} md={3} key={i}>
                  <Skeleton variant="rectangular" height={120} />
                </Grid>
              ))}
            </Grid>
            <Box mt={3}>
              <Skeleton variant="rectangular" height={300} />
            </Box>
          </Box>
        )}

        {error && (
          <Alert severity="error">
            Failed to load usage statistics. Please try again later.
          </Alert>
        )}

        {stats && (
          <>
            {/* Summary Cards */}
            <Grid container spacing={3} mb={3}>
              <Grid item xs={12} sm={6} md={3}>
                <Card>
                  <CardContent>
                    <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                      <Box>
                        <Typography color="text.secondary" gutterBottom>
                          Total Requests
                        </Typography>
                        <Typography variant="h4">
                          {formatNumber(stats.total_requests)}
                        </Typography>
                      </Box>
                      <Box display="flex" alignItems="center" gap={0.5}>
                        {Number(trend) > 0 ? (
                          <TrendingUpIcon color="success" />
                        ) : Number(trend) < 0 ? (
                          <TrendingDownIcon color="error" />
                        ) : null}
                        {trend !== 0 && (
                          <Typography 
                            variant="body2" 
                            color={Number(trend) > 0 ? 'success.main' : 'error.main'}
                          >
                            {trend}%
                          </Typography>
                        )}
                      </Box>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} sm={6} md={3}>
                <Card>
                  <CardContent>
                    <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                      <Box>
                        <Typography color="text.secondary" gutterBottom>
                          Success Rate
                        </Typography>
                        <Typography variant="h4">
                          {getSuccessRate()}%
                        </Typography>
                      </Box>
                      <SuccessIcon color="success" />
                    </Box>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} sm={6} md={3}>
                <Card>
                  <CardContent>
                    <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                      <Box>
                        <Typography color="text.secondary" gutterBottom>
                          Total Errors
                        </Typography>
                        <Typography variant="h4">
                          {formatNumber(stats.total_errors)}
                        </Typography>
                      </Box>
                      <ErrorIcon color="error" />
                    </Box>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} sm={6} md={3}>
                <Card>
                  <CardContent>
                    <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                      <Box>
                        <Typography color="text.secondary" gutterBottom>
                          Avg Response Time
                        </Typography>
                        <Typography variant="h4">
                          {stats.average_response_time.toFixed(0)}ms
                        </Typography>
                      </Box>
                      <TimeIcon color="primary" />
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>

            {/* Usage Chart */}
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Daily Usage (Last 30 Days)
                </Typography>
                <Box height={300}>
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={stats.daily_usage}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis 
                        dataKey="date" 
                        tickFormatter={(date) => format(new Date(date), 'MMM dd')}
                      />
                      <YAxis />
                      <Tooltip 
                        labelFormatter={(date) => format(new Date(date), 'MMM dd, yyyy')}
                        formatter={(value: number) => [formatNumber(value), 'Requests']}
                      />
                      <Area 
                        type="monotone" 
                        dataKey="count" 
                        stroke="#8884d8" 
                        fill="#8884d8" 
                        fillOpacity={0.6}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </Box>
              </CardContent>
            </Card>

            {/* Error Chart */}
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Error Rate
                </Typography>
                <Box height={200}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={stats.daily_usage}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis 
                        dataKey="date" 
                        tickFormatter={(date) => format(new Date(date), 'MMM dd')}
                      />
                      <YAxis />
                      <Tooltip 
                        labelFormatter={(date) => format(new Date(date), 'MMM dd, yyyy')}
                        formatter={(value: number) => [value, 'Errors']}
                      />
                      <Bar dataKey="errors" fill="#f44336" />
                    </BarChart>
                  </ResponsiveContainer>
                </Box>
              </CardContent>
            </Card>

            {/* Last Error */}
            {stats.last_error && (
              <Alert severity="warning" sx={{ mt: 3 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Last Error
                </Typography>
                <Typography variant="body2">
                  {stats.last_error}
                </Typography>
              </Alert>
            )}
          </>
        )}
      </DialogContent>
      
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

export default ApiKeyStatsDialog;
