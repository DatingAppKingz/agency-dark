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
  Avatar,
  AvatarGroup,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  People,
  AttachMoney,
  Star,
  Schedule,
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
  Legend,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from 'recharts';
import { useQuery } from '@tanstack/react-query';
import { format } from 'date-fns';

interface AgencyAnalyticsProps {
  dateRange: {
    start: Date;
    end: Date;
  };
  refreshKey: number;
}

export const AgencyAnalytics = ({ dateRange, refreshKey }: AgencyAnalyticsProps) => {
  const { data: analyticsData, isLoading } = useQuery({
    queryKey: ['agency-analytics', dateRange, refreshKey],
    queryFn: async () => {
      // Simulated API call
      return {
        summary: {
          totalRevenue: 85000,
          revenueChange: 15.3,
          totalModels: 42,
          activeModels: 38,
          totalChatters: 15,
          avgResponseTime: 2.5,
          commissionEarned: 25500,
          conversionRate: 68.5,
        },
        revenueChart: Array.from({ length: 30 }, (_, i) => ({
          date: format(new Date(2024, 0, i + 1), 'MMM d'),
          revenue: Math.floor(Math.random() * 3000) + 2000,
          commission: Math.floor(Math.random() * 900) + 600,
        })),
        modelPerformance: [
          { 
            name: 'Emma Johnson', 
            avatar: '/avatar1.jpg',
            revenue: 15000, 
            subscribers: 450, 
            messages: 3200, 
            rating: 4.8,
            status: 'online' 
          },
          { 
            name: 'Sophia Williams', 
            avatar: '/avatar2.jpg',
            revenue: 12500, 
            subscribers: 380, 
            messages: 2900, 
            rating: 4.9,
            status: 'online' 
          },
          { 
            name: 'Isabella Brown', 
            avatar: '/avatar3.jpg',
            revenue: 11000, 
            subscribers: 320, 
            messages: 2500, 
            rating: 4.7,
            status: 'offline' 
          },
          { 
            name: 'Olivia Davis', 
            avatar: '/avatar4.jpg',
            revenue: 9500, 
            subscribers: 290, 
            messages: 2100, 
            rating: 4.6,
            status: 'online' 
          },
          { 
            name: 'Ava Miller', 
            avatar: '/avatar5.jpg',
            revenue: 8700, 
            subscribers: 265, 
            messages: 1900, 
            rating: 4.8,
            status: 'offline' 
          },
        ],
        chatterPerformance: Array.from({ length: 7 }, (_, i) => ({
          day: format(new Date(2024, 0, i + 1), 'EEE'),
          messages: Math.floor(Math.random() * 500) + 300,
          responseTime: Math.random() * 2 + 1,
        })),
        performanceMetrics: [
          { metric: 'Response Rate', value: 85, benchmark: 80 },
          { metric: 'Conversion', value: 68, benchmark: 65 },
          { metric: 'Retention', value: 75, benchmark: 70 },
          { metric: 'Satisfaction', value: 92, benchmark: 85 },
          { metric: 'Growth', value: 78, benchmark: 75 },
          { metric: 'Efficiency', value: 82, benchmark: 80 },
        ],
      };
    },
  });

  if (isLoading) {
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
                    Agency Revenue
                  </Typography>
                  <Typography variant="h4">
                    ${analyticsData?.summary.totalRevenue.toLocaleString()}
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', mt: 1 }}>
                    <TrendingUp color="success" fontSize="small" />
                    <Typography variant="body2" color="success.main" sx={{ ml: 0.5 }}>
                      {analyticsData?.summary.revenueChange}%
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
                    Active Models
                  </Typography>
                  <Typography variant="h4">
                    {analyticsData?.summary.activeModels}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {analyticsData?.summary.totalModels} total
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
                    Commission
                  </Typography>
                  <Typography variant="h4">
                    ${analyticsData?.summary.commissionEarned.toLocaleString()}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    30% rate
                  </Typography>
                </Box>
                <Star color="primary" sx={{ fontSize: 40, opacity: 0.3 }} />
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
                    {analyticsData?.summary.avgResponseTime}m
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {analyticsData?.summary.totalChatters} chatters
                  </Typography>
                </Box>
                <Schedule color="primary" sx={{ fontSize: 40, opacity: 0.3 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        {/* Revenue & Commission Chart */}
        <Grid item xs={12} lg={8}>
          <Paper sx={{ p: 3, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              Revenue & Commission Trend
            </Typography>
            <ResponsiveContainer width="100%" height="90%">
              <AreaChart data={analyticsData?.revenueChart}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip formatter={(value) => `$${value}`} />
                <Legend />
                <Area
                  type="monotone"
                  dataKey="revenue"
                  stackId="1"
                  stroke="#8884d8"
                  fill="#8884d8"
                  fillOpacity={0.6}
                  name="Total Revenue"
                />
                <Area
                  type="monotone"
                  dataKey="commission"
                  stackId="1"
                  stroke="#82ca9d"
                  fill="#82ca9d"
                  fillOpacity={0.6}
                  name="Commission"
                />
              </AreaChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Performance Radar */}
        <Grid item xs={12} lg={4}>
          <Paper sx={{ p: 3, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              Performance Metrics
            </Typography>
            <ResponsiveContainer width="100%" height="90%">
              <RadarChart data={analyticsData?.performanceMetrics}>
                <PolarGrid />
                <PolarAngleAxis dataKey="metric" />
                <PolarRadiusAxis angle={90} domain={[0, 100]} />
                <Radar
                  name="Current"
                  dataKey="value"
                  stroke="#8884d8"
                  fill="#8884d8"
                  fillOpacity={0.6}
                />
                <Radar
                  name="Benchmark"
                  dataKey="benchmark"
                  stroke="#82ca9d"
                  fill="#82ca9d"
                  fillOpacity={0.3}
                />
                <Tooltip />
                <Legend />
              </RadarChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Top Models Table */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Top Performing Models
            </Typography>
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Model</TableCell>
                    <TableCell align="right">Revenue</TableCell>
                    <TableCell align="right">Subscribers</TableCell>
                    <TableCell align="right">Messages</TableCell>
                    <TableCell align="right">Rating</TableCell>
                    <TableCell align="center">Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {analyticsData?.modelPerformance.map((model) => (
                    <TableRow key={model.name}>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                          <Avatar src={model.avatar}>{model.name[0]}</Avatar>
                          {model.name}
                        </Box>
                      </TableCell>
                      <TableCell align="right">${model.revenue.toLocaleString()}</TableCell>
                      <TableCell align="right">{model.subscribers}</TableCell>
                      <TableCell align="right">{model.messages.toLocaleString()}</TableCell>
                      <TableCell align="right">
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 0.5 }}>
                          <Star fontSize="small" color="primary" />
                          {model.rating}
                        </Box>
                      </TableCell>
                      <TableCell align="center">
                        <Chip
                          label={model.status}
                          size="small"
                          color={model.status === 'online' ? 'success' : 'default'}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Grid>

        {/* Chatter Performance */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              Chatter Activity & Response Time
            </Typography>
            <ResponsiveContainer width="100%" height="90%">
              <BarChart data={analyticsData?.chatterPerformance}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="day" />
                <YAxis yAxisId="left" />
                <YAxis yAxisId="right" orientation="right" />
                <Tooltip />
                <Legend />
                <Bar yAxisId="left" dataKey="messages" fill="#8884d8" name="Messages Sent" />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="responseTime"
                  stroke="#ff7300"
                  name="Avg Response Time (min)"
                />
              </BarChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};