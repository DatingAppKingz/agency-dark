import React, { useState } from 'react';
import { 
  Box, 
  Container, 
  Typography,
  Paper,
  Grid,
  Card,
  CardContent,
} from '@mui/material';
import { 
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  AttachMoney as MoneyIcon,
  Receipt as ReceiptIcon,
} from '@mui/icons-material';
import { useTransactions } from '@/hooks/useTransactions';
import { TransactionList } from '@/components/financial/TransactionList';
import { TransactionType } from '@/types/financial';
import { formatCurrency } from '@/utils/formatters';
import { startOfMonth, endOfMonth, format } from 'date-fns';

const TransactionsPage: React.FC = () => {
  const [filters, setFilters] = useState({
    startDate: format(startOfMonth(new Date()), 'yyyy-MM-dd'),
    endDate: format(endOfMonth(new Date()), 'yyyy-MM-dd'),
  });

  const { data: transactions = [], isLoading, refetch } = useTransactions(filters);

  // Calculate summary stats
  const summaryStats = transactions.reduce(
    (acc, transaction) => {
      acc.totalGross += transaction.gross_amount;
      acc.totalFees += transaction.platform_fee;
      acc.totalCommission += transaction.agency_commission;
      acc.totalNet += transaction.net_amount;
      
      if (transaction.type === TransactionType.TIP) {
        acc.tips += transaction.gross_amount;
      } else if (transaction.type === TransactionType.SUBSCRIPTION) {
        acc.subscriptions += transaction.gross_amount;
      } else if (transaction.type === TransactionType.PPV) {
        acc.ppv += transaction.gross_amount;
      }
      
      return acc;
    },
    {
      totalGross: 0,
      totalFees: 0,
      totalCommission: 0,
      totalNet: 0,
      tips: 0,
      subscriptions: 0,
      ppv: 0,
    }
  );

  const handleViewDetails = (transaction: any) => {
    // TODO: Implement transaction details view
    console.log('View transaction:', transaction);
  };

  const StatCard = ({ 
    title, 
    value, 
    icon, 
    color = 'primary.main',
    trend,
  }: { 
    title: string; 
    value: string | number; 
    icon: React.ReactNode;
    color?: string;
    trend?: number;
  }) => (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography color="text.secondary" gutterBottom variant="caption">
              {title}
            </Typography>
            <Typography variant="h5" component="div">
              {value}
            </Typography>
            {trend !== undefined && (
              <Box sx={{ display: 'flex', alignItems: 'center', mt: 1 }}>
                {trend > 0 ? (
                  <TrendingUpIcon sx={{ color: 'success.main', fontSize: 16 }} />
                ) : (
                  <TrendingDownIcon sx={{ color: 'error.main', fontSize: 16 }} />
                )}
                <Typography
                  variant="caption"
                  sx={{ 
                    color: trend > 0 ? 'success.main' : 'error.main',
                    ml: 0.5 
                  }}
                >
                  {Math.abs(trend)}% vs last period
                </Typography>
              </Box>
            )}
          </Box>
          <Box
            sx={{
              backgroundColor: color,
              borderRadius: 2,
              p: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              opacity: 0.1,
            }}
          >
            {icon}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );

  return (
    <Container maxWidth="xl">
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Transactions
        </Typography>
        
        {/* Summary Cards */}
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              title="Total Revenue"
              value={formatCurrency(summaryStats.totalGross, 'USD')}
              icon={<MoneyIcon sx={{ fontSize: 40 }} />}
              color="primary.main"
              trend={12.5}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              title="Platform Fees"
              value={formatCurrency(summaryStats.totalFees, 'USD')}
              icon={<ReceiptIcon sx={{ fontSize: 40 }} />}
              color="warning.main"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              title="Agency Commission"
              value={formatCurrency(summaryStats.totalCommission, 'USD')}
              icon={<MoneyIcon sx={{ fontSize: 40 }} />}
              color="info.main"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              title="Model Earnings"
              value={formatCurrency(summaryStats.totalNet, 'USD')}
              icon={<MoneyIcon sx={{ fontSize: 40 }} />}
              color="success.main"
              trend={8.3}
            />
          </Grid>
        </Grid>

        {/* Revenue by Type */}
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Revenue by Type
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={4}>
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Tips
                    </Typography>
                    <Typography variant="h6">
                      {formatCurrency(summaryStats.tips, 'USD')}
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} sm={4}>
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Subscriptions
                    </Typography>
                    <Typography variant="h6">
                      {formatCurrency(summaryStats.subscriptions, 'USD')}
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} sm={4}>
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      PPV Content
                    </Typography>
                    <Typography variant="h6">
                      {formatCurrency(summaryStats.ppv, 'USD')}
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
            </Paper>
          </Grid>
        </Grid>

        {/* Transaction List */}
        <TransactionList
          transactions={transactions}
          loading={isLoading}
          onRefresh={refetch}
          onViewDetails={handleViewDetails}
        />
      </Box>
    </Container>
  );
};

export default TransactionsPage;