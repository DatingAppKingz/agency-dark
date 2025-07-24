import { Grid, Typography, Box, Paper } from '@mui/material';
import { Business, People, AttachMoney, TrendingUp } from '@mui/icons-material';
import { StatsCard } from '@/components/dashboard/StatsCard';
import { useDashboardStats, useAgencyStats } from '@/hooks/useAnalytics';

export const SuperAdminDashboard = () => {
  const { data: stats, isLoading: statsLoading } = useDashboardStats();
  const { data: agencies, isLoading: agenciesLoading } = useAgencyStats();

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

        <Grid item xs={12}>
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
      </Grid>
    </Box>
  );
};