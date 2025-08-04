import React, { useState } from 'react';
import { 
  Box, 
  Button, 
  Container, 
  Paper, 
  Typography,
  Tabs,
  Tab,
} from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import { usePayouts, useBulkPayoutAction } from '@/hooks/usePayouts';
import { PayoutList } from '@/components/financial/PayoutList';
import { PayoutForm } from '@/components/financial/PayoutForm';
import { useAuth } from '@/hooks/useAuth';
import { PayoutStatus } from '@/types/financial';

const PayoutsPage: React.FC = () => {
  const { user } = useAuth();
  const [tabValue, setTabValue] = useState(0);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [filters, setFilters] = useState({
    status: '',
    modelId: undefined,
  });

  const { data: payouts = [], isLoading, refetch } = usePayouts(filters);
  const { mutate: bulkAction } = useBulkPayoutAction();

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
    
    switch (newValue) {
      case 0: // All
        setFilters({ ...filters, status: '' });
        break;
      case 1: // Pending
        setFilters({ ...filters, status: PayoutStatus.PENDING });
        break;
      case 2: // Processing
        setFilters({ ...filters, status: PayoutStatus.PROCESSING });
        break;
      case 3: // Completed
        setFilters({ ...filters, status: PayoutStatus.COMPLETED });
        break;
    }
  };

  const handleApprove = (payoutIds: number[]) => {
    bulkAction({
      payoutIds,
      action: 'approve',
      notes: `Approved by ${user?.email}`,
    });
  };

  const handleProcess = (payoutIds: number[]) => {
    bulkAction({
      payoutIds,
      action: 'process',
      notes: `Processed by ${user?.email}`,
    });
  };

  const handleCancel = (payoutIds: number[]) => {
    bulkAction({
      payoutIds,
      action: 'cancel',
      notes: `Cancelled by ${user?.email}`,
    });
  };

  const handleCreatePayout = (data: any) => {
    // This would be handled by the form component
    setShowCreateForm(false);
    refetch();
  };

  const canCreatePayouts = user?.role === 'super_admin' || 
    user?.role === 'agency_owner' || 
    user?.role === 'agency_admin';

  return (
    <Container maxWidth="xl">
      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" component="h1">
            Payouts
          </Typography>
          {canCreatePayouts && (
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setShowCreateForm(true)}
            >
              Create Payout
            </Button>
          )}
        </Box>

        <Paper sx={{ mb: 3 }}>
          <Tabs value={tabValue} onChange={handleTabChange}>
            <Tab label={`All (${payouts.length})`} />
            <Tab label={`Pending (${payouts.filter(p => p.status === PayoutStatus.PENDING).length})`} />
            <Tab label={`Processing (${payouts.filter(p => p.status === PayoutStatus.PROCESSING).length})`} />
            <Tab label={`Completed (${payouts.filter(p => p.status === PayoutStatus.COMPLETED).length})`} />
          </Tabs>
        </Paper>

        <PayoutList
          payouts={payouts}
          loading={isLoading}
          onRefresh={refetch}
          onApprove={handleApprove}
          onProcess={handleProcess}
          onCancel={handleCancel}
          showBulkActions={canCreatePayouts}
          userRole={user?.role}
        />
      </Box>

      <PayoutForm
        open={showCreateForm}
        onClose={() => setShowCreateForm(false)}
        onSubmit={handleCreatePayout}
      />
    </Container>
  );
};

export default PayoutsPage;