import { useEffect } from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  LinearProgress,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  People,
  AttachMoney,
  ChatBubble,
  Percent,
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
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { useQuery } from '@tanstack/react-query';
import { format } from 'date-fns';

interface PlatformAnalyticsProps {
  dateRange: {
    start: Date;
    end: Date;
  };
  refreshKey: number;
}

export const PlatformAnalytics = ({ dateRange, refreshKey }: PlatformAnalyticsProps) => {
  // Mock data - replace with actual API calls
  const { data: metricsData, isLoading } = useQuery({
    queryKey: ['platform-metrics', dateRange, refreshKey],
    queryFn: async () => {
      // Simulated API call
      return {
        revenue: {
          total: 125430,
          change: 12.5,
          chartData: Array.from({ length: 30 }, (_, i) => ({
            date: format(new Date(2024, 0, i + 1), 'MMM d'),
            revenue: Math.floor(Math.random() * 5000) + 3000,
          })),
        },
        users: {
          total: 3542,
          active: 2847,
          new: 156,
          change: 8.3,
          chartData: Array.from({ length: 30 }, (_, i) => ({
            date: format(new Date(2024, 0, i + 1), 'MMM d'),
            active: Math.floor(Math.random() * 200) + 2500,
            new: Math.floor(Math.random() * 20) + 5,
          })),
        },
        agencies: {
          total: 45,
          active: 42,
          revenue_share: 65000,
        },
        messages: {
          total: 45291,
          average_per_user: 12.8,
          change: -2.1,
        },
        topAgencies: [
          { name: 'Elite Models Agency', models: 25, revenue: 45000, growth: 15.2 },
          { name: 'Premier Talent', models: 18, revenue: 38000, growth: 8.7 },
          { name: 'Star Management', models: 22, revenue: 35000, growth: -2.1 },
          { name: 'Exclusive Agency', models: 15, revenue: 28000, growth: 22.5 },
          { name: 'Top Tier Models', models: 12, revenue: 24000, growth: 5.3 },
        ],
        revenueByType: [
          { name: 'Subscriptions', value: 65000, percentage: 52 },
          { name: 'Tips', value: 35000, percentage: 28 },
          { name: 'PPV', value: 15000, percentage: 12 },
          { name: 'Messages', value: 10430, percentage: 8 },
        ],
      };
    },
  });

  const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042'];

  if (isLoading) {
    return <LinearProgress />;
  }

  return (
    <Box>
      {/* Key Metrics */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography color="text.secondary" gutterBottom>
                    Total Revenue
                  </Typography>
                  <Typography variant="h4">
                    ${metricsData?.revenue.total.toLocaleString()}
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', mt: 1 }}>
                    {metricsData?.revenue.change > 0 ? (
                      <TrendingUp color="success" fontSize="small" />
                    ) : (
                      <TrendingDown color="error" fontSize="small" />
                    )}
                    <Typography
                      variant="body2"
                      color={metricsData?.revenue.change > 0 ? 'success.main' : 'error.main'}
                      sx={{ ml: 0.5 }}
                    >
                      {Math.abs(metricsData?.revenue.change)}%
                    </Typography>
                  </Box>
                </Box>
                <AttachMoney color="primary" sx={{ fontSize: 40, opacity: 0.3 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography color="text.secondary" gutterBottom>
                    Active Users
                  </Typography>
                  <Typography variant="h4">
                    {metricsData?.users.active.toLocaleString()}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {metricsData?.users.new} new this period
                  </Typography>
                </Box>
                <People color="primary" sx={{ fontSize: 40, opacity: 0.3 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography color="text.secondary" gutterBottom>
                    Total Messages
                  </Typography>
                  <Typography variant="h4">
                    {metricsData?.messages.total.toLocaleString()}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {metricsData?.messages.average_per_user} avg/user
                  </Typography>
                </Box>
                <ChatBubble color="primary" sx={{ fontSize: 40, opacity: 0.3 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography color="text.secondary" gutterBottom>
                    Active Agencies
                  </Typography>
                  <Typography variant="h4">
                    {metricsData?.agencies.active}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {metricsData?.agencies.total} total
                  </Typography>
                </Box>
                <Percent color="primary" sx={{ fontSize: 40, opacity: 0.3 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Charts */}
      <Grid container spacing={3}>
        {/* Revenue Trend */}
        <Grid item xs={12} lg={8}>
          <Paper sx={{ p: 3, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              Revenue Trend
            </Typography>
            <ResponsiveContainer width="100%" height="90%">
              <AreaChart data={metricsData?.revenue.chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip formatter={(value) => `$${value}`} />
                <Area
                  type="monotone"
                  dataKey="revenue"
                  stroke="#8884d8"
                  fill="#8884d8"
                  fillOpacity={0.6}
                />
              </AreaChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Revenue by Type */}
        <Grid item xs={12} lg={4}>
          <Paper sx={{ p: 3, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              Revenue by Type
            </Typography>
            <ResponsiveContainer width="100%" height="90%">
              <PieChart>
                <Pie
                  data={metricsData?.revenueByType}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ percentage }) => `${percentage}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {metricsData?.revenueByType.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => `$${value}`} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* User Activity */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              User Activity
            </Typography>
            <ResponsiveContainer width="100%" height="90%">
              <LineChart data={metricsData?.users.chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="active"
                  stroke="#8884d8"
                  name="Active Users"
                />
                <Line
                  type="monotone"
                  dataKey="new"
                  stroke="#82ca9d"
                  name="New Users"
                />
              </LineChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Top Agencies Table */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Top Performing Agencies
            </Typography>
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Agency Name</TableCell>
                    <TableCell align="right">Models</TableCell>
                    <TableCell align="right">Revenue</TableCell>
                    <TableCell align="right">Growth</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {metricsData?.topAgencies.map((agency) => (
                    <TableRow key={agency.name}>
                      <TableCell>{agency.name}</TableCell>
                      <TableCell align="right">{agency.models}</TableCell>
                      <TableCell align="right">${agency.revenue.toLocaleString()}</TableCell>
                      <TableCell align="right">
                        <Chip
                          label={`${agency.growth > 0 ? '+' : ''}${agency.growth}%`}
                          size="small"
                          color={agency.growth > 0 ? 'success' : 'error'}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};