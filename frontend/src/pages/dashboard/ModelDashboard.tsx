import { Grid, Typography, Box, Paper, LinearProgress } from '@mui/material';
import { AttachMoney, People, Message, TrendingUp } from '@mui/icons-material';
import { StatsCard } from '@/components/dashboard/StatsCard';
import { useAuthStore } from '@/store/authStore';

export const ModelDashboard = () => {
  const { user } = useAuthStore();

  // Mock data - will be replaced with real API calls
  const stats = {
    monthlyEarnings: 15420,
    totalFans: 234,
    activeChats: 12,
    conversionRate: 3.5,
    todayEarnings: 1250,
    newFans: 8,
  };

  const earningsGoal = 20000;
  const earningsProgress = (stats.monthlyEarnings / earningsGoal) * 100;

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 3 }}>
        Welcome back, {user?.full_name}!
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Monthly Earnings"
            value={`$${stats.monthlyEarnings.toLocaleString()}`}
            icon={<AttachMoney fontSize="large" />}
            color="success"
            trend={{
              value: 15.5,
              isPositive: true
            }}
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Total Fans"
            value={stats.totalFans}
            icon={<People fontSize="large" />}
            color="primary"
            trend={{
              value: 8,
              isPositive: true
            }}
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Active Chats"
            value={stats.activeChats}
            icon={<Message fontSize="large" />}
            color="info"
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Conversion Rate"
            value={`${stats.conversionRate}%`}
            icon={<TrendingUp fontSize="large" />}
            color="warning"
            trend={{
              value: 0.5,
              isPositive: true
            }}
          />
        </Grid>

        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Earnings Goal Progress
            </Typography>
            <Box sx={{ mt: 3 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="body2" color="text.secondary">
                  Current: ${stats.monthlyEarnings.toLocaleString()}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Goal: ${earningsGoal.toLocaleString()}
                </Typography>
              </Box>
              <LinearProgress 
                variant="determinate" 
                value={earningsProgress} 
                sx={{ height: 10, borderRadius: 5 }}
              />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {earningsProgress.toFixed(1)}% of monthly goal achieved
              </Typography>
            </Box>

            <Box sx={{ mt: 4 }}>
              <Typography variant="h6" gutterBottom>
                Today's Performance
              </Typography>
              <Grid container spacing={2} sx={{ mt: 1 }}>
                <Grid item xs={4}>
                  <Box>
                    <Typography variant="h5" color="primary">
                      ${stats.todayEarnings}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Earnings
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={4}>
                  <Box>
                    <Typography variant="h5" color="primary">
                      {stats.newFans}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      New Fans
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={4}>
                  <Box>
                    <Typography variant="h5" color="primary">
                      45
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Messages
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
            </Box>
          </Paper>
        </Grid>

        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Recent Activity
            </Typography>
            <Box sx={{ mt: 2 }}>
              {[
                { fan: 'John D.', action: 'Started new chat', time: '5 min ago' },
                { fan: 'Sarah M.', action: 'Purchased content', time: '15 min ago' },
                { fan: 'Mike R.', action: 'Renewed subscription', time: '1 hour ago' },
                { fan: 'Emma L.', action: 'Sent tip $50', time: '2 hours ago' },
              ].map((activity, index) => (
                <Box
                  key={index}
                  sx={{
                    py: 1.5,
                    borderBottom: index < 3 ? 1 : 0,
                    borderColor: 'divider',
                  }}
                >
                  <Typography variant="body2">{activity.fan}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {activity.action} • {activity.time}
                  </Typography>
                </Box>
              ))}
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};
