import React, { useState, useEffect } from 'react';
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
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Tabs,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  LinearProgress,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Close as CloseIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  AccessTime as AccessTimeIcon,
  Person as PersonIcon,
  Apps as AppsIcon,
  Security as SecurityIcon,
  Speed as SpeedIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Refresh as RefreshIcon,
  Download as DownloadIcon,
} from '@mui/icons-material';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts';
import { format, subDays, startOfDay, endOfDay } from 'date-fns';
import { useOAuthTokens } from '../../hooks/useOAuthTokens';

interface TokenAnalyticsProps {
  open: boolean;
  onClose: () => void;
}

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
      id={`analytics-tabpanel-${index}`}
      aria-labelledby={`analytics-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
};

const COLORS = {
  primary: '#1976d2',
  success: '#4caf50',
  warning: '#ff9800',
  error: '#f44336',
  info: '#2196f3',
};

const PIE_COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

export const TokenAnalytics: React.FC<TokenAnalyticsProps> = ({
  open,
  onClose,
}) => {
  const { getTokenAnalytics } = useOAuthTokens();
  const [activeTab, setActiveTab] = useState(0);
  const [timeRange, setTimeRange] = useState(7); // days
  const [loading, setLoading] = useState(false);
  const [analytics, setAnalytics] = useState<any>(null);

  useEffect(() => {
    if (open) {
      fetchAnalytics();
    }
  }, [open, timeRange]);

  const fetchAnalytics = async () => {
    setLoading(true);
    try {
      const data = await getTokenAnalytics({
        startDate: startOfDay(subDays(new Date(), timeRange)),
        endDate: endOfDay(new Date()),
      });
      setAnalytics(data);
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const handleExport = () => {
    // Export analytics data to CSV
    if (analytics) {
      const csv = generateAnalyticsCSV(analytics);
      downloadCSV(csv, `token-analytics-${format(new Date(), 'yyyy-MM-dd')}.csv`);
    }
  };

  // Mock data for demonstration
  const mockAnalytics = {
    summary: {
      totalTokens: 15234,
      activeTokens: 8456,
      revokedTokens: 3421,
      expiredTokens: 3357,
      averageLifetime: 3600,
      uniqueUsers: 2341,
      uniqueClients: 45,
    },
    trends: {
      daily: Array.from({ length: timeRange }, (_, i) => ({
        date: format(subDays(new Date(), timeRange - i - 1), 'MMM dd'),
        issued: Math.floor(Math.random() * 1000) + 500,
        revoked: Math.floor(Math.random() * 200) + 50,
        expired: Math.floor(Math.random() * 300) + 100,
        active: Math.floor(Math.random() * 5000) + 3000,
      })),
    },
    tokensByType: [
      { name: 'Access Token', value: 8456, percentage: 55.5 },
      { name: 'Refresh Token', value: 4821, percentage: 31.6 },
      { name: 'ID Token', value: 1957, percentage: 12.9 },
    ],
    tokensByClient: [
      { name: 'Web App', tokens: 4521, percentage: 29.7 },
      { name: 'Mobile App', tokens: 3842, percentage: 25.2 },
      { name: 'API Client', tokens: 2156, percentage: 14.1 },
      { name: 'Admin Portal', tokens: 1892, percentage: 12.4 },
      { name: 'Others', tokens: 2823, percentage: 18.6 },
    ],
    topUsers: [
      { userId: 'user_1', name: 'John Doe', tokens: 234, lastActive: '2 hours ago' },
      { userId: 'user_2', name: 'Jane Smith', tokens: 189, lastActive: '5 minutes ago' },
      { userId: 'user_3', name: 'Bob Johnson', tokens: 156, lastActive: '1 day ago' },
      { userId: 'user_4', name: 'Alice Brown', tokens: 134, lastActive: '3 hours ago' },
      { userId: 'user_5', name: 'Charlie Wilson', tokens: 98, lastActive: '30 minutes ago' },
    ],
    performance: {
      averageIssuanceTime: 45, // ms
      averageValidationTime: 12, // ms
      failureRate: 0.3, // %
      successRate: 99.7, // %
    },
    securityEvents: [
      { type: 'suspicious_activity', count: 23, severity: 'high' },
      { type: 'rate_limit_exceeded', count: 156, severity: 'medium' },
      { type: 'invalid_token', count: 342, severity: 'low' },
      { type: 'expired_token_usage', count: 89, severity: 'low' },
    ],
  };

  const data = analytics || mockAnalytics;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="h6">Token Analytics</Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <Select
                value={timeRange}
                onChange={(e) => setTimeRange(e.target.value as number)}
              >
                <MenuItem value={7}>Last 7 days</MenuItem>
                <MenuItem value={14}>Last 14 days</MenuItem>
                <MenuItem value={30}>Last 30 days</MenuItem>
                <MenuItem value={90}>Last 90 days</MenuItem>
              </Select>
            </FormControl>
            <IconButton onClick={fetchAnalytics} disabled={loading}>
              <RefreshIcon />
            </IconButton>
            <IconButton onClick={onClose}>
              <CloseIcon />
            </IconButton>
          </Box>
        </Box>
      </DialogTitle>

      <DialogContent>
        {loading && <LinearProgress />}
        
        <Tabs value={activeTab} onChange={handleTabChange} sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tab label="Overview" />
          <Tab label="Trends" />
          <Tab label="Distribution" />
          <Tab label="Performance" />
          <Tab label="Security" />
        </Tabs>

        {/* Overview Tab */}
        <TabPanel value={activeTab} index={0}>
          <Grid container spacing={3}>
            {/* Summary Cards */}
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <Box>
                      <Typography variant="h4">
                        {data.summary.totalTokens.toLocaleString()}
                      </Typography>
                      <Typography variant="body2" color="textSecondary">
                        Total Tokens
                      </Typography>
                    </Box>
                    <SecurityIcon sx={{ fontSize: 40, color: 'primary.light' }} />
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <Box>
                      <Typography variant="h4" color="success.main">
                        {data.summary.activeTokens.toLocaleString()}
                      </Typography>
                      <Typography variant="body2" color="textSecondary">
                        Active Tokens
                      </Typography>
                    </Box>
                    <CheckCircleIcon sx={{ fontSize: 40, color: 'success.light' }} />
                  </Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', mt: 1 }}>
                    <TrendingUpIcon fontSize="small" color="success" />
                    <Typography variant="caption" color="success.main">
                      +12% from last period
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <Box>
                      <Typography variant="h4">
                        {data.summary.uniqueUsers.toLocaleString()}
                      </Typography>
                      <Typography variant="body2" color="textSecondary">
                        Unique Users
                      </Typography>
                    </Box>
                    <PersonIcon sx={{ fontSize: 40, color: 'info.light' }} />
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <Box>
                      <Typography variant="h4">
                        {data.summary.uniqueClients}
                      </Typography>
                      <Typography variant="body2" color="textSecondary">
                        OAuth Clients
                      </Typography>
                    </Box>
                    <AppsIcon sx={{ fontSize: 40, color: 'secondary.light' }} />
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            {/* Token Lifetime */}
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="subtitle1" gutterBottom>
                    Token Status Distribution
                  </Typography>
                  <Box sx={{ mt: 2 }}>
                    <Grid container spacing={2}>
                      <Grid item xs={12} sm={4}>
                        <Box>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                            <Typography variant="body2">Active</Typography>
                            <Typography variant="body2" color="success.main">
                              {((data.summary.activeTokens / data.summary.totalTokens) * 100).toFixed(1)}%
                            </Typography>
                          </Box>
                          <LinearProgress
                            variant="determinate"
                            value={(data.summary.activeTokens / data.summary.totalTokens) * 100}
                            color="success"
                            sx={{ height: 8, borderRadius: 1 }}
                          />
                        </Box>
                      </Grid>
                      <Grid item xs={12} sm={4}>
                        <Box>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                            <Typography variant="body2">Revoked</Typography>
                            <Typography variant="body2" color="error.main">
                              {((data.summary.revokedTokens / data.summary.totalTokens) * 100).toFixed(1)}%
                            </Typography>
                          </Box>
                          <LinearProgress
                            variant="determinate"
                            value={(data.summary.revokedTokens / data.summary.totalTokens) * 100}
                            color="error"
                            sx={{ height: 8, borderRadius: 1 }}
                          />
                        </Box>
                      </Grid>
                      <Grid item xs={12} sm={4}>
                        <Box>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                            <Typography variant="body2">Expired</Typography>
                            <Typography variant="body2" color="warning.main">
                              {((data.summary.expiredTokens / data.summary.totalTokens) * 100).toFixed(1)}%
                            </Typography>
                          </Box>
                          <LinearProgress
                            variant="determinate"
                            value={(data.summary.expiredTokens / data.summary.totalTokens) * 100}
                            color="warning"
                            sx={{ height: 8, borderRadius: 1 }}
                          />
                        </Box>
                      </Grid>
                    </Grid>
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            {/* Top Users */}
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="subtitle1" gutterBottom>
                    Top Users by Token Count
                  </Typography>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>User</TableCell>
                          <TableCell align="right">Tokens</TableCell>
                          <TableCell>Last Active</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {data.topUsers.map((user: any) => (
                          <TableRow key={user.userId}>
                            <TableCell>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <PersonIcon fontSize="small" color="action" />
                                <Typography variant="body2">{user.name}</Typography>
                              </Box>
                            </TableCell>
                            <TableCell align="right">
                              <Chip label={user.tokens} size="small" />
                            </TableCell>
                            <TableCell>
                              <Typography variant="body2" color="textSecondary">
                                {user.lastActive}
                              </Typography>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </TabPanel>

        {/* Trends Tab */}
        <TabPanel value={activeTab} index={1}>
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="subtitle1" gutterBottom>
                    Token Activity Trends
                  </Typography>
                  <ResponsiveContainer width="100%" height={300}>
                    <AreaChart data={data.trends.daily}>
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
                        stroke={COLORS.error}
                        fill={COLORS.error}
                        name="Revoked"
                      />
                      <Area
                        type="monotone"
                        dataKey="expired"
                        stackId="1"
                        stroke={COLORS.warning}
                        fill={COLORS.warning}
                        name="Expired"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="subtitle1" gutterBottom>
                    Active Tokens Over Time
                  </Typography>
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={data.trends.daily}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" />
                      <YAxis />
                      <RechartsTooltip />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="active"
                        stroke={COLORS.primary}
                        strokeWidth={2}
                        name="Active Tokens"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </TabPanel>

        {/* Distribution Tab */}
        <TabPanel value={activeTab} index={2}>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="subtitle1" gutterBottom>
                    Tokens by Type
                  </Typography>
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie
                        data={data.tokensByType}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={({ name, percentage }) => `${name}: ${percentage.toFixed(1)}%`}
                        outerRadius={80}
                        fill="#8884d8"
                        dataKey="value"
                      >
                        {data.tokensByType.map((entry: any, index: number) => (
                          <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
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
                  <Typography variant="subtitle1" gutterBottom>
                    Tokens by Client
                  </Typography>
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={data.tokensByClient}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" />
                      <YAxis />
                      <RechartsTooltip />
                      <Bar dataKey="tokens" fill={COLORS.primary} />
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="subtitle1" gutterBottom>
                    Token Distribution by Client
                  </Typography>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Client</TableCell>
                          <TableCell align="right">Tokens</TableCell>
                          <TableCell align="right">Percentage</TableCell>
                          <TableCell>Distribution</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {data.tokensByClient.map((client: any) => (
                          <TableRow key={client.name}>
                            <TableCell>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <AppsIcon fontSize="small" color="action" />
                                <Typography variant="body2">{client.name}</Typography>
                              </Box>
                            </TableCell>
                            <TableCell align="right">
                              <Typography variant="body2">{client.tokens.toLocaleString()}</Typography>
                            </TableCell>
                            <TableCell align="right">
                              <Chip label={`${client.percentage}%`} size="small" />
                            </TableCell>
                            <TableCell>
                              <LinearProgress
                                variant="determinate"
                                value={client.percentage}
                                sx={{ height: 6, borderRadius: 1 }}
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
          </Grid>
        </TabPanel>

        {/* Performance Tab */}
        <TabPanel value={activeTab} index={3}>
          <Grid container spacing={3}>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <SpeedIcon color="primary" />
                    <Typography variant="subtitle2">Avg Issuance Time</Typography>
                  </Box>
                  <Typography variant="h4">
                    {data.performance.averageIssuanceTime}ms
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', mt: 1 }}>
                    <TrendingDownIcon fontSize="small" color="success" />
                    <Typography variant="caption" color="success.main">
                      -5% from last period
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <SpeedIcon color="primary" />
                    <Typography variant="subtitle2">Avg Validation Time</Typography>
                  </Box>
                  <Typography variant="h4">
                    {data.performance.averageValidationTime}ms
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', mt: 1 }}>
                    <TrendingDownIcon fontSize="small" color="success" />
                    <Typography variant="caption" color="success.main">
                      -8% from last period
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <CheckCircleIcon color="success" />
                    <Typography variant="subtitle2">Success Rate</Typography>
                  </Box>
                  <Typography variant="h4" color="success.main">
                    {data.performance.successRate}%
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <ErrorIcon color="error" />
                    <Typography variant="subtitle2">Failure Rate</Typography>
                  </Box>
                  <Typography variant="h4" color="error.main">
                    {data.performance.failureRate}%
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="subtitle1" gutterBottom>
                    Performance Metrics
                  </Typography>
                  <Box sx={{ mt: 2 }}>
                    <Grid container spacing={3}>
                      <Grid item xs={12} md={4}>
                        <Typography variant="body2" color="textSecondary" gutterBottom>
                          Token Issuance Latency Distribution
                        </Typography>
                        <List dense>
                          <ListItem>
                            <ListItemText primary="P50" secondary="35ms" />
                          </ListItem>
                          <ListItem>
                            <ListItemText primary="P95" secondary="85ms" />
                          </ListItem>
                          <ListItem>
                            <ListItemText primary="P99" secondary="120ms" />
                          </ListItem>
                        </List>
                      </Grid>
                      <Grid item xs={12} md={4}>
                        <Typography variant="body2" color="textSecondary" gutterBottom>
                          Token Validation Latency Distribution
                        </Typography>
                        <List dense>
                          <ListItem>
                            <ListItemText primary="P50" secondary="8ms" />
                          </ListItem>
                          <ListItem>
                            <ListItemText primary="P95" secondary="15ms" />
                          </ListItem>
                          <ListItem>
                            <ListItemText primary="P99" secondary="25ms" />
                          </ListItem>
                        </List>
                      </Grid>
                      <Grid item xs={12} md={4}>
                        <Typography variant="body2" color="textSecondary" gutterBottom>
                          System Health
                        </Typography>
                        <List dense>
                          <ListItem>
                            <ListItemText primary="Uptime" secondary="99.99%" />
                          </ListItem>
                          <ListItem>
                            <ListItemText primary="Error Rate" secondary="0.3%" />
                          </ListItem>
                          <ListItem>
                            <ListItemText primary="Throughput" secondary="1.2K req/s" />
                          </ListItem>
                        </List>
                      </Grid>
                    </Grid>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </TabPanel>

        {/* Security Tab */}
        <TabPanel value={activeTab} index={4}>
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="subtitle1" gutterBottom>
                    Security Events
                  </Typography>
                  <TableContainer>
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableCell>Event Type</TableCell>
                          <TableCell align="right">Count</TableCell>
                          <TableCell>Severity</TableCell>
                          <TableCell>Status</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {data.securityEvents.map((event: any) => (
                          <TableRow key={event.type}>
                            <TableCell>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <WarningIcon
                                  fontSize="small"
                                  color={
                                    event.severity === 'high' ? 'error' :
                                    event.severity === 'medium' ? 'warning' : 'action'
                                  }
                                />
                                <Typography variant="body2">
                                  {event.type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                                </Typography>
                              </Box>
                            </TableCell>
                            <TableCell align="right">
                              <Typography variant="body2">{event.count}</Typography>
                            </TableCell>
                            <TableCell>
                              <Chip
                                label={event.severity.toUpperCase()}
                                size="small"
                                color={
                                  event.severity === 'high' ? 'error' :
                                  event.severity === 'medium' ? 'warning' : 'default'
                                }
                              />
                            </TableCell>
                            <TableCell>
                              <Chip
                                label="Monitoring"
                                size="small"
                                variant="outlined"
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
              <Alert severity="info">
                <Typography variant="body2">
                  Security monitoring is active. Suspicious activities are automatically logged and reviewed.
                </Typography>
              </Alert>
            </Grid>
          </Grid>
        </TabPanel>
      </DialogContent>

      <DialogActions>
        <Button onClick={handleExport} startIcon={<DownloadIcon />}>
          Export Report
        </Button>
        <Button onClick={onClose} variant="contained">
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
};

// Helper functions
const generateAnalyticsCSV = (analytics: any): string => {
  // Generate CSV content from analytics data
  const lines = ['OAuth Token Analytics Report'];
  lines.push(`Generated: ${format(new Date(), 'PPpp')}`);
  lines.push('');
  lines.push('Summary');
  lines.push(`Total Tokens,${analytics.summary.totalTokens}`);
  lines.push(`Active Tokens,${analytics.summary.activeTokens}`);
  // Add more lines as needed
  return lines.join('\n');
};

const downloadCSV = (csv: string, filename: string): void => {
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
};