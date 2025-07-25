import { Grid, Typography, Box, Paper } from '@mui/material';
import { 
  Business, 
  People, 
  AttachMoney, 
  TrendingUp,
  ShowChart,
  Groups,
  Paid,
} from '@mui/icons-material';
import { 
  StatsCard, 
  AnalyticsWidget, 
  MetricsGrid, 
  ChartWidget, 
  ActivityFeed 
} from '@/components/dashboard';
import { useDashboardStats, useAgencyStats } from '@/hooks/useAnalytics';
import { useMemo } from 'react';

export const SuperAdminDashboard = () => {
  const { data: stats, isLoading: statsLoading } = useDashboardStats();
  const { data: agencies, isLoading: agenciesLoading } = useAgencyStats();

  // Mock data for charts and activities - replace with real API calls
  const revenueChartData = useMemo(() => [
    { label: 'Jan', value: 125000 },
    { label: 'Feb', value: 145000 },
    { label: 'Mar', value: 165000 },
    { label: 'Apr', value: 155000 },
    { label: 'May', value: 185000 },
    { label: 'Jun', value: 205000 },
  ], []);

  const userGrowthData = useMemo(() => [
    { label: 'Week 1', value: 1200 },
    { label: 'Week 2', value: 1350 },
    { label: 'Week 3', value: 1420 },
    { label: 'Week 4', value: 1580 },
  ], []);

  const platformMetrics = useMemo(() => [
    { label: 'Active Models', value: stats?.active_models || 0, change: 12, icon: People, color: 'primary' as const },
    { label: 'Messages/Day', value: stats?.daily_messages || 0, change: 5, icon: ShowChart, color: 'info' as const },
    { label: 'Avg Revenue/User', value: `$${stats?.avg_revenue_per_user || 0}`, icon: Paid, color: 'success' as const },
    { label: 'Conversion Rate', value: `${stats?.conversion_rate || 0}%`, change: -2, icon: TrendingUp, color: 'warning' as const },
  ], [stats]);

  const recentActivities = useMemo(() => [
    {
      id: '1',
      type: 'user_joined' as const,
      title: 'New agency registered',
      description: 'Premium Agency LLC joined the platform',
      timestamp: new Date(Date.now() - 1000 * 60 * 30),
      metadata: { agency: 'Premium Agency LLC' },
    },
    {
      id: '2',
      type: 'payment' as const,
      title: 'Large payout processed',
      description: 'Model Sarah J. received payout',
      timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2),
      metadata: { amount: 15420 },
    },
    {
      id: '3',
      type: 'achievement' as const,
      title: 'Revenue milestone reached',
      description: 'Platform exceeded $2M monthly revenue',
      timestamp: new Date(Date.now() - 1000 * 60 * 60 * 5),
    },
    {
      id: '4',
      type: 'alert' as const,
      title: 'High server load detected',
      description: 'CPU usage at 85% - scaling initiated',
      timestamp: new Date(Date.now() - 1000 * 60 * 60 * 12),
    },
    {
      id: '5',
      type: 'success' as const,
      title: 'System update completed',
      description: 'v2.3.1 deployed successfully',
      timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24),
    },
  ], []);

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 3 }}>
        Platform Overview
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Total Agencies"
            value={agencies?.length || 0}
            icon={<Business fontSize="large" />}
            color="primary"
            loading={agenciesLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Total Users"
            value={stats?.total_users || 0}
            icon={<People fontSize="large" />}
            color="secondary"
            loading={statsLoading}
            trend={{
              value: 12,
              isPositive: true
            }}
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Platform Revenue"
            value={`$${stats?.total_revenue?.toLocaleString() || 0}`}
            icon={<AttachMoney fontSize="large" />}
            color="success"
            loading={statsLoading}
            trend={{
              value: 8.5,
              isPositive: true
            }}
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Growth Rate"
            value="15.3%"
            icon={<TrendingUp fontSize="large" />}
            color="info"
            loading={statsLoading}
          />
        </Grid>

        {/* Analytics Widgets Row */}
        <Grid item xs={12} md={6} lg={3}>
          <AnalyticsWidget
            title="Monthly Active Users"
            value={stats?.monthly_active_users || 0}
            previousValue={stats?.prev_monthly_active_users || 0}
            format="number"
            icon={<Groups />}
            color="primary"
            loading={statsLoading}
          />
        </Grid>
        <Grid item xs={12} md={6} lg={3}>
          <AnalyticsWidget
            title="Avg Session Duration"
            value={stats?.avg_session_duration || '0m'}
            icon={<ShowChart />}
            color="info"
            loading={statsLoading}
          />
        </Grid>
        <Grid item xs={12} md={6} lg={3}>
          <AnalyticsWidget
            title="Platform Commission"
            value={stats?.platform_commission || 0}
            previousValue={stats?.prev_platform_commission || 0}
            format="currency"
            icon={<Paid />}
            color="success"
            loading={statsLoading}
          />
        </Grid>
        <Grid item xs={12} md={6} lg={3}>
          <AnalyticsWidget
            title="Server Uptime"
            value={99.9}
            format="percentage"
            icon={<TrendingUp />}
            color="success"
            progress={99.9}
            loading={statsLoading}
          />
        </Grid>

        {/* Platform Metrics */}
        <Grid item xs={12}>
          <MetricsGrid
            title="Platform Metrics"
            metrics={platformMetrics}
            columns={4}
            loading={statsLoading}
          />
        </Grid>

        {/* Charts Row */}
        <Grid item xs={12} lg={8}>
          <ChartWidget
            title="Revenue Trend"
            data={revenueChartData}
            type="area"
            height={350}
            showTimeRangeSelector
            valueFormatter={(value) => `$${value.toLocaleString()}`}
            loading={statsLoading}
          />
        </Grid>
        <Grid item xs={12} lg={4}>
          <ChartWidget
            title="User Growth"
            data={userGrowthData}
            type="bar"
            height={350}
            color="#82ca9d"
            loading={statsLoading}
          />
        </Grid>

        {/* Agency Performance and Activity Feed */}
        <Grid item xs={12} lg={7}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Top Performing Agencies
            </Typography>
            {agenciesLoading ? (
              <Typography>Loading agencies...</Typography>
            ) : (
              <Box sx={{ mt: 2 }}>
                {agencies?.slice(0, 5).map((agency) => (
                  <Box
                    key={agency.agency_id}
                    sx={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      py: 1.5,
                      borderBottom: 1,
                      borderColor: 'divider',
                    }}
                  >
                    <Box>
                      <Typography variant="body1">{agency.agency_name}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {agency.total_models} models • {agency.active_subscriptions} active subs
                      </Typography>
                    </Box>
                    <Typography variant="h6" color="success.main">
                      ${agency.total_revenue.toLocaleString()}
                    </Typography>
                  </Box>
                ))}
              </Box>
            )}
          </Paper>
        </Grid>
        <Grid item xs={12} lg={5}>
          <ActivityFeed
            activities={recentActivities}
            loading={statsLoading}
          />
        </Grid>
      </Grid>
    </Box>
  );
};