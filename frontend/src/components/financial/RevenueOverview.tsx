import { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Grid,
  Box,
  ToggleButton,
  ToggleButtonGroup,
  CircularProgress,
  Alert,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  AttachMoney,
  Receipt,
  AccountBalance,
} from '@mui/icons-material';
import { LineChart, Line, AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { useQuery } from '@tanstack/react-query';
import { financialApi } from '@/services/api/financial';
import type { Revenue } from '@/types/financial';

interface StatCardProps {
  title: string;
  value: string | number;
  change?: number;
  icon: React.ReactNode;
  color: string;
}

const StatCard = ({ title, value, change, icon, color }: StatCardProps) => (
  <Card>
    <CardContent>
      <Box display="flex" justifyContent="space-between" alignItems="flex-start">
        <Box>
          <Typography color="textSecondary" gutterBottom variant="body2">
            {title}
          </Typography>
          <Typography variant="h5" component="div">
            {value}
          </Typography>
          {change !== undefined && (
            <Box display="flex" alignItems="center" mt={1}>
              {change >= 0 ? (
                <TrendingUp sx={{ fontSize: 16, color: 'success.main', mr: 0.5 }} />
              ) : (
                <TrendingDown sx={{ fontSize: 16, color: 'error.main', mr: 0.5 }} />
              )}
              <Typography
                variant="body2"
                color={change >= 0 ? 'success.main' : 'error.main'}
              >
                {Math.abs(change)}%
              </Typography>
            </Box>
          )}
        </Box>
        <Box
          sx={{
            backgroundColor: `${color}.light`,
            borderRadius: 2,
            p: 1,
            color: `${color}.main`,
          }}
        >
          {icon}
        </Box>
      </Box>
    </CardContent>
  </Card>
);

interface RevenueOverviewProps {
  modelId?: string;
  agencyId?: string;
}

export const RevenueOverview = ({ modelId, agencyId }: RevenueOverviewProps) => {
  const [period, setPeriod] = useState<Revenue['period']>('monthly');

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['financial-summary', modelId, agencyId],
    queryFn: () => financialApi.getFinancialSummary({ model_id: modelId, agency_id: agencyId }),
  });

  const { data: currentRevenue, isLoading: revenueLoading } = useQuery({
    queryKey: ['revenue', period, modelId, agencyId],
    queryFn: () => financialApi.getRevenue({ period, model_id: modelId, agency_id: agencyId }),
  });

  const { data: revenueHistory, isLoading: historyLoading } = useQuery({
    queryKey: ['revenue-history', period, modelId, agencyId],
    queryFn: () => financialApi.getRevenueHistory({ 
      period, 
      count: 12, 
      model_id: modelId, 
      agency_id: agencyId 
    }),
  });

  const handlePeriodChange = (_: React.MouseEvent<HTMLElement>, newPeriod: Revenue['period'] | null) => {
    if (newPeriod) {
      setPeriod(newPeriod);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: summary?.data?.currency || 'USD',
    }).format(amount);
  };

  const formatChartData = () => {
    if (!revenueHistory?.data) return [];
    
    return revenueHistory.data.map((rev) => ({
      period: new Date(rev.start_date).toLocaleDateString('en-US', {
        month: 'short',
        day: period === 'daily' ? 'numeric' : undefined,
        year: period === 'yearly' ? 'numeric' : undefined,
      }),
      gross: rev.gross_revenue,
      net: rev.net_revenue,
      commission: rev.commission,
    }));
  };

  const formatBreakdownData = () => {
    if (!currentRevenue?.data?.breakdown) return [];
    
    return currentRevenue.data.breakdown.map((item) => ({
      name: item.source.charAt(0).toUpperCase() + item.source.slice(1).replace('_', ' '),
      value: item.amount,
      percentage: item.percentage,
    }));
  };

  if (summaryLoading || revenueLoading || historyLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight={400}>
        <CircularProgress />
      </Box>
    );
  }

  if (!summary?.data || !currentRevenue?.data) {
    return (
      <Alert severity="error">Failed to load financial data</Alert>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5">Revenue Overview</Typography>
        <ToggleButtonGroup
          value={period}
          exclusive
          onChange={handlePeriodChange}
          size="small"
        >
          <ToggleButton value="daily">Daily</ToggleButton>
          <ToggleButton value="weekly">Weekly</ToggleButton>
          <ToggleButton value="monthly">Monthly</ToggleButton>
          <ToggleButton value="yearly">Yearly</ToggleButton>
        </ToggleButtonGroup>
      </Box>

      <Grid container spacing={3}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total Revenue"
            value={formatCurrency(summary.data.total_revenue)}
            icon={<AttachMoney />}
            color="primary"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Available Balance"
            value={formatCurrency(summary.data.available_balance)}
            icon={<AccountBalance />}
            color="success"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total Payouts"
            value={formatCurrency(summary.data.total_payouts)}
            icon={<Receipt />}
            color="info"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Pending Payouts"
            value={formatCurrency(summary.data.pending_payouts)}
            icon={<Receipt />}
            color="warning"
          />
        </Grid>

        <Grid item xs={12} lg={8}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Revenue Trend
              </Typography>
              <Box height={300}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={formatChartData()}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="period" />
                    <YAxis />
                    <Tooltip formatter={(value: number) => formatCurrency(value)} />
                    <Legend />
                    <Area
                      type="monotone"
                      dataKey="gross"
                      stackId="1"
                      stroke="#8884d8"
                      fill="#8884d8"
                      name="Gross Revenue"
                    />
                    <Area
                      type="monotone"
                      dataKey="commission"
                      stackId="1"
                      stroke="#ffc658"
                      fill="#ffc658"
                      name="Commission"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} lg={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Revenue Breakdown
              </Typography>
              <Box height={300}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={formatBreakdownData()} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis type="category" dataKey="name" />
                    <Tooltip formatter={(value: number) => formatCurrency(value)} />
                    <Bar dataKey="value" fill="#82ca9d" />
                  </BarChart>
                </ResponsiveContainer>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Current Period Summary
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={4}>
                  <Typography variant="body2" color="textSecondary">
                    Gross Revenue
                  </Typography>
                  <Typography variant="h6">
                    {formatCurrency(currentRevenue.data.gross_revenue)}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={4}>
                  <Typography variant="body2" color="textSecondary">
                    Commission
                  </Typography>
                  <Typography variant="h6">
                    {formatCurrency(currentRevenue.data.commission)}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={4}>
                  <Typography variant="body2" color="textSecondary">
                    Net Revenue
                  </Typography>
                  <Typography variant="h6">
                    {formatCurrency(currentRevenue.data.net_revenue)}
                  </Typography>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};