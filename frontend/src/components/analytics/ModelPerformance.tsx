import {
  Box,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  LinearProgress,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Avatar,
  FormControl,
  InputLabel,
  Select,
  MenuItem } from '@mui/material';
import {
  TrendingUp,
  AttachMoney,
  People,
  Favorite,
  Message } from '@mui/icons-material';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer } from 'recharts';
import { useQuery } from '@tanstack/react-query';
import { format } from 'date-fns';
import { useState } from 'react';

interface ModelPerformanceProps {
  dateRange: {
    start: Date;
    end: Date;
  };
  refreshKey: number;
}

export const ModelPerformance = ({ dateRange, refreshKey }: ModelPerformanceProps) => {
  const [selectedModel, setSelectedModel] = useState('all');

  const { data: performanceData, isPending } = useQuery({
    queryKey: ['model-performance', dateRange, refreshKey, selectedModel],
    queryFn: async () => {
      // Simulated API call
      return {
        summary: {
          totalEarnings: 45000,
          earningsChange: 18.5,
          totalSubscribers: 850,
          newSubscribers: 125,
          totalMessages: 12500,
          avgResponseTime: 3.2,
          contentPieces: 156,
          fanEngagement: 78.5 },
        earningsChart: Array.from({ length: 30 }, (_, i) => ({
          date: format(new Date(2024, 0, i + 1), 'MMM d'),
          earnings: Math.floor(Math.random() * 2000) + 1000,
          tips: Math.floor(Math.random() * 500) + 200,
          subscriptions: Math.floor(Math.random() * 800) + 600 })),
        subscriberGrowth: Array.from({ length: 30 }, (_, i) => ({
          date: format(new Date(2024, 0, i + 1), 'MMM d'),
          total: 600 + i * 8 + Math.floor(Math.random() * 20),
          new: Math.floor(Math.random() * 10) + 2,
          lost: Math.floor(Math.random() * 3) })),
        topFans: [
          { name: 'JohnDoe123', spent: 2500, messages: 450, joinDate: '2023-06-15', tier: 'VIP' },
          { name: 'MikeSmith', spent: 1800, messages: 320, joinDate: '2023-08-20', tier: 'Premium' },
          { name: 'AlexJones', spent: 1500, messages: 280, joinDate: '2023-09-10', tier: 'Premium' },
          { name: 'ChrisLee', spent: 1200, messages: 210, joinDate: '2023-10-05', tier: 'Standard' },
          { name: 'DavidBrown', spent: 950, messages: 180, joinDate: '2023-11-12', tier: 'Standard' },
        ],
        contentPerformance: [
          { type: 'Photos', count: 85, revenue: 15000 },
          { type: 'Videos', count: 45, revenue: 18000 },
          { type: 'Live', count: 12, revenue: 8000 },
          { type: 'PPV', count: 14, revenue: 4000 },
        ],
        engagementMetrics: [
          { hour: '12 AM', messages: 15, views: 120 },
          { hour: '4 AM', messages: 8, views: 45 },
          { hour: '8 AM', messages: 25, views: 180 },
          { hour: '12 PM', messages: 45, views: 320 },
          { hour: '4 PM', messages: 38, views: 280 },
          { hour: '8 PM', messages: 65, views: 450 },
          { hour: '11 PM', messages: 42, views: 310 },
        ],
        goals: [
          { name: 'Monthly Revenue', target: 50000, current: 45000, percentage: 90 },
          { name: 'New Subscribers', target: 150, current: 125, percentage: 83 },
          { name: 'Content Posts', target: 200, current: 156, percentage: 78 },
          { name: 'Fan Engagement', target: 85, current: 78.5, percentage: 92 },
        ] };
    } });

  const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042'];

  if (isPending) {
    return <LinearProgress />;
  }

  return (
    <Box>
      {/* Model Selector */}
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'flex-end' }}>
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>Select Model</InputLabel>
          <Select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            label="Select Model"
          >
            <MenuItem value="all">All Models</MenuItem>
            <MenuItem value="model1">Emma Johnson</MenuItem>
            <MenuItem value="model2">Sophia Williams</MenuItem>
            <MenuItem value="model3">Isabella Brown</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {/* Summary Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography color="text.secondary" gutterBottom>
                    Total Earnings
                  </Typography>
                  <Typography variant="h4">
                    ${performanceData?.summary.totalEarnings.toLocaleString()}
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', mt: 1 }}>
                    <TrendingUp color="success" fontSize="small" />
                    <Typography variant="body2" color="success.main" sx={{ ml: 0.5 }}>
                      {performanceData?.summary.earningsChange}%
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
                    Subscribers
                  </Typography>
                  <Typography variant="h4">
                    {performanceData?.summary.totalSubscribers}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    +{performanceData?.summary.newSubscribers} new
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
                    Messages
                  </Typography>
                  <Typography variant="h4">
                    {performanceData?.summary.totalMessages.toLocaleString()}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {performanceData?.summary.avgResponseTime}m avg
                  </Typography>
                </Box>
                <Message color="primary" sx={{ fontSize: 40, opacity: 0.3 }} />
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
                    Engagement
                  </Typography>
                  <Typography variant="h4">
                    {performanceData?.summary.fanEngagement}%
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {performanceData?.summary.contentPieces} posts
                  </Typography>
                </Box>
                <Favorite color="primary" sx={{ fontSize: 40, opacity: 0.3 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        {/* Earnings Breakdown */}
        <Grid item xs={12} lg={8}>
          <Paper sx={{ p: 3, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              Earnings Breakdown
            </Typography>
            <ResponsiveContainer width="100%" height="90%">
              <AreaChart data={performanceData?.earningsChart}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip formatter={(value) => `$${value}`} />
                <Legend />
                <Area
                  type="monotone"
                  dataKey="subscriptions"
                  stackId="1"
                  stroke="#8884d8"
                  fill="#8884d8"
                  name="Subscriptions"
                />
                <Area
                  type="monotone"
                  dataKey="tips"
                  stackId="1"
                  stroke="#82ca9d"
                  fill="#82ca9d"
                  name="Tips"
                />
                <Area
                  type="monotone"
                  dataKey="earnings"
                  stackId="1"
                  stroke="#ffc658"
                  fill="#ffc658"
                  name="Other"
                />
              </AreaChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Content Performance */}
        <Grid item xs={12} lg={4}>
          <Paper sx={{ p: 3, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              Content Performance
            </Typography>
            <ResponsiveContainer width="100%" height="90%">
              <PieChart>
                <Pie
                  data={performanceData?.contentPerformance}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ type, revenue }) => `${type}: $${revenue}`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="revenue"
                >
                  {performanceData?.contentPerformance.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => `$${value}`} />
              </PieChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Subscriber Growth */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              Subscriber Growth
            </Typography>
            <ResponsiveContainer width="100%" height="90%">
              <LineChart data={performanceData?.subscriberGrowth}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="total"
                  stroke="#8884d8"
                  name="Total Subscribers"
                />
                <Line
                  type="monotone"
                  dataKey="new"
                  stroke="#82ca9d"
                  name="New Subscribers"
                />
                <Line
                  type="monotone"
                  dataKey="lost"
                  stroke="#ff7c7c"
                  name="Lost Subscribers"
                />
              </LineChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Top Fans */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Top Fans
            </Typography>
            <List>
              {performanceData?.topFans.map((fan, index) => (
                <ListItem key={fan.name} divider={index < performanceData.topFans.length - 1}>
                  <ListItemAvatar>
                    <Avatar>{fan.name[0]}</Avatar>
                  </ListItemAvatar>
                  <ListItemText
                    primary={fan.name}
                    secondary={`$${fan.spent.toLocaleString()} spent • ${fan.messages} messages`}
                    secondaryTypographyProps={{ component: 'div' }}
                  />
                  <Chip 
                    label={fan.tier} 
                    size="small" 
                    color={fan.tier === 'VIP' ? 'primary' : 'default'}
                  />
                </ListItem>
              ))}
            </List>
          </Paper>
        </Grid>

        {/* Goals Progress */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Monthly Goals
            </Typography>
            <List>
              {performanceData?.goals.map((goal) => (
                <ListItem key={goal.name}>
                  <ListItemText
                    primary={goal.name}
                    secondary={
                      <Box component="span" sx={{ mt: 1, display: 'block' }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                          <Typography variant="body2" component="span">
                            {goal.name.toLowerCase().includes('revenue') ? '$' : ''}{goal.current.toLocaleString()} / {goal.name.toLowerCase().includes('revenue') ? '$' : ''}{goal.target.toLocaleString()}
                          </Typography>
                          <Typography variant="body2" color="text.secondary" component="span">
                            {goal.percentage}%
                          </Typography>
                        </Box>
                        <LinearProgress 
                          variant="determinate" 
                          value={goal.percentage} 
                          color={goal.percentage >= 80 ? 'success' : 'primary'}
                          sx={{ mt: 1 }}
                        />
                      </Box>
                    }
                    secondaryTypographyProps={{ component: 'div' }}
                  />
                </ListItem>
              ))}
            </List>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};
