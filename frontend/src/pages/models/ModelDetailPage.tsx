import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Button,
  Tabs,
  Tab,
  Avatar,
  Chip,
  IconButton,
  Skeleton,
} from '@mui/material';
import {
  ArrowBack,
  Edit,
  AttachMoney,
  People,
  TrendingUp,
  Message,
  Schedule,
  Settings,
  Analytics,
} from '@mui/icons-material';
import { StatsCard } from '@/components/dashboard/StatsCard';
import { 
  ModelPerformance, 
  ModelEarnings, 
  ModelAvailability, 
  ModelPreferences,
  ModelAnalytics 
} from './components';
import { useModel, useModelStats } from '@/hooks/useModels';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel = ({ children, value, index }: TabPanelProps) => {
  return (
    <div role="tabpanel" hidden={value !== index}>
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
};

const ModelDetailPage = () => {
  const { modelId } = useParams<{ modelId: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState(0);
  
  const { data: model, isLoading: modelLoading } = useModel(modelId!);
  const { data: stats, isLoading: statsLoading } = useModelStats(modelId!, 'month');

  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  if (modelLoading) {
    return (
      <Box>
        <Skeleton variant="rectangular" height={200} sx={{ mb: 3 }} />
        <Grid container spacing={3}>
          {[1, 2, 3, 4].map((i) => (
            <Grid item xs={12} sm={6} md={3} key={i}>
              <Skeleton variant="rectangular" height={120} />
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  if (!model) {
    return (
      <Box sx={{ textAlign: 'center', py: 6 }}>
        <Typography variant="h6">Model not found</Typography>
        <Button
          startIcon={<ArrowBack />}
          onClick={() => navigate('/dashboard/models')}
          sx={{ mt: 2 }}
        >
          Back to Models
        </Button>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Button
          startIcon={<ArrowBack />}
          onClick={() => navigate('/dashboard/models')}
          sx={{ mb: 2 }}
        >
          Back to Models
        </Button>
      </Box>

      {/* Profile Header */}
      <Paper
        sx={{
          mb: 3,
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <Box
          sx={{
            height: 200,
            backgroundImage: model.cover_image_url ? `url(${model.cover_image_url})` : 'none',
            backgroundColor: 'grey.200',
            backgroundSize: 'cover',
            backgroundPosition: 'center',
          }}
        />
        <Box sx={{ p: 3, display: 'flex', alignItems: 'center', gap: 3 }}>
          <Avatar
            src={model.avatar_url}
            sx={{
              width: 120,
              height: 120,
              mt: -8,
              border: '4px solid',
              borderColor: 'background.paper',
            }}
          >
            {model.stage_name[0]}
          </Avatar>
          <Box sx={{ flexGrow: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography variant="h4">{model.stage_name}</Typography>
              <Chip
                label={model.is_active ? 'Active' : 'Inactive'}
                color={model.is_active ? 'success' : 'default'}
                size="small"
              />
            </Box>
            {model.user && (
              <Typography variant="body1" color="text.secondary">
                {model.user.full_name} • {model.user.email}
              </Typography>
            )}
            {model.bio && (
              <Typography variant="body2" sx={{ mt: 1 }}>
                {model.bio}
              </Typography>
            )}
          </Box>
          <IconButton
            onClick={() => navigate(`/dashboard/models/${model.id}/edit`)}
            sx={{
              position: 'absolute',
              top: 16,
              right: 16,
              backgroundColor: 'background.paper',
            }}
          >
            <Edit />
          </IconButton>
        </Box>
      </Paper>

      {/* Stats Grid */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Monthly Earnings"
            value={`$${stats?.total_earnings?.toLocaleString() || 0}`}
            icon={<AttachMoney fontSize="large" />}
            color="success"
            loading={statsLoading}
            trend={stats && {
              value: 15.2,
              isPositive: true,
            }}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Total Fans"
            value={model.total_fans || 0}
            icon={<People fontSize="large" />}
            color="primary"
            loading={statsLoading}
            trend={stats && {
              value: stats.new_fans - stats.lost_fans,
              isPositive: stats.new_fans > stats.lost_fans,
            }}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Active Chats"
            value={model.active_chats || 0}
            icon={<Message fontSize="large" />}
            color="info"
            loading={statsLoading}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Conversion Rate"
            value={`${stats?.conversion_rate?.toFixed(1) || 0}%`}
            icon={<TrendingUp fontSize="large" />}
            color="warning"
            loading={statsLoading}
          />
        </Grid>
      </Grid>

      {/* Tabs */}
      <Paper>
        <Tabs value={activeTab} onChange={handleTabChange}>
          <Tab label="Analytics" icon={<Analytics />} iconPosition="start" />
          <Tab label="Performance" icon={<TrendingUp />} iconPosition="start" />
          <Tab label="Earnings" icon={<AttachMoney />} iconPosition="start" />
          <Tab label="Availability" icon={<Schedule />} iconPosition="start" />
          <Tab label="Preferences" icon={<Settings />} iconPosition="start" />
        </Tabs>

        <TabPanel value={activeTab} index={0}>
          <ModelAnalytics modelId={model.id} />
        </TabPanel>
        <TabPanel value={activeTab} index={1}>
          <ModelPerformance modelId={model.id} />
        </TabPanel>
        <TabPanel value={activeTab} index={2}>
          <ModelEarnings modelId={model.id} />
        </TabPanel>
        <TabPanel value={activeTab} index={3}>
          <ModelAvailability modelId={model.id} />
        </TabPanel>
        <TabPanel value={activeTab} index={4}>
          <ModelPreferences modelId={model.id} />
        </TabPanel>
      </Paper>
    </Box>
  );
};

export default ModelDetailPage;