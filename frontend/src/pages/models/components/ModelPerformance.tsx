import { useState } from 'react';
import {
  Box,
  Grid,
  Typography,
  ToggleButton,
  ToggleButtonGroup,
  Paper,
  Skeleton,
} from '@mui/material';
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
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { useModelStats } from '@/hooks/useModels';

interface ModelPerformanceProps {
  modelId: string;
}

export const ModelPerformance = ({ modelId }: ModelPerformanceProps) => {
  const [period, setPeriod] = useState<'day' | 'week' | 'month'>('month');
  const { data: stats, isPending } = useModelStats(modelId, period);

  const handlePeriodChange = (_: React.MouseEvent<HTMLElement>, newPeriod: 'day' | 'week' | 'month' | null) => {
    if (newPeriod !== null) {
      setPeriod(newPeriod);
    }
  };

  // Mock data for charts - replace with real data from API
  const revenueData = [
    { name: 'Mon', revenue: 450, tips: 120 },
    { name: 'Tue', revenue: 520, tips: 180 },
    { name: 'Wed', revenue: 480, tips: 150 },
    { name: 'Thu', revenue: 610, tips: 220 },
    { name: 'Fri', revenue: 750, tips: 300 },
    { name: 'Sat', revenue: 820, tips: 350 },
    { name: 'Sun', revenue: 690, tips: 280 },
  ];

  const fanData = [
    { name: 'Week 1', gained: 25, lost: 5 },
    { name: 'Week 2', gained: 32, lost: 8 },
    { name: 'Week 3', gained: 28, lost: 6 },
    { name: 'Week 4', gained: 35, lost: 7 },
  ];

  const contentPerformance = [
    { name: 'Photos', value: 45, color: '#8884d8' },
    { name: 'Videos', value: 30, color: '#82ca9d' },
    { name: 'Messages', value: 20, color: '#ffc658' },
    { name: 'Tips', value: 5, color: '#ff7c7c' },
  ];

  if (isPending) {
    return (
      <Box sx={{ p: 3 }}>
        <Grid container spacing={3}>
          {[1, 2, 3].map((i) => (
            <Grid item xs={12} key={i}>
              <Skeleton variant="rectangular" height={300} />
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h6">Performance Analytics</Typography>
        <ToggleButtonGroup
          value={period}
          exclusive
          onChange={handlePeriodChange}
          size="small"
        >
          <ToggleButton value="day">Day</ToggleButton>
          <ToggleButton value="week">Week</ToggleButton>
          <ToggleButton value="month">Month</ToggleButton>
        </ToggleButtonGroup>
      </Box>

      <Grid container spacing={3}>
        {/* Revenue Chart */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" gutterBottom>
              Revenue & Tips
            </Typography>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={revenueData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="revenue"
                  stroke="#8884d8"
                  name="Revenue"
                  strokeWidth={2}
                />
                <Line
                  type="monotone"
                  dataKey="tips"
                  stroke="#82ca9d"
                  name="Tips"
                  strokeWidth={2}
                />
              </LineChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Content Performance Pie Chart */}
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" gutterBottom>
              Revenue by Content Type
            </Typography>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={contentPerformance}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, value }) => `${name}: ${value}%`}
                  outerRadius={100}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {contentPerformance.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Fan Growth Chart */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" gutterBottom>
              Fan Growth & Churn
            </Typography>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={fanData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="gained" fill="#82ca9d" name="New Fans" />
                <Bar dataKey="lost" fill="#ff7c7c" name="Lost Fans" />
              </BarChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Key Metrics */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" gutterBottom sx={{ mb: 2 }}>
              Key Metrics
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={6} sm={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h4" color="primary">
                    {stats?.avg_response_time ? `${stats.avg_response_time} min` : 'N/A'}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Avg Response Time
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h4" color="primary">
                    {stats?.total_messages || 0}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Messages Sent
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h4" color="primary">
                    ${stats?.total_tips || 0}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Total Tips
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h4" color="primary">
                    {stats?.conversion_rate?.toFixed(1) || 0}%
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Conversion Rate
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};
