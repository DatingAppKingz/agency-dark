import { useState } from 'react';
import {
  Box,
  Typography,
  Grid,
  Paper,
  Tab,
  Tabs,
  Button,
  IconButton } from '@mui/material';
import {
  TrendingUp,
  People,
  AttachMoney,
  ChatBubble,
  Refresh,
  Download,
  Compare } from '@mui/icons-material';
import { DateRangePicker } from '@/components/common/DateRangePicker';
import { PlatformAnalytics } from '@/components/analytics/PlatformAnalytics';
import { AgencyAnalytics } from '@/components/analytics/AgencyAnalytics';
import { ModelPerformance } from '@/components/analytics/ModelPerformance';
import { ChatterMetrics } from '@/components/analytics/ChatterMetrics';
import { useAuthStore } from '@/store/authStore';
import { startOfMonth, endOfMonth, subMonths } from 'date-fns';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel = ({ children, value, index }: TabPanelProps) => {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`analytics-tabpanel-${index}`}
      aria-labelledby={`analytics-tab-${index}`}
    >
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
};

const AnalyticsPage = () => {
  const { user } = useAuthStore();
  const [selectedTab, setSelectedTab] = useState(0);
  const [dateRange, setDateRange] = useState({
    start: startOfMonth(subMonths(new Date(), 1)),
    end: endOfMonth(new Date()) });
  const [comparisonMode, setComparisonMode] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setSelectedTab(newValue);
  };

  const handleRefresh = () => {
    setRefreshKey(prev => prev + 1);
  };

  const handleExport = () => {
    // TODO: Implement export functionality
    console.log('Exporting analytics data...');
  };

  // Determine available tabs based on user role
  const getAvailableTabs = () => {
    const tabs = [];
    
    if (user?.role === 'super_admin') {
      tabs.push({ label: 'Platform Overview', icon: <TrendingUp />, component: <PlatformAnalytics dateRange={dateRange} refreshKey={refreshKey} /> });
    }
    
    if (['super_admin', 'agency_owner', 'agency_admin'].includes(user?.role || '')) {
      tabs.push({ label: 'Agency Analytics', icon: <People />, component: <AgencyAnalytics dateRange={dateRange} refreshKey={refreshKey} /> });
    }
    
    if (['super_admin', 'agency_owner', 'agency_admin', 'model'].includes(user?.role || '')) {
      tabs.push({ label: 'Model Performance', icon: <AttachMoney />, component: <ModelPerformance dateRange={dateRange} refreshKey={refreshKey} /> });
    }
    
    if (['super_admin', 'agency_owner', 'agency_admin', 'chatter'].includes(user?.role || '')) {
      tabs.push({ label: 'Chatter Metrics', icon: <ChatBubble />, component: <ChatterMetrics dateRange={dateRange} refreshKey={refreshKey} /> });
    }
    
    return tabs;
  };

  const availableTabs = getAvailableTabs();

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Analytics & Insights</Typography>
        
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <DateRangePicker
            startDate={dateRange.start}
            endDate={dateRange.end}
            onStartDateChange={(date) => setDateRange(prev => ({ ...prev, start: date }))}
            onEndDateChange={(date) => setDateRange(prev => ({ ...prev, end: date }))}
          />
          
          <Button
            variant={comparisonMode ? 'contained' : 'outlined'}
            startIcon={<Compare />}
            onClick={() => setComparisonMode(!comparisonMode)}
            size="small"
          >
            Compare
          </Button>
          
          <IconButton onClick={handleRefresh} color="primary">
            <Refresh />
          </IconButton>
          
          <Button
            variant="outlined"
            startIcon={<Download />}
            onClick={handleExport}
            size="small"
          >
            Export
          </Button>
        </Box>
      </Box>

      <Paper sx={{ mb: 3 }}>
        <Tabs
          value={selectedTab}
          onChange={handleTabChange}
          variant="fullWidth"
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          {availableTabs.map((tab, index) => (
            <Tab
              key={index}
              icon={tab.icon}
              label={tab.label}
              id={`analytics-tab-${index}`}
              aria-controls={`analytics-tabpanel-${index}`}
            />
          ))}
        </Tabs>

        {availableTabs.map((tab, index) => (
          <TabPanel key={index} value={selectedTab} index={index}>
            {tab.component}
          </TabPanel>
        ))}
      </Paper>

      {/* Quick Stats Summary */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={3}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h4" color="primary">
              $125,430
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Total Revenue
            </Typography>
            <Typography variant="body2" color="success.main">
              +12.5% from last period
            </Typography>
          </Paper>
        </Grid>
        
        <Grid item xs={12} md={3}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h4" color="primary">
              3,542
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Active Users
            </Typography>
            <Typography variant="body2" color="success.main">
              +8.3% from last period
            </Typography>
          </Paper>
        </Grid>
        
        <Grid item xs={12} md={3}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h4" color="primary">
              45,291
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Messages Sent
            </Typography>
            <Typography variant="body2" color="error.main">
              -2.1% from last period
            </Typography>
          </Paper>
        </Grid>
        
        <Grid item xs={12} md={3}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h4" color="primary">
              89.2%
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Satisfaction Rate
            </Typography>
            <Typography variant="body2" color="success.main">
              +0.5% from last period
            </Typography>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default AnalyticsPage;
