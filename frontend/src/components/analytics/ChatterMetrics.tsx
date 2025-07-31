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
  Avatar } from '@mui/material';
import {
  Speed,
  Message,
  Timer,
  ThumbUp } from '@mui/icons-material';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
  Cell,
  PieChart,
  Pie } from 'recharts';
import { useQuery } from '@tanstack/react-query';
import { format } from 'date-fns';

interface ChatterMetricsProps {
  dateRange: {
    start: Date;
    end: Date;
  };
  refreshKey: number;
}

export const ChatterMetrics = ({ dateRange, refreshKey }: ChatterMetricsProps) => {
  const { data: metricsData, isPending } = useQuery({
    queryKey: ['chatter-metrics', dateRange, refreshKey],
    queryFn: async () => {
      // Simulated API call
      return {
        summary: {
          totalMessages: 8500,
          avgResponseTime: 2.8,
          satisfactionRate: 92,
          conversationRate: 68,
          activeHours: 145,
          messagesPerHour: 58.6 },
        performance: [
          { 
            name: 'Sarah Johnson',
            avatar: '/avatar1.jpg',
            messages: 1850,
            responseTime: 2.1,
            satisfaction: 95,
            conversions: 125,
            revenue: 12500,
            status: 'online'
          },
          { 
            name: 'Mike Chen',
            avatar: '/avatar2.jpg',
            messages: 1620,
            responseTime: 2.5,
            satisfaction: 93,
            conversions: 108,
            revenue: 10800,
            status: 'online'
          },
          { 
            name: 'Lisa White',
            avatar: '/avatar3.jpg',
            messages: 1480,
            responseTime: 3.2,
            satisfaction: 91,
            conversions: 95,
            revenue: 9500,
            status: 'away'
          },
          { 
            name: 'Tom Davis',
            avatar: '/avatar4.jpg',
            messages: 1350,
            responseTime: 2.8,
            satisfaction: 89,
            conversions: 87,
            revenue: 8700,
            status: 'offline'
          },
          { 
            name: 'Emma Brown',
            avatar: '/avatar5.jpg',
            messages: 1200,
            responseTime: 3.5,
            satisfaction: 88,
            conversions: 72,
            revenue: 7200,
            status: 'online'
          },
        ],
        activityChart: Array.from({ length: 24 }, (_, i) => ({
          hour: `${i}:00`,
          messages: Math.floor(Math.random() * 100) + 20,
          responseTime: Math.random() * 2 + 1.5 })),
        responseTimeDistribution: [
          { range: '<1 min', count: 2500, percentage: 29 },
          { range: '1-3 min', count: 3500, percentage: 41 },
          { range: '3-5 min', count: 1800, percentage: 21 },
          { range: '5-10 min', count: 600, percentage: 7 },
          { range: '>10 min', count: 100, percentage: 2 },
        ],
        conversationTypes: [
          { type: 'General Chat', value: 3500, percentage: 41 },
          { type: 'Sales', value: 2800, percentage: 33 },
          { type: 'Support', value: 1200, percentage: 14 },
          { type: 'Tips/PPV', value: 1000, percentage: 12 },
        ],
        weeklyTrend: Array.from({ length: 7 }, (_, i) => ({
          day: format(new Date(2024, 0, i + 1), 'EEE'),
          messages: Math.floor(Math.random() * 1500) + 1000,
          conversions: Math.floor(Math.random() * 30) + 15,
          revenue: Math.floor(Math.random() * 3000) + 2000 })) };
    } });

  const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

  if (isPending) {
    return <LinearProgress />;
  }

  return (
    <Box>
      {/* Summary Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography color="text.secondary" gutterBottom>
                    Total Messages
                  </Typography>
                  <Typography variant="h4">
                    {metricsData?.summary.totalMessages.toLocaleString()}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {metricsData?.summary.messagesPerHour.toFixed(1)}/hour
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
                    Avg Response
                  </Typography>
                  <Typography variant="h4">
                    {metricsData?.summary.avgResponseTime}m
                  </Typography>
                  <Typography variant="body2" color="success.main">
                    Within target
                  </Typography>
                </Box>
                <Timer color="primary" sx={{ fontSize: 40, opacity: 0.3 }} />
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
                    Satisfaction
                  </Typography>
                  <Typography variant="h4">
                    {metricsData?.summary.satisfactionRate}%
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    User rating
                  </Typography>
                </Box>
                <ThumbUp color="primary" sx={{ fontSize: 40, opacity: 0.3 }} />
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
                    Conversion Rate
                  </Typography>
                  <Typography variant="h4">
                    {metricsData?.summary.conversationRate}%
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {metricsData?.summary.activeHours}h active
                  </Typography>
                </Box>
                <Speed color="primary" sx={{ fontSize: 40, opacity: 0.3 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        {/* Activity Heatmap */}
        <Grid item xs={12} lg={8}>
          <Paper sx={{ p: 3, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              24-Hour Activity Pattern
            </Typography>
            <ResponsiveContainer width="100%" height="90%">
              <BarChart data={metricsData?.activityChart}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="hour" />
                <YAxis yAxisId="left" />
                <YAxis yAxisId="right" orientation="right" />
                <RechartsTooltip />
                <Legend />
                <Bar yAxisId="left" dataKey="messages" fill="#8884d8" name="Messages" />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="responseTime"
                  stroke="#ff7300"
                  name="Response Time (min)"
                />
              </BarChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Response Time Distribution */}
        <Grid item xs={12} lg={4}>
          <Paper sx={{ p: 3, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              Response Time Distribution
            </Typography>
            <ResponsiveContainer width="100%" height="90%">
              <PieChart>
                <Pie
                  data={metricsData?.responseTimeDistribution}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ percentage }) => `${percentage}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="count"
                >
                  {metricsData?.responseTimeDistribution.map((index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <RechartsTooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Chatter Performance Table */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Chatter Performance
            </Typography>
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Chatter</TableCell>
                    <TableCell align="right">Messages</TableCell>
                    <TableCell align="right">Avg Response</TableCell>
                    <TableCell align="right">Satisfaction</TableCell>
                    <TableCell align="right">Conversions</TableCell>
                    <TableCell align="right">Revenue</TableCell>
                    <TableCell align="center">Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {metricsData?.performance.map((chatter) => (
                    <TableRow key={chatter.name}>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                          <Avatar src={chatter.avatar}>{chatter.name[0]}</Avatar>
                          {chatter.name}
                        </Box>
                      </TableCell>
                      <TableCell align="right">{chatter.messages.toLocaleString()}</TableCell>
                      <TableCell align="right">{chatter.responseTime}m</TableCell>
                      <TableCell align="right">
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 0.5 }}>
                          {chatter.satisfaction}%
                          <ThumbUp fontSize="small" color="success" />
                        </Box>
                      </TableCell>
                      <TableCell align="right">{chatter.conversions}</TableCell>
                      <TableCell align="right">${chatter.revenue.toLocaleString()}</TableCell>
                      <TableCell align="center">
                        <Chip
                          label={chatter.status}
                          size="small"
                          color={
                            chatter.status === 'online' ? 'success' :
                            chatter.status === 'away' ? 'warning' : 'default'
                          }
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Grid>

        {/* Weekly Performance Trend */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              Weekly Performance Trend
            </Typography>
            <ResponsiveContainer width="100%" height="90%">
              <LineChart data={metricsData?.weeklyTrend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="day" />
                <YAxis yAxisId="left" />
                <YAxis yAxisId="right" orientation="right" />
                <RechartsTooltip />
                <Legend />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="messages"
                  stroke="#8884d8"
                  name="Messages"
                />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="conversions"
                  stroke="#82ca9d"
                  name="Conversions"
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="revenue"
                  stroke="#ffc658"
                  name="Revenue ($)"
                />
              </LineChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Conversation Types */}
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              Conversation Types
            </Typography>
            <Box sx={{ mt: 3 }}>
              {metricsData?.conversationTypes.map((type, index) => (
                <Box key={type.type} sx={{ mb: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="body2">{type.type}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {type.percentage}%
                    </Typography>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={type.percentage}
                    sx={{
                      height: 10,
                      borderRadius: 5,
                      backgroundColor: 'grey.200',
                      '& .MuiLinearProgress-bar': {
                        backgroundColor: COLORS[index % COLORS.length] } }}
                  />
                </Box>
              ))}
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};
