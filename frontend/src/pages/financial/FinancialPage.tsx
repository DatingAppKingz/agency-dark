import { useState } from 'react';
import {
  Box,
  Tab,
  Tabs,
  Paper,
} from '@mui/material';
import {
  TrendingUp,
  AccountBalance,
  Receipt,
  Calculate,
  CreditCard,
  Assessment,
  Description,
  AttachMoney,
  AccountBalanceWallet,
} from '@mui/icons-material';
import { RevenueOverview } from '@/components/financial/RevenueOverview';
import { PayoutManagement } from '@/components/financial/PayoutManagement';
import { TransactionHistory } from '@/components/financial/TransactionHistory';
import { CommissionCalculator } from '@/components/financial/CommissionCalculator';
import { PaymentMethods } from '@/components/financial/PaymentMethods';
import { FinancialReports } from '@/components/financial/FinancialReports';
import { TaxDocuments } from '@/components/financial/TaxDocuments';
import { EarningsStatements } from '@/components/financial/EarningsStatements';
import { CommissionBreakdown } from '@/components/financial/CommissionBreakdown';
import { useAuth } from '@/hooks/useAuth';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel = (props: TabPanelProps) => {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`financial-tabpanel-${index}`}
      aria-labelledby={`financial-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
};

const FinancialPage = () => {
  const [tab, setTab] = useState(0);
  const { user } = useAuth();

  // Get model/agency ID based on user role
  const modelId = user?.role === 'model' ? user.id : undefined;
  const agencyId = ['agency_owner', 'agency_admin'].includes(user?.role || '') ? user?.agency_id : undefined;

  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setTab(newValue);
  };

  return (
    <Box>
      <Paper sx={{ mb: 3 }}>
        <Tabs
          value={tab}
          onChange={handleTabChange}
          variant="scrollable"
          scrollButtons="auto"
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab
            icon={<TrendingUp />}
            iconPosition="start"
            label="Revenue Overview"
          />
          <Tab
            icon={<AccountBalance />}
            iconPosition="start"
            label="Payouts"
          />
          <Tab
            icon={<Receipt />}
            iconPosition="start"
            label="Transactions"
          />
          <Tab
            icon={<Calculate />}
            iconPosition="start"
            label="Commission Calculator"
          />
          <Tab
            icon={<CreditCard />}
            iconPosition="start"
            label="Payment Methods"
          />
          <Tab
            icon={<Assessment />}
            iconPosition="start"
            label="Reports"
          />
          <Tab
            icon={<Description />}
            iconPosition="start"
            label="Tax Documents"
          />
          <Tab
            icon={<AttachMoney />}
            iconPosition="start"
            label="Earnings"
          />
          <Tab
            icon={<AccountBalanceWallet />}
            iconPosition="start"
            label="Commissions"
          />
        </Tabs>
      </Paper>

      <TabPanel value={tab} index={0}>
        <RevenueOverview modelId={modelId} agencyId={agencyId} />
      </TabPanel>
      <TabPanel value={tab} index={1}>
        <PayoutManagement modelId={modelId} agencyId={agencyId} />
      </TabPanel>
      <TabPanel value={tab} index={2}>
        <TransactionHistory modelId={modelId} agencyId={agencyId} />
      </TabPanel>
      <TabPanel value={tab} index={3}>
        <CommissionCalculator modelId={modelId} agencyId={agencyId} />
      </TabPanel>
      <TabPanel value={tab} index={4}>
        <PaymentMethods />
      </TabPanel>
      <TabPanel value={tab} index={5}>
        <FinancialReports modelId={modelId} agencyId={agencyId} />
      </TabPanel>
      <TabPanel value={tab} index={6}>
        <TaxDocuments modelId={modelId} agencyId={agencyId} />
      </TabPanel>
      <TabPanel value={tab} index={7}>
        <EarningsStatements modelId={modelId} agencyId={agencyId} />
      </TabPanel>
      <TabPanel value={tab} index={8}>
        <CommissionBreakdown agencyId={agencyId} />
      </TabPanel>
    </Box>
  );
};

export default FinancialPage;
