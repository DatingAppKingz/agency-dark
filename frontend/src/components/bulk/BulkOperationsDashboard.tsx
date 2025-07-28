import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Tabs,
  Tab,
  Grid,
  Alert,
  Paper,
} from '@mui/material';
import {
  Send as MessageIcon,
  People as UsersIcon,
  Description as ContentIcon,
  History as HistoryIcon,
  Schedule as ScheduleIcon,
  CheckCircle as SuccessIcon,
} from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { bulkOperationsService } from '@/services/api/bulkOperations';
import BulkMessageOperations from './BulkMessageOperations';
import BulkUserOperations from './BulkUserOperations';
import BulkContentOperations from './BulkContentOperations';
import BulkOperationProgress from './BulkOperationProgress';
import BulkOperationHistory from './BulkOperationHistory';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div role="tabpanel" hidden={value !== index} {...other}>
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
}

const BulkOperationsDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);

  // Fetch stats
  const { data: stats } = useQuery({
    queryKey: ['bulk-operations-stats'],
    queryFn: () => bulkOperationsService.getBulkOperationStats(),
  });


  const renderStats = () => (
    <Grid container spacing={2} sx={{ mb: 3 }}>
      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Box display="flex" justifyContent="space-between" alignItems="center">
              <Box>
                <Typography color="text.secondary" gutterBottom>
                  Total Operations
                </Typography>
                <Typography variant="h4">
                  {stats?.total_operations || 0}
                </Typography>
              </Box>
              <ScheduleIcon color="action" sx={{ fontSize: 40 }} />
            </Box>
          </CardContent>
        </Card>
      </Grid>
      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Box display="flex" justifyContent="space-between" alignItems="center">
              <Box>
                <Typography color="text.secondary" gutterBottom>
                  Items Processed
                </Typography>
                <Typography variant="h4">
                  {stats?.total_items_processed || 0}
                </Typography>
              </Box>
              <SuccessIcon color="success" sx={{ fontSize: 40 }} />
            </Box>
          </CardContent>
        </Card>
      </Grid>
      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Box display="flex" justifyContent="space-between" alignItems="center">
              <Box>
                <Typography color="text.secondary" gutterBottom>
                  Success Rate
                </Typography>
                <Typography variant="h4">
                  {stats?.success_rate || 0}%
                </Typography>
              </Box>
              <SuccessIcon color="success" sx={{ fontSize: 40 }} />
            </Box>
          </CardContent>
        </Card>
      </Grid>
      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Box display="flex" justifyContent="space-between" alignItems="center">
              <Box>
                <Typography color="text.secondary" gutterBottom>
                  Active Now
                </Typography>
                <Typography variant="h4">
                  {stats?.active_operations || 0}
                </Typography>
              </Box>
              <ScheduleIcon color="primary" sx={{ fontSize: 40 }} />
            </Box>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );


  return (
    <Box>
      {/* Stats Overview */}
      {renderStats()}

      {/* Info Alert */}
      <Alert severity="info" sx={{ mb: 3 }}>
        <Typography variant="body2">
          <strong>Bulk Operations:</strong>
          <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
            <li>Process multiple items at once to save time</li>
            <li>Operations run in the background - you can continue working</li>
            <li>Check the history tab to monitor progress and results</li>
            <li>Failed items can be retried individually</li>
          </ul>
        </Typography>
      </Alert>

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs value={activeTab} onChange={(_, value) => setActiveTab(value)}>
          <Tab icon={<MessageIcon />} label="Messages" />
          <Tab icon={<UsersIcon />} label="Users" />
          <Tab icon={<ContentIcon />} label="Content" />
          <Tab icon={<HistoryIcon />} label="History" />
        </Tabs>
      </Paper>

      {/* Tab Panels */}
      <TabPanel value={activeTab} index={0}>
        <BulkMessageOperations />
      </TabPanel>

      <TabPanel value={activeTab} index={1}>
        <BulkUserOperations />
      </TabPanel>

      <TabPanel value={activeTab} index={2}>
        <BulkContentOperations />
      </TabPanel>

      <TabPanel value={activeTab} index={3}>
        <BulkOperationHistory />
      </TabPanel>

    </Box>
  );
};

export default BulkOperationsDashboard;