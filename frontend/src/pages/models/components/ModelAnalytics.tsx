import { useState, useMemo } from 'react';
import { logger } from '@/utils/logger';
import {
  Box,
  Grid,
  Typography,
  Card,
  CardContent,
  ToggleButton,
  ToggleButtonGroup,
  Button,
  Chip,
  Avatar,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  LinearProgress,
  Divider } from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  People,
  AttachMoney,
  Message,
  Favorite,
  Download } from '@mui/icons-material';
import { ChartWidget, MetricsGrid } from '@/components/dashboard';
import { format, subDays } from 'date-fns';

interface ModelAnalyticsProps {
  modelId: string;
}

export const ModelAnalytics = ({ modelId: _modelId }: ModelAnalyticsProps) => {
  const [period, setPeriod] = useState<'week' | 'month' | 'quarter' | 'year'>('month');

  // Mock data - replace with real API calls
  const subscriberGrowthData = useMemo(() => {
    const points = period === 'week' ? 7 : period === 'month' ? 30 : period === 'quarter' ? 90 : 365;
    let totalSubs = 1000;
    
    return Array.from({ length: Math.min(points, 30) }, (_, i) => {
      const date = subDays(new Date(), points - i - 1);
      const dailyGrowth = Math.floor(Math.random() * 20) - 5;
      totalSubs += dailyGrowth;
      
      return {
        label: format(date, points <= 30 ? 'MMM d' : 'MMM'),
        subscribers: totalSubs,
        growth: dailyGrowth };
    });
  }, [period]);

  const messageVolumeData = useMemo(() => {
    const points = period === 'week' ? 7 : period === 'month' ? 30 : period === 'quarter' ? 12 : 12;
    
    return Array.from({ length: points }, (_, i) => {
      const sent = Math.floor(Math.random() * 100) + 50;
      const received = Math.floor(Math.random() * 150) + 100;
      
      return {
        label: `Period ${i + 1}`,
        sent,
        received,
        total: sent + received };
    });
  }, [period]);

  const contentPerformanceData = [
    { label: 'Photos', value: 45, engagement: 8.5 },
    { label: 'Videos', value: 30, engagement: 12.3 },
    { label: 'Stories', value: 15, engagement: 6.7 },
    { label: 'Live Streams', value: 10, engagement: 15.2 },
  ];

  const topFans = [
    { 
      id: '1', 
      name: 'John Doe', 
      avatar: 'J', 
      totalSpent: 1250, 
      joinedDays: 180,
      lastActive: '2 hours ago',
      tier: 'platinum'
    },
    { 
      id: '2', 
      name: 'Mike Smith', 
      avatar: 'M', 
      totalSpent: 890, 
      joinedDays: 120,
      lastActive: '1 day ago',
      tier: 'gold'
    },
    { 
      id: '3', 
      name: 'David Johnson', 
      avatar: 'D', 
      totalSpent: 675, 
      joinedDays: 90,
      lastActive: '3 hours ago',
      tier: 'gold'
    },
    { 
      id: '4', 
      name: 'Chris Brown', 
      avatar: 'C', 
      totalSpent: 450, 
      joinedDays: 60,
      lastActive: '5 hours ago',
      tier: 'silver'
    },
    { 
      id: '5', 
      name: 'Alex Wilson', 
      avatar: 'A', 
      totalSpent: 325, 
      joinedDays: 30,
      lastActive: '1 hour ago',
      tier: 'silver'
    },
  ];

  const conversionMetrics = {
    subscriberToTipper: 15.3,
    messageToTip: 8.7,
    contentPurchaseRate: 12.4,
    avgFanLifetimeValue: 125.50,
    churnRate: 4.2,
    retentionRate: 95.8 };

  const metrics = [
    { 
      label: 'Active Subscribers', 
      value: 1234, 
      change: 12, 
      icon: People, 
      color: 'primary' as const 
    },
    { 
      label: 'Avg Revenue/Fan', 
      value: '$48.50', 
      change: 5, 
      icon: AttachMoney, 
      color: 'success' as const 
    },
    { 
      label: 'Engagement Rate', 
      value: '24.5%', 
      change: -2, 
      icon: Favorite, 
      color: 'error' as const 
    },
    { 
      label: 'Messages/Day', 
      value: 156, 
      change: 18, 
      icon: Message, 
      color: 'info' as const 
    },
  ];

  const getTierColor = (tier: string) => {
    switch (tier) {
      case 'platinum': return '#b0bec5';
      case 'gold': return '#ffd700';
      case 'silver': return '#c0c0c0';
      default: return '#cd7f32';
    }
  };

  const handleExport = () => {
    logger.info('Exporting analytics data...');
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5">Model Analytics</Typography>
        <Box display="flex" gap={2}>
          <ToggleButtonGroup
            value={period}
            exclusive
            onChange={(_, newPeriod) => newPeriod && setPeriod(newPeriod)}
            size="small"
          >
            <ToggleButton value="week">Week</ToggleButton>
            <ToggleButton value="month">Month</ToggleButton>
            <ToggleButton value="quarter">Quarter</ToggleButton>
            <ToggleButton value="year">Year</ToggleButton>
          </ToggleButtonGroup>
          <Button
            variant="outlined"
            startIcon={<Download />}
            onClick={handleExport}
          >
            Export
          </Button>
        </Box>
      </Box>

      {/* Key Metrics */}
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <MetricsGrid metrics={metrics} columns={4} />
        </Grid>

        {/* Subscriber Growth Chart */}
        <Grid item xs={12} lg={8}>
          <ChartWidget
            title="Subscriber Growth"
            data={subscriberGrowthData as any}
            type="area"
            height={350}
            dataKey="subscribers"
            showTimeRangeSelector={false}
          />
        </Grid>

        {/* Conversion Metrics */}
        <Grid item xs={12} lg={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Conversion Metrics
              </Typography>
              <Box display="flex" flexDirection="column" gap={2}>
                <Box>
                  <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Typography variant="body2" color="textSecondary">
                      Subscriber to Tipper
                    </Typography>
                    <Typography variant="body2" fontWeight="bold">
                      {conversionMetrics.subscriberToTipper}%
                    </Typography>
                  </Box>
                  <LinearProgress 
                    variant="determinate" 
                    value={conversionMetrics.subscriberToTipper} 
                    sx={{ mt: 0.5, height: 6, borderRadius: 3 }}
                  />
                </Box>
                <Box>
                  <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Typography variant="body2" color="textSecondary">
                      Message to Tip
                    </Typography>
                    <Typography variant="body2" fontWeight="bold">
                      {conversionMetrics.messageToTip}%
                    </Typography>
                  </Box>
                  <LinearProgress 
                    variant="determinate" 
                    value={conversionMetrics.messageToTip} 
                    sx={{ mt: 0.5, height: 6, borderRadius: 3 }}
                    color="secondary"
                  />
                </Box>
                <Box>
                  <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Typography variant="body2" color="textSecondary">
                      Content Purchase Rate
                    </Typography>
                    <Typography variant="body2" fontWeight="bold">
                      {conversionMetrics.contentPurchaseRate}%
                    </Typography>
                  </Box>
                  <LinearProgress 
                    variant="determinate" 
                    value={conversionMetrics.contentPurchaseRate} 
                    sx={{ mt: 0.5, height: 6, borderRadius: 3 }}
                    color="success"
                  />
                </Box>
                <Divider sx={{ my: 1 }} />
                <Box display="flex" justifyContent="space-between">
                  <Typography variant="body2" color="textSecondary">
                    Avg Fan Lifetime Value
                  </Typography>
                  <Typography variant="body2" fontWeight="bold" color="success.main">
                    ${conversionMetrics.avgFanLifetimeValue}
                  </Typography>
                </Box>
                <Box display="flex" justifyContent="space-between">
                  <Typography variant="body2" color="textSecondary">
                    Retention Rate
                  </Typography>
                  <Typography variant="body2" fontWeight="bold" color="success.main">
                    {conversionMetrics.retentionRate}%
                  </Typography>
                </Box>
                <Box display="flex" justifyContent="space-between">
                  <Typography variant="body2" color="textSecondary">
                    Churn Rate
                  </Typography>
                  <Typography variant="body2" fontWeight="bold" color="error.main">
                    {conversionMetrics.churnRate}%
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Message Volume */}
        <Grid item xs={12} md={6}>
          <ChartWidget
            title="Message Volume"
            data={messageVolumeData as any}
            type="bar"
            height={300}
            dataKey="total"
            color="#82ca9d"
          />
        </Grid>

        {/* Content Performance */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Content Performance
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Type</TableCell>
                      <TableCell align="right">Posts</TableCell>
                      <TableCell align="right">Engagement</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {contentPerformanceData.map((content) => (
                      <TableRow key={content.label}>
                        <TableCell>{content.label}</TableCell>
                        <TableCell align="right">{content.value}</TableCell>
                        <TableCell align="right">
                          <Box display="flex" alignItems="center" justifyContent="flex-end" gap={0.5}>
                            {content.engagement > 10 ? (
                              <TrendingUp fontSize="small" color="success" />
                            ) : (
                              <TrendingDown fontSize="small" color="error" />
                            )}
                            <Typography variant="body2" color={content.engagement > 10 ? 'success.main' : 'error.main'}>
                              {content.engagement}%
                            </Typography>
                          </Box>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* Top Fans */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Top Fans
              </Typography>
              <List>
                {topFans.map((fan, index) => (
                  <ListItem key={fan.id} divider={index < topFans.length - 1}>
                    <ListItemAvatar>
                      <Avatar sx={{ bgcolor: getTierColor(fan.tier) }}>
                        {fan.avatar}
                      </Avatar>
                    </ListItemAvatar>
                    <ListItemText
                      primary={
                        <Box display="flex" alignItems="center" gap={1}>
                          <Typography variant="body1">{fan.name}</Typography>
                          <Chip 
                            label={fan.tier} 
                            size="small" 
                            sx={{ 
                              bgcolor: getTierColor(fan.tier),
                              color: 'white',
                              fontSize: '0.7rem',
                              height: 20 }} 
                          />
                        </Box>
                      }
                      secondary={
                        <Typography variant="body2" color="textSecondary">
                          Member for {fan.joinedDays} days • Last active {fan.lastActive}
                        </Typography>
                      }
                    />
                    <Box textAlign="right">
                      <Typography variant="h6" color="success.main">
                        ${fan.totalSpent}
                      </Typography>
                      <Typography variant="caption" color="textSecondary">
                        Total spent
                      </Typography>
                    </Box>
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};
