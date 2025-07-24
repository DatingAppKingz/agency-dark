import { Grid, Typography, Box, Paper, Button } from '@mui/material';
import { Person, AttachMoney, Message, TrendingUp, Add } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { StatsCard } from '@/components/dashboard/StatsCard';
import { useDashboardStats, useModelPerformance } from '@/hooks/useAnalytics';

export const AgencyOwnerDashboard = () => {
  const navigate = useNavigate();
  const { data: stats, isLoading: statsLoading } = useDashboardStats();
  const { data: models, isLoading: modelsLoading } = useModelPerformance('month');

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">
          Agency Dashboard
        </Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="outlined"
            startIcon={<Add />}
            onClick={() => navigate('/dashboard/models')}
          >
            Add Model
          </Button>
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={() => navigate('/dashboard/users')}
          >
            Add User
          </Button>
        </Box>
      </Box>

      <Grid container spacing={3}>
        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Active Models"
            value={stats?.active_models || 0}
            icon={<Person fontSize="large" />}
            color="primary"
            loading={statsLoading}
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Monthly Revenue"
            value={`$${stats?.total_revenue?.toLocaleString() || 0}`}
            icon={<AttachMoney fontSize="large" />}
            color="success"
            loading={statsLoading}
            trend={{
              value: 23.5,
              isPositive: true
            }}
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Total Messages"
            value={stats?.total_messages?.toLocaleString() || 0}
            icon={<Message fontSize="large" />}
            color="info"
            loading={statsLoading}
            trend={{
              value: 15,
              isPositive: true
            }}
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Active Chats"
            value={stats?.active_chats || 0}
            icon={<TrendingUp fontSize="large" />}
            color="warning"
            loading={statsLoading}
          />
        </Grid>

        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Top Performing Models
            </Typography>
            {modelsLoading ? (
              <Typography>Loading models...</Typography>
            ) : (
              <Box sx={{ mt: 2 }}>
                {models?.slice(0, 5).map((model) => (
                  <Box
                    key={model.model_id}
                    sx={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      py: 1.5,
                      borderBottom: 1,
                      borderColor: 'divider',
                      cursor: 'pointer',
                      '&:hover': {
                        backgroundColor: 'action.hover',
                      },
                    }}
                    onClick={() => navigate(`/dashboard/models/${model.model_id}`)}
                  >
                    <Box>
                      <Typography variant="body1">{model.model_name}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {model.fans} fans • {model.messages} messages
                      </Typography>
                    </Box>
                    <Box sx={{ textAlign: 'right' }}>
                      <Typography variant="h6" color="success.main">
                        ${model.revenue.toLocaleString()}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {model.conversion_rate}% conversion
                      </Typography>
                    </Box>
                  </Box>
                ))}
              </Box>
            )}
          </Paper>
        </Grid>

        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Quick Actions
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mt: 2 }}>
              <Button fullWidth variant="outlined" onClick={() => navigate('/dashboard/financial')}>
                View Payouts
              </Button>
              <Button fullWidth variant="outlined" onClick={() => navigate('/dashboard/analytics')}>
                Analytics Report
              </Button>
              <Button fullWidth variant="outlined" onClick={() => navigate('/dashboard/settings')}>
                Agency Settings
              </Button>
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};