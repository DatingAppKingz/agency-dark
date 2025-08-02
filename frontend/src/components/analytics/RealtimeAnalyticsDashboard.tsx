import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Grid,
  Typography,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  ToggleButton,
  ToggleButtonGroup,
  Paper,
  Skeleton,
  Alert,
  Chip,
  LinearProgress,
  useTheme
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  AttachMoney,
  People,
  Visibility,
  Message,
  Speed
} from '@mui/icons-material';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { format, parseISO } from 'date-fns';

interface MetricData {
  value: number;
  count: number;
  min: number;
  max: number;
  avg: number;
  std_dev: number;
  timestamp: string;
}

interface RealtimeMetrics {
  revenue?: MetricData[];
  subscribers?: MetricData[];
  content_views?: MetricData[];
  messages?: MetricData[];
  conversion_rate?: MetricData[];
  engagement_rate?: MetricData[];
}

interface MetricSummary {
  revenue: {
    total: number;
    count: number;
    average: number;
  };
  subscribers: {
    total: number;
    new: number;
    growth_rate: number;
  };
  engagement: {
    message_count: number;
    content_views: number;
    avg_response_time: number;
  };
  performance: {
    avg_processing_time: number;
    error_counts: Record<string, number>;
    active_subscribers: number;
  };
}

interface RealtimeAnalyticsDashboardProps {
  agencyId: string;
  modelId?: string;
}

// const COLORS = ['#8884d8', '#82ca9d', '#ffc658', '#ff7c7c', '#8dd1e1', '#d084d0'];

