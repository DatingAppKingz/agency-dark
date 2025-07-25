import { useState, useMemo } from 'react';
import {
  Box,
  Grid,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Button,
  TextField,
  InputAdornment,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { Download, Search, TrendingUp, TrendingDown } from '@mui/icons-material';
import { ChartWidget } from '@/components/dashboard/ChartWidget';
import { format, subDays } from 'date-fns';

interface ModelEarningsProps {
  modelId: string;
}

export const ModelEarnings = ({ modelId }: ModelEarningsProps) => {
  const [startDate, setStartDate] = useState<Date | null>(subDays(new Date(), 30));
  const [endDate, setEndDate] = useState<Date | null>(new Date());
  const [searchTerm, setSearchTerm] = useState('');
  const [chartPeriod, setChartPeriod] = useState<'daily' | 'weekly' | 'monthly'>('daily');

  // Mock earnings data - replace with real API data
  const earnings = [
    {
      id: '1',
      date: '2025-01-24',
      type: 'subscription',
      description: 'Monthly subscription - John D.',
      amount: 9.99,
      status: 'completed',
    },
    {
      id: '2',
      date: '2025-01-24',
      type: 'tip',
      description: 'Tip from Mike R.',
      amount: 50.00,
      status: 'completed',
    },
    {
      id: '3',
      date: '2025-01-23',
      type: 'content',
      description: 'Photo set purchase - Sarah M.',
      amount: 15.00,
      status: 'completed',
    },
    {
      id: '4',
      date: '2025-01-23',
      type: 'message',
      description: 'Paid message - Emma L.',
      amount: 5.00,
      status: 'pending',
    },
  ];

  const summary = {
    totalEarnings: 1542.50,
    subscriptions: 899.10,
    tips: 450.00,
    content: 150.00,
    messages: 43.40,
    pendingPayout: 327.80,
  };

  // Mock revenue chart data
  const revenueChartData = useMemo(() => {
    const days = chartPeriod === 'daily' ? 30 : chartPeriod === 'weekly' ? 12 : 12;
    return Array.from({ length: days }, (_, i) => {
      const date = subDays(new Date(), days - i - 1);
      const baseValue = 50 + Math.random() * 100;
      return {
        label: format(date, chartPeriod === 'daily' ? 'MMM d' : chartPeriod === 'weekly' ? 'MMM d' : 'MMM'),
        subscriptions: baseValue * 0.6,
        tips: baseValue * 0.25,
        content: baseValue * 0.1,
        messages: baseValue * 0.05,
        total: baseValue,
      };
    });
  }, [chartPeriod]);

  // Mock earnings breakdown pie chart data
  const earningsBreakdownData = [
    { label: 'Subscriptions', value: summary.subscriptions },
    { label: 'Tips', value: summary.tips },
    { label: 'Content', value: summary.content },
    { label: 'Messages', value: summary.messages },
  ];

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'subscription':
        return 'primary';
      case 'tip':
        return 'success';
      case 'content':
        return 'warning';
      case 'message':
        return 'info';
      default:
        return 'default';
    }
  };

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box sx={{ p: 3 }}>
        {/* Summary Cards */}
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} sm={6} md={4}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle2" color="text.secondary">
                Total Earnings
              </Typography>
              <Typography variant="h4" sx={{ my: 1 }}>
                ${summary.totalEarnings.toFixed(2)}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <TrendingUp color="success" fontSize="small" />
                <Typography variant="body2" color="success.main">
                  +12.5% from last month
                </Typography>
              </Box>
            </Paper>
          </Grid>
          <Grid item xs={12} sm={6} md={4}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle2" color="text.secondary">
                Pending Payout
              </Typography>
              <Typography variant="h4" sx={{ my: 1 }}>
                ${summary.pendingPayout.toFixed(2)}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Next payout in 3 days
              </Typography>
            </Paper>
          </Grid>
          <Grid item xs={12} sm={12} md={4}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Earnings Breakdown
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2">Subscriptions</Typography>
                  <Typography variant="body2">${summary.subscriptions}</Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2">Tips</Typography>
                  <Typography variant="body2">${summary.tips}</Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2">Content</Typography>
                  <Typography variant="body2">${summary.content}</Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2">Messages</Typography>
                  <Typography variant="body2">${summary.messages}</Typography>
                </Box>
              </Box>
            </Paper>
          </Grid>
        </Grid>

        {/* Revenue Charts */}
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid item xs={12} lg={8}>
            <Paper>
              <Box sx={{ p: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                  <Typography variant="h6">Revenue Trend</Typography>
                  <ToggleButtonGroup
                    value={chartPeriod}
                    exclusive
                    onChange={(_, newPeriod) => newPeriod && setChartPeriod(newPeriod)}
                    size="small"
                  >
                    <ToggleButton value="daily">Daily</ToggleButton>
                    <ToggleButton value="weekly">Weekly</ToggleButton>
                    <ToggleButton value="monthly">Monthly</ToggleButton>
                  </ToggleButtonGroup>
                </Box>
                <ChartWidget
                  title=""
                  data={revenueChartData}
                  type="area"
                  height={300}
                  dataKey="total"
                  valueFormatter={(value) => `$${value.toFixed(2)}`}
                />
              </Box>
            </Paper>
          </Grid>
          <Grid item xs={12} lg={4}>
            <Paper>
              <Box sx={{ p: 2 }}>
                <Typography variant="h6" gutterBottom>Earnings Breakdown</Typography>
                <ChartWidget
                  title=""
                  data={earningsBreakdownData}
                  type="pie"
                  height={300}
                  valueFormatter={(value) => `$${value.toFixed(2)}`}
                />
              </Box>
            </Paper>
          </Grid>
        </Grid>

        {/* Filters */}
        <Paper sx={{ p: 2, mb: 3 }}>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} sm={6} md={3}>
              <DatePicker
                label="Start Date"
                value={startDate}
                onChange={setStartDate}
                slotProps={{ textField: { fullWidth: true } }}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <DatePicker
                label="End Date"
                value={endDate}
                onChange={setEndDate}
                slotProps={{ textField: { fullWidth: true } }}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <TextField
                fullWidth
                placeholder="Search transactions..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <Search />
                    </InputAdornment>
                  ),
                }}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={2}>
              <Button
                fullWidth
                variant="outlined"
                startIcon={<Download />}
              >
                Export
              </Button>
            </Grid>
          </Grid>
        </Paper>

        {/* Transactions Table */}
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Date</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Description</TableCell>
                <TableCell align="right">Amount</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {earnings.map((transaction) => (
                <TableRow key={transaction.id}>
                  <TableCell>{transaction.date}</TableCell>
                  <TableCell>
                    <Chip
                      label={transaction.type}
                      size="small"
                      color={getTypeColor(transaction.type)}
                    />
                  </TableCell>
                  <TableCell>{transaction.description}</TableCell>
                  <TableCell align="right">
                    ${transaction.amount.toFixed(2)}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={transaction.status}
                      size="small"
                      color={transaction.status === 'completed' ? 'success' : 'warning'}
                      variant="outlined"
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    </LocalizationProvider>
  );
};