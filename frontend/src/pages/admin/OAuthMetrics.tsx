import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Grid,
  Card,
  CardContent,
  Paper,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Button,
  IconButton,
  Chip,
  Alert,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  Tab,
  Tooltip,
  Avatar,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  Divider,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Assessment as AssessmentIcon,
  Speed as SpeedIcon,
  Security as SecurityIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  Download as DownloadIcon,
  Refresh as RefreshIcon,
  Schedule as ScheduleIcon,
  People as PeopleIcon,
  Apps as AppsIcon,
  VpnKey as KeyIcon,
  Block as BlockIcon,
  BarChart as BarChartIcon,
  PieChart as PieChartIcon,
  Timeline as TimelineIcon,
  FilterList as FilterIcon,
  CalendarToday as CalendarIcon,
} from '@mui/icons-material';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
  ComposedChart,
  Scatter,
  ScatterChart,
  ZAxis,
} from 'recharts';
import { format, subDays, startOfDay, endOfDay, subHours } from 'date-fns';
import { useOAuthMetrics } from '../../hooks/useOAuthMetrics';
import { MetricCard } from '../../components/metrics/MetricCard';
import { RealTimeMetrics } from '../../components/metrics/RealTimeMetrics';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index, ...other }) => {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`metrics-tabpanel-${index}`}
      aria-labelledby={`metrics-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
};

const COLORS = {
  primary: '#1976d2',
  secondary: '#dc004e',
  success: '#4caf50',
  warning: '#ff9800',
  error: '#f44336',
  info: '#2196f3',
};

const CHART_COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#82CA9D'];

const OAuthMetrics: React.FC = () => {
  const {
    getOverviewMetrics,
    getAuthenticationMetrics,
    getTokenMetrics,
    getClientMetrics,
    getSecurityMetrics,
    getPerformanceMetrics,
    exportMetrics,
  } = useOAuthMetrics();

  const [activeTab, setActiveTab] = useState(0);
  const [timeRange, setTimeRange] = useState(7); // days
  const [granularity, setGranularity] = useState<'hour' | 'day' | 'week' | 'month'>('day');
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [metrics, setMetrics] = useState<any>(null);

  useEffect(() => {
    fetchMetrics();
    
    if (autoRefresh) {
      const interval = setInterval(fetchMetrics, 30000); // Refresh every 30 seconds
      return () => clearInterval(interval);
    }
  }, [activeTab, timeRange, granularity, autoRefresh]);

  const fetchMetrics = async () => {
    setLoading(true);
    try {
      const startDate = startOfDay(subDays(new Date(), timeRange));
      const endDate = endOfDay(new Date());
      
      const data = await Promise.all([
        getOverviewMetrics({ startDate, endDate, granularity }),
        getAuthenticationMetrics({ startDate, endDate, granularity }),
        getTokenMetrics({ startDate, endDate, granularity }),
        getClientMetrics({ startDate, endDate, granularity }),
        getSecurityMetrics({ startDate, endDate, granularity }),
        getPerformanceMetrics({ startDate, endDate, granularity }),
      ]);

      setMetrics({
        overview: data[0],
        authentication: data[1],
        tokens: data[2],
        clients: data[3],
        security: data[4],
        performance: data[5],
      });
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    const data = await exportMetrics({
      startDate: startOfDay(subDays(new Date(), timeRange)),
      endDate: endOfDay(new Date()),
      format: 'csv',
    });
    downloadFile(data, `oauth-metrics-${format(new Date(), 'yyyy-MM-dd')}.csv`);
  };

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  // Mock data for demonstration
  const mockMetrics = {
    overview: {
      summary: {
        totalRequests: 1524367,
        successRate: 99.7,
        activeUsers: 45231,
        activeClients: 892,
        averageResponseTime: 145,
        errorRate: 0.3,
      },
      trends: Array.from({ length: timeRange }, (_, i) => ({
        date: format(subDays(new Date(), timeRange - i - 1), 'MMM dd'),
        requests: Math.floor(Math.random() * 100000) + 150000,
        users: Math.floor(Math.random() * 5000) + 40000,
        errors: Math.floor(Math.random() * 500) + 100,
      })),
    },
    authentication: {
      flowDistribution: [
        { name: 'Authorization Code', value: 65, count: 991234 },
        { name: 'Client Credentials', value: 20, count: 304873 },
        { name: 'Refresh Token', value: 10, count: 152437 },
        { name: 'Implicit', value: 3, count: 45734 },
        { name: 'Password', value: 2, count: 30489 },
      ],
      successRates: {
        authorizationCode: 99.8,
        clientCredentials: 99.9,
        refreshToken: 99.5,
        implicit: 98.2,
        password: 97.5,
      },
      hourlyPattern: Array.from({ length: 24 }, (_, hour) => ({
        hour: `${hour}:00`,
        authentications: Math.floor(Math.random() * 10000) + 
          (hour >= 9 && hour <= 17 ? 15000 : 5000),
        failures: Math.floor(Math.random() * 100) + 10,
      })),
    },
    tokens: {
      issuedVsRevoked: Array.from({ length: timeRange }, (_, i) => ({
        date: format(subDays(new Date(), timeRange - i - 1), 'MMM dd'),
        issued: Math.floor(Math.random() * 50000) + 80000,
        revoked: Math.floor(Math.random() * 10000) + 5000,
        expired: Math.floor(Math.random() * 15000) + 10000,
      })),
      typeDistribution: [
        { type: 'Access Token', count: 892345, percentage: 55 },
        { type: 'Refresh Token', count: 534212, percentage: 33 },
        { type: 'ID Token', count: 194523, percentage: 12 },
      ],
      lifetimeAnalysis: {
        averageLifetime: 3600,
        medianLifetime: 3300,
        p95Lifetime: 7200,
        p99Lifetime: 10800,
      },
    },
    clients: {
      topClients: [
        { name: 'Web Dashboard', requests: 453234, users: 12453, errorRate: 0.2 },
        { name: 'Mobile App', requests: 342123, users: 23421, errorRate: 0.5 },
        { name: 'API Gateway', requests: 234521, users: 8923, errorRate: 0.1 },
        { name: 'Analytics Service', requests: 123456, users: 4532, errorRate: 0.3 },
        { name: 'Third-party Integration', requests: 98234, users: 2341, errorRate: 0.8 },
      ],
      clientGrowth: Array.from({ length: timeRange }, (_, i) => ({
        date: format(subDays(new Date(), timeRange - i - 1), 'MMM dd'),
        newClients: Math.floor(Math.random() * 50) + 10,
        totalClients: 800 + i * 10 + Math.floor(Math.random() * 20),
      })),
      scopeUsage: [
        { scope: 'openid', usage: 95 },
        { scope: 'profile', usage: 88 },
        { scope: 'email', usage: 82 },
        { scope: 'api:read', usage: 67 },
        { scope: 'api:write', usage: 45 },
        { scope: 'offline_access', usage: 38 },
      ],
    },
    security: {
      threats: [
        { type: 'Suspicious Login Attempts', count: 234, severity: 'high', trend: 'up' },
        { type: 'Rate Limit Violations', count: 1523, severity: 'medium', trend: 'stable' },
        { type: 'Invalid Token Usage', count: 3421, severity: 'low', trend: 'down' },
        { type: 'PKCE Violations', count: 89, severity: 'high', trend: 'down' },
        { type: 'Expired Token Reuse', count: 567, severity: 'low', trend: 'stable' },
      ],
      geographicDistribution: [
        { country: 'United States', requests: 453234, suspicious: 234 },
        { country: 'United Kingdom', requests: 234123, suspicious: 123 },
        { country: 'Germany', requests: 123456, suspicious: 45 },
        { country: 'Japan', requests: 98234, suspicious: 23 },
        { country: 'Australia', requests: 67234, suspicious: 12 },
      ],
      ipAnalysis: {
        uniqueIPs: 23456,
        blacklistedIPs: 34,
        whitelistedIPs: 234,
        suspiciousIPs: 89,
      },
    },
    performance: {
      responseTime: Array.from({ length: 24 }, (_, hour) => ({
        hour: `${hour}:00`,
        p50: Math.floor(Math.random() * 50) + 80,
        p95: Math.floor(Math.random() * 100) + 150,
        p99: Math.floor(Math.random() * 200) + 250,
      })),
      endpointPerformance: [
        { endpoint: '/oauth/authorize', avgTime: 145, requests: 234523, errorRate: 0.2 },
        { endpoint: '/oauth/token', avgTime: 89, requests: 453234, errorRate: 0.1 },
        { endpoint: '/oauth/introspect', avgTime: 45, requests: 123456, errorRate: 0.3 },
        { endpoint: '/oauth/revoke', avgTime: 67, requests: 34521, errorRate: 0.1 },
        { endpoint: '/oauth/userinfo', avgTime: 123, requests: 89234, errorRate: 0.4 },
      ],
      errorAnalysis: {
        '400': 1234,
        '401': 3421,
        '403': 892,
        '429': 1523,
        '500': 234,
        '503': 45,
      },
    },
  };

  const data = metrics || mockMetrics;

  return (
    <Container maxWidth={false} sx={{ mt: 4, mb: 4 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" gutterBottom>
            OAuth Metrics Dashboard
          </Typography>
          <Typography variant="body2" color="textSecondary">
            Real-time analytics and insights for your OAuth implementation
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Time Range</InputLabel>
            <Select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value as number)}
              label="Time Range"
            >
              <MenuItem value={1}>Last 24 hours</MenuItem>
              <MenuItem value={7}>Last 7 days</MenuItem>
              <MenuItem value={14}>Last 14 days</MenuItem>
              <MenuItem value={30}>Last 30 days</MenuItem>
              <MenuItem value={90}>Last 90 days</MenuItem>
            </Select>
          </FormControl>
          
          <FormControl size="small" sx={{ minWidth: 100 }}>
            <InputLabel>Granularity</InputLabel>
            <Select
              value={granularity}
              onChange={(e) => setGranularity(e.target.value as any)}
              label="Granularity"
            >
              <MenuItem value="hour">Hourly</MenuItem>
              <MenuItem value="day">Daily</MenuItem>
              <MenuItem value="week">Weekly</MenuItem>
              <MenuItem value="month">Monthly</MenuItem>
            </Select>
          </FormControl>

          <Tooltip title={autoRefresh ? "Auto-refresh enabled" : "Auto-refresh disabled"}>
            <IconButton
              onClick={() => setAutoRefresh(!autoRefresh)}
              color={autoRefresh ? "primary" : "default"}
            >
              <RefreshIcon />
            </IconButton>
          </Tooltip>

          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            onClick={handleExport}
          >
            Export
          </Button>
        </Box>
      </Box>

      {/* Key Metrics Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={2}>
          <MetricCard
            title="Total Requests"
            value={data.overview.summary.totalRequests.toLocaleString()}
            trend={12.5}
            icon={<AssessmentIcon />}
            color="primary"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <MetricCard
            title="Success Rate"
            value={`${data.overview.summary.successRate}%`}
            trend={0.5}
            icon={<CheckCircleIcon />}
            color="success"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <MetricCard
            title="Active Users"
            value={data.overview.summary.activeUsers.toLocaleString()}
            trend={8.3}
            icon={<PeopleIcon />}
            color="info"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <MetricCard
            title="Active Clients"
            value={data.overview.summary.activeClients}
            trend={3.2}
            icon={<AppsIcon />}
            color="secondary"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <MetricCard
            title="Avg Response"
            value={`${data.overview.summary.averageResponseTime}ms`}
            trend={-5.4}
            icon={<SpeedIcon />}
            color="warning"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <MetricCard
            title="Error Rate"
            value={`${data.overview.summary.errorRate}%`}
            trend={-2.1}
            icon={<ErrorIcon />}
            color="error"
          />
        </Grid>
      </Grid>

      {/* Real-time Metrics */}
      <RealTimeMetrics />

      {/* Main Content Tabs */}
      <Card>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={activeTab} onChange={handleTabChange} variant="scrollable" scrollButtons="auto">
            <Tab label="Overview" icon={<DashboardIcon />} iconPosition="start" />
            <Tab label="Authentication" icon={<SecurityIcon />} iconPosition="start" />
            <Tab label="Tokens" icon={<KeyIcon />} iconPosition="start" />
            <Tab label="Clients" icon={<AppsIcon />} iconPosition="start" />
            <Tab label="Security" icon={<WarningIcon />} iconPosition="start" />
            <Tab label="Performance" icon={<SpeedIcon />} iconPosition="start" />
          </Tabs>
        </Box>

        {loading && <LinearProgress />}

        {/* Overview Tab */}
        <TabPanel value={activeTab} index={0}>
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Request Trends
                  </Typography>
                  <ResponsiveContainer width="100%" height={300}>
                    <AreaChart data={data.overview.trends}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" />
                      <YAxis />
                      <RechartsTooltip />
                      <Legend />
                      <Area
                        type="monotone"
                        dataKey="requests"
                        stroke={COLORS.primary}
                        fill={COLORS.primary}
                        fillOpacity={0.6}
                        name="Requests"
                      />
                      <Area
                        type="monotone"
                        dataKey="users"
                        stroke={COLORS.success}
                        fill={COLORS.success}
                        fillOpacity={0.6}
                        name="Active Users"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </TabPanel>

        {/* Authentication Tab */}
        <TabPanel value={activeTab} index={1}>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    OAuth Flow Distribution
                  </Typography>
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie
                        data={data.authentication.flowDistribution}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={({ name, value }) => `${name}: ${value}%`}
                        outerRadius={80}
                        fill="#8884d8"
                        dataKey="value"
                      >
                        {data.authentication.flowDistribution.map((entry: any, index: number) => (
                          <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                        ))}
                      </Pie>
                      <RechartsTooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Success Rates by Flow
                  </Typography>
                  <List>
                    {Object.entries(data.authentication.successRates).map(([flow, rate]) => (
                      <ListItem key={flow}>
                        <ListItemText
                          primary={flow.replace(/([A-Z])/g, ' $1').trim()}
                          secondary={
                            <LinearProgress
                              variant="determinate"
                              value={rate as number}
                              sx={{ mt: 1 }}
                            />
                          }
                        />
                        <Typography variant="body2">
                          {rate}%
                        </Typography>
                      </ListItem>
                    ))}
                  </List>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Hourly Authentication Pattern
                  </Typography>
                  <ResponsiveContainer width="100%" height={300}>
                    <ComposedChart data={data.authentication.hourlyPattern}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="hour" />
                      <YAxis yAxisId="left" />
                      <YAxis yAxisId="right" orientation="right" />
                      <RechartsTooltip />
                      <Legend />
                      <Bar
                        yAxisId="left"
                        dataKey="authentications"
                        fill={COLORS.primary}
                        name="Authentications"
                      />
                      <Line
                        yAxisId="right"
                        type="monotone"
                        dataKey="failures"
                        stroke={COLORS.error}
                        name="Failures"
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </TabPanel>

        {/* Tokens Tab */}
        <TabPanel value={activeTab} index={2}>
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Token Lifecycle
                  </Typography>
                  <ResponsiveContainer width="100%" height={300}>
                    <AreaChart data={data.tokens.issuedVsRevoked}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" />
                      <YAxis />
                      <RechartsTooltip />
                      <Legend />
                      <Area
                        type="monotone"
                        dataKey="issued"
                        stackId="1"
                        stroke={COLORS.success}
                        fill={COLORS.success}
                        name="Issued"
                      />
                      <Area
                        type="monotone"
                        dataKey="revoked"
                        stackId="1"
                        stroke={COLORS.warning}
                        fill={COLORS.warning}
                        name="Revoked"
                      />
                      <Area
                        type="monotone"
                        dataKey="expired"
                        stackId="1"
                        stroke={COLORS.error}
                        fill={COLORS.error}
                        name="Expired"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Token Type Distribution
                  </Typography>
                  <List>
                    {data.tokens.typeDistribution.map((item: any) => (
                      <ListItem key={item.type}>
                        <ListItemAvatar>
                          <Avatar sx={{ bgcolor: CHART_COLORS[0] }}>
                            <KeyIcon />
                          </Avatar>
                        </ListItemAvatar>
                        <ListItemText
                          primary={item.type}
                          secondary={`${item.count.toLocaleString()} tokens`}
                        />
                        <Chip label={`${item.percentage}%`} />
                      </ListItem>
                    ))}
                  </List>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Token Lifetime Analysis
                  </Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={6}>
                      <Typography variant="body2" color="textSecondary">
                        Average Lifetime
                      </Typography>
                      <Typography variant="h5">
                        {Math.floor(data.tokens.lifetimeAnalysis.averageLifetime / 60)} min
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="body2" color="textSecondary">
                        Median Lifetime
                      </Typography>
                      <Typography variant="h5">
                        {Math.floor(data.tokens.lifetimeAnalysis.medianLifetime / 60)} min
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="body2" color="textSecondary">
                        95th Percentile
                      </Typography>
                      <Typography variant="h5">
                        {Math.floor(data.tokens.lifetimeAnalysis.p95Lifetime / 60)} min
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="body2" color="textSecondary">
                        99th Percentile
                      </Typography>
                      <Typography variant="h5">
                        {Math.floor(data.tokens.lifetimeAnalysis.p99Lifetime / 60)} min
                      </Typography>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </TabPanel>

        {/* Clients Tab */}
        <TabPanel value={activeTab} index={3}>
          <Grid container spacing={3}>
            <Grid item xs={12} md={8}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Top Clients by Requests
                  </Typography>
                  <TableContainer>
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableCell>Client</TableCell>
                          <TableCell align="right">Requests</TableCell>
                          <TableCell align="right">Users</TableCell>
                          <TableCell align="right">Error Rate</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {data.clients.topClients.map((client: any) => (
                          <TableRow key={client.name}>
                            <TableCell>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <AppsIcon fontSize="small" color="action" />
                                <Typography variant="body2">{client.name}</Typography>
                              </Box>
                            </TableCell>
                            <TableCell align="right">
                              {client.requests.toLocaleString()}
                            </TableCell>
                            <TableCell align="right">
                              {client.users.toLocaleString()}
                            </TableCell>
                            <TableCell align="right">
                              <Chip
                                label={`${client.errorRate}%`}
                                size="small"
                                color={client.errorRate > 1 ? 'error' : 'success'}
                              />
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={4}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Scope Usage
                  </Typography>
                  <List>
                    {data.clients.scopeUsage.map((scope: any) => (
                      <ListItem key={scope.scope}>
                        <ListItemText
                          primary={scope.scope}
                          secondary={
                            <LinearProgress
                              variant="determinate"
                              value={scope.usage}
                              sx={{ mt: 1 }}
                            />
                          }
                        />
                        <Typography variant="body2">
                          {scope.usage}%
                        </Typography>
                      </ListItem>
                    ))}
                  </List>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Client Growth
                  </Typography>
                  <ResponsiveContainer width="100%" height={300}>
                    <ComposedChart data={data.clients.clientGrowth}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" />
                      <YAxis yAxisId="left" />
                      <YAxis yAxisId="right" orientation="right" />
                      <RechartsTooltip />
                      <Legend />
                      <Bar
                        yAxisId="left"
                        dataKey="newClients"
                        fill={COLORS.success}
                        name="New Clients"
                      />
                      <Line
                        yAxisId="right"
                        type="monotone"
                        dataKey="totalClients"
                        stroke={COLORS.primary}
                        name="Total Clients"
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </TabPanel>

        {/* Security Tab */}
        <TabPanel value={activeTab} index={4}>
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Alert severity="warning" sx={{ mb: 2 }}>
                <Typography variant="body2">
                  {data.security.threats.filter((t: any) => t.severity === 'high').length} high severity threats detected in the last {timeRange} days
                </Typography>
              </Alert>
            </Grid>

            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Security Threats
                  </Typography>
                  <List>
                    {data.security.threats.map((threat: any) => (
                      <ListItem key={threat.type}>
                        <ListItemAvatar>
                          <Avatar sx={{ 
                            bgcolor: threat.severity === 'high' ? 'error.main' : 
                                    threat.severity === 'medium' ? 'warning.main' : 'info.main' 
                          }}>
                            <WarningIcon />
                          </Avatar>
                        </ListItemAvatar>
                        <ListItemText
                          primary={threat.type}
                          secondary={`${threat.count} incidents`}
                        />
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          {threat.trend === 'up' && <TrendingUpIcon color="error" />}
                          {threat.trend === 'down' && <TrendingDownIcon color="success" />}
                          <Chip
                            label={threat.severity}
                            size="small"
                            color={
                              threat.severity === 'high' ? 'error' :
                              threat.severity === 'medium' ? 'warning' : 'info'
                            }
                          />
                        </Box>
                      </ListItem>
                    ))}
                  </List>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Geographic Distribution
                  </Typography>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Country</TableCell>
                          <TableCell align="right">Requests</TableCell>
                          <TableCell align="right">Suspicious</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {data.security.geographicDistribution.map((geo: any) => (
                          <TableRow key={geo.country}>
                            <TableCell>{geo.country}</TableCell>
                            <TableCell align="right">
                              {geo.requests.toLocaleString()}
                            </TableCell>
                            <TableCell align="right">
                              <Chip
                                label={geo.suspicious}
                                size="small"
                                color={geo.suspicious > 100 ? 'error' : 'default'}
                              />
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    IP Analysis
                  </Typography>
                  <Grid container spacing={3}>
                    <Grid item xs={6} sm={3}>
                      <Typography variant="h4">
                        {data.security.ipAnalysis.uniqueIPs.toLocaleString()}
                      </Typography>
                      <Typography variant="body2" color="textSecondary">
                        Unique IPs
                      </Typography>
                    </Grid>
                    <Grid item xs={6} sm={3}>
                      <Typography variant="h4" color="error.main">
                        {data.security.ipAnalysis.blacklistedIPs}
                      </Typography>
                      <Typography variant="body2" color="textSecondary">
                        Blacklisted
                      </Typography>
                    </Grid>
                    <Grid item xs={6} sm={3}>
                      <Typography variant="h4" color="success.main">
                        {data.security.ipAnalysis.whitelistedIPs}
                      </Typography>
                      <Typography variant="body2" color="textSecondary">
                        Whitelisted
                      </Typography>
                    </Grid>
                    <Grid item xs={6} sm={3}>
                      <Typography variant="h4" color="warning.main">
                        {data.security.ipAnalysis.suspiciousIPs}
                      </Typography>
                      <Typography variant="body2" color="textSecondary">
                        Suspicious
                      </Typography>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </TabPanel>

        {/* Performance Tab */}
        <TabPanel value={activeTab} index={5}>
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Response Time Distribution
                  </Typography>
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={data.performance.responseTime}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="hour" />
                      <YAxis />
                      <RechartsTooltip />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="p50"
                        stroke={COLORS.success}
                        name="P50 (Median)"
                      />
                      <Line
                        type="monotone"
                        dataKey="p95"
                        stroke={COLORS.warning}
                        name="P95"
                      />
                      <Line
                        type="monotone"
                        dataKey="p99"
                        stroke={COLORS.error}
                        name="P99"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={8}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Endpoint Performance
                  </Typography>
                  <TableContainer>
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableCell>Endpoint</TableCell>
                          <TableCell align="right">Avg Time (ms)</TableCell>
                          <TableCell align="right">Requests</TableCell>
                          <TableCell align="right">Error Rate</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {data.performance.endpointPerformance.map((endpoint: any) => (
                          <TableRow key={endpoint.endpoint}>
                            <TableCell>
                              <Typography variant="body2" fontFamily="monospace">
                                {endpoint.endpoint}
                              </Typography>
                            </TableCell>
                            <TableCell align="right">
                              <Chip
                                label={endpoint.avgTime}
                                size="small"
                                color={
                                  endpoint.avgTime < 100 ? 'success' :
                                  endpoint.avgTime < 200 ? 'warning' : 'error'
                                }
                              />
                            </TableCell>
                            <TableCell align="right">
                              {endpoint.requests.toLocaleString()}
                            </TableCell>
                            <TableCell align="right">
                              {endpoint.errorRate}%
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={4}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Error Distribution
                  </Typography>
                  <List>
                    {Object.entries(data.performance.errorAnalysis).map(([code, count]) => (
                      <ListItem key={code}>
                        <ListItemAvatar>
                          <Avatar sx={{ 
                            bgcolor: code.startsWith('5') ? 'error.main' :
                                    code.startsWith('4') ? 'warning.main' : 'info.main'
                          }}>
                            {code}
                          </Avatar>
                        </ListItemAvatar>
                        <ListItemText
                          primary={`HTTP ${code}`}
                          secondary={getErrorDescription(code)}
                        />
                        <Typography variant="body2">
                          {(count as number).toLocaleString()}
                        </Typography>
                      </ListItem>
                    ))}
                  </List>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </TabPanel>
      </Card>
    </Container>
  );
};

// Helper functions
const getErrorDescription = (code: string): string => {
  const descriptions: Record<string, string> = {
    '400': 'Bad Request',
    '401': 'Unauthorized',
    '403': 'Forbidden',
    '429': 'Too Many Requests',
    '500': 'Internal Server Error',
    '503': 'Service Unavailable',
  };
  return descriptions[code] || 'Unknown Error';
};

const downloadFile = (data: string, filename: string): void => {
  const blob = new Blob([data], { type: 'text/csv' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
};

export default OAuthMetrics;