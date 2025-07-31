import { Grid, Typography, Box } from '@mui/material';
import { Person, Message, TrendingUp, Assignment } from '@mui/icons-material';
import { StatsCard } from '@/components/dashboard/StatsCard';
import { useDashboardStats } from '@/hooks/useAnalytics';

export const AgencyAdminDashboard = () => {
  const { data: stats, isPending } = useDashboardStats();

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 3 }}>
        Admin Dashboard
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Total Models"
            value={stats?.active_models || 0}
            icon={<Person fontSize="large" />}
            color="primary"
            loading={isPending}
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Active Chats"
            value={stats?.active_chats || 0}
            icon={<Message fontSize="large" />}
            color="info"
            loading={isPending}
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Today's Messages"
            value={stats?.messages_today || 0}
            icon={<Assignment fontSize="large" />}
            color="secondary"
            loading={isPending}
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="New Users Today"
            value={stats?.new_users_today || 0}
            icon={<TrendingUp fontSize="large" />}
            color="success"
            loading={isPending}
          />
        </Grid>
      </Grid>
    </Box>
  );
};