const RealtimeAnalyticsDashboard: React.FC<RealtimeAnalyticsDashboardProps> = ({
  agencyId,
  modelId
}) => {
  const theme = useTheme();
  const [metrics, setMetrics] = useState<RealtimeMetrics>({});
  const [summary, setSummary] = useState<MetricSummary | null>(null);
  const [timeWindow, setTimeWindow] = useState<string>('1h');
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>(['revenue', 'subscribers']);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);

  // Format currency
  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value);
  };

  // Format large numbers
  const formatNumber = (value: number) => {
    if (value >= 1000000) {
      return `${(value / 1000000).toFixed(1)}M`;
    } else if (value >= 1000) {
      return `${(value / 1000).toFixed(1)}K`;
    }
    return value.toString();
  };

  // Calculate percentage change
  // const calculateChange = (current: number, previous: number) => {
  //   if (previous === 0) return 0;
  //   return ((current - previous) / previous) * 100;
  // };

  // WebSocket connection
  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    const wsUrl = `${import.meta.env.VITE_WS_URL || 'ws://localhost:8000'}/api/v1/analytics/realtime/ws/${agencyId}${modelId ? `?model_id=${modelId}` : ''}`;
    
    try {
      const ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        setConnectionError(null);
        reconnectAttemptsRef.current = 0;
        
        // Subscribe to metrics
        ws.send(JSON.stringify({
          type: 'subscribe',
          metrics: selectedMetrics
        }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'initial') {
            setSummary(data.data);
            setIsLoading(false);
          } else if (data.type === 'update') {
            // Update metrics
            setMetrics(prev => ({
              ...prev,
              ...data.metrics
            }));
          }
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setConnectionError('Connection error occurred');
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
        
        // Attempt to reconnect with exponential backoff
        const attempts = reconnectAttemptsRef.current;
        if (attempts < 5) {
          const delay = Math.min(1000 * Math.pow(2, attempts), 30000);
          reconnectTimeoutRef.current = window.setTimeout(() => {
            reconnectAttemptsRef.current += 1;
            connectWebSocket();
          }, delay);
        } else {
          setConnectionError('Unable to connect to real-time updates');
        }
      };

      wsRef.current = ws;
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      setConnectionError('Failed to establish connection');
    }
  }, [agencyId, modelId, selectedMetrics]);

  // Disconnect WebSocket
  const disconnectWebSocket = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  // Initialize connection
  useEffect(() => {
    connectWebSocket();
    
    // Cleanup on unmount
    return () => {
      disconnectWebSocket();
    };
  }, [connectWebSocket, disconnectWebSocket]);

  // Handle metric selection change
  const handleMetricChange = (newMetrics: string[]) => {
    setSelectedMetrics(newMetrics);
    
    // Update subscription
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'subscribe',
        metrics: newMetrics
      }));
    }
  };

  // Prepare chart data
  const prepareChartData = (metricData: MetricData[] | undefined) => {
    if (!metricData) return [];
    
    return metricData.map(item => ({
      time: format(parseISO(item.timestamp), 'HH:mm'),
      value: item.value,
      avg: item.avg,
      min: item.min,
      max: item.max
    }));
  };

  // Metric card component
  const MetricCard: React.FC<{
    title: string;
    value: number | string;
    change?: number;
    icon: React.ReactNode;
    color?: string;
    prefix?: string;
    suffix?: string;
  }> = ({ title, value, change, icon, color = theme.palette.primary.main, prefix = '', suffix = '' }) => (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Box>
            <Typography color="textSecondary" gutterBottom variant="body2">
              {title}
            </Typography>
            <Typography variant="h4" component="div">
              {prefix}{typeof value === 'number' ? formatNumber(value) : value}{suffix}
            </Typography>
            {change !== undefined && (
              <Box display="flex" alignItems="center" mt={1}>
                {change >= 0 ? (
                  <TrendingUp sx={{ color: theme.palette.success.main, mr: 0.5 }} />
                ) : (
                  <TrendingDown sx={{ color: theme.palette.error.main, mr: 0.5 }} />
                )}
                <Typography
                  variant="body2"
                  color={change >= 0 ? 'success.main' : 'error.main'}
                >
                  {Math.abs(change).toFixed(1)}%
                </Typography>
              </Box>
            )}
          </Box>
          <Box sx={{ color }}>
            {icon}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );

  if (isLoading) {
    return (
      <Box>
        <Grid container spacing={3}>
          {[1, 2, 3, 4].map(i => (
            <Grid item xs={12} sm={6} md={3} key={i}>
              <Skeleton variant="rectangular" height={120} />
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  return (
    <Box>
      {/* Connection Status */}
      <Box mb={2}>
        {connectionError ? (
          <Alert severity="error" onClose={() => setConnectionError(null)}>
            {connectionError}
          </Alert>
        ) : (
          <Box display="flex" alignItems="center" gap={1}>
            <Chip
              label={isConnected ? 'Connected' : 'Connecting...'}
              color={isConnected ? 'success' : 'warning'}
              size="small"
              icon={<Speed />}
            />
            {isConnected && (
              <Typography variant="caption" color="textSecondary">
                Real-time updates active
              </Typography>
            )}
          </Box>
        )}
      </Box>

      {/* Summary Cards */}
      <Grid container spacing={3} mb={3}>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Total Revenue"
            value={summary?.revenue.total || 0}
            change={10.5}
            icon={<AttachMoney sx={{ fontSize: 40 }} />}
            color={theme.palette.success.main}
            prefix="$"
          />
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Active Subscribers"
            value={summary?.subscribers.total || 0}
            change={summary?.subscribers.growth_rate}
            icon={<People sx={{ fontSize: 40 }} />}
            color={theme.palette.info.main}
          />
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Content Views"
            value={summary?.engagement.content_views || 0}
            change={5.2}
            icon={<Visibility sx={{ fontSize: 40 }} />}
            color={theme.palette.warning.main}
          />
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Messages"
            value={summary?.engagement.message_count || 0}
            change={-2.1}
            icon={<Message sx={{ fontSize: 40 }} />}
            color={theme.palette.secondary.main}
          />
        </Grid>
      </Grid>

      {/* Controls */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={6}>
            <FormControl fullWidth size="small">
              <InputLabel>Metrics</InputLabel>
              <Select
                multiple
                value={selectedMetrics}
                onChange={(e) => handleMetricChange(e.target.value as string[])}
                label="Metrics"
              >
                <MenuItem value="revenue">Revenue</MenuItem>
                <MenuItem value="subscribers">Subscribers</MenuItem>
                <MenuItem value="content_views">Content Views</MenuItem>
                <MenuItem value="messages">Messages</MenuItem>
                <MenuItem value="conversion_rate">Conversion Rate</MenuItem>
                <MenuItem value="engagement_rate">Engagement Rate</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12} md={6}>
            <ToggleButtonGroup
              value={timeWindow}
              exclusive
              onChange={(_, value) => value && setTimeWindow(value)}
              size="small"
              fullWidth
            >
              <ToggleButton value="1h">1 Hour</ToggleButton>
              <ToggleButton value="6h">6 Hours</ToggleButton>
              <ToggleButton value="24h">24 Hours</ToggleButton>
              <ToggleButton value="7d">7 Days</ToggleButton>
            </ToggleButtonGroup>
          </Grid>
        </Grid>
      </Paper>

      {/* Charts */}
      <Grid container spacing={3}>
        {/* Revenue Chart */}
        {selectedMetrics.includes('revenue') && (
          <Grid item xs={12} lg={6}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Revenue Trend
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={prepareChartData(metrics.revenue)}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="time" />
                  <YAxis tickFormatter={(value) => `$${formatNumber(value)}`} />
                  <Tooltip
                    formatter={(value: number) => formatCurrency(value)}
                    labelStyle={{ color: theme.palette.text.primary }}
                  />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke={theme.palette.primary.main}
                    fill={theme.palette.primary.light}
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </Paper>
          </Grid>
        )}

        {/* Subscribers Chart */}
        {selectedMetrics.includes('subscribers') && (
          <Grid item xs={12} lg={6}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Subscriber Growth
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={prepareChartData(metrics.subscribers)}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="time" />
                  <YAxis />
                  <Tooltip
                    labelStyle={{ color: theme.palette.text.primary }}
                  />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke={theme.palette.info.main}
                    strokeWidth={2}
                    dot={{ fill: theme.palette.info.main }}
                  />
                  <Line
                    type="monotone"
                    dataKey="avg"
                    stroke={theme.palette.info.light}
                    strokeDasharray="5 5"
                  />
                </LineChart>
              </ResponsiveContainer>
            </Paper>
          </Grid>
        )}

        {/* Engagement Metrics */}
        {(selectedMetrics.includes('content_views') || selectedMetrics.includes('messages')) && (
          <Grid item xs={12}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Engagement Metrics
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={prepareChartData(metrics.content_views)}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="time" />
                  <YAxis />
                  <Tooltip
                    labelStyle={{ color: theme.palette.text.primary }}
                  />
                  <Legend />
                  {selectedMetrics.includes('content_views') && (
                    <Bar
                      dataKey="value"
                      fill={theme.palette.warning.main}
                      name="Content Views"
                    />
                  )}
                  {selectedMetrics.includes('messages') && (
                    <Bar
                      dataKey="value"
                      fill={theme.palette.secondary.main}
                      name="Messages"
                    />
                  )}
                </BarChart>
              </ResponsiveContainer>
            </Paper>
          </Grid>
        )}
      </Grid>

      {/* Live Update Indicator */}
      {isConnected && (
        <Box mt={2}>
          <LinearProgress variant="indeterminate" sx={{ height: 2 }} />
          <Typography variant="caption" color="textSecondary" align="center" display="block" mt={1}>
            Receiving live updates...
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default RealtimeAnalyticsDashboard;