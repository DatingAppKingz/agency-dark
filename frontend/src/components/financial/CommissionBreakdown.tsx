import { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Button,
  TextField,
  MenuItem,
  Paper,
  Avatar,
  LinearProgress,
  Tooltip,
  IconButton,
  Divider,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  Download,
  Person,
  CalendarToday,
  AttachMoney,
  Assessment,
  Info,
  FilterList,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { PieChart, Pie, Cell, BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend, ResponsiveContainer } from 'recharts';
import { useQuery } from '@tanstack/react-query';
import { format, startOfMonth, endOfMonth } from 'date-fns';
import { useToast } from '@/components/common/Toaster';

interface CommissionBreakdownProps {
  agencyId?: string;
}

interface ModelCommission {
  model_id: string;
  model_name: string;
  model_avatar?: string;
  gross_earnings: number;
  commission_rate: number;
  commission_amount: number;
  net_earnings: number;
  transactions: number;
  status: 'active' | 'pending' | 'paid';
  performance_change: number;
}

interface CommissionSummary {
  total_gross_earnings: number;
  total_commissions: number;
  total_net_earnings: number;
  average_commission_rate: number;
  total_models: number;
  total_transactions: number;
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

export const CommissionBreakdown = ({ agencyId }: CommissionBreakdownProps) => {
  const { error, success } = useToast();
  const [startDate, setStartDate] = useState<Date | null>(startOfMonth(new Date()));
  const [endDate, setEndDate] = useState<Date | null>(endOfMonth(new Date()));
  const [filterStatus, setFilterStatus] = useState<'all' | 'active' | 'pending' | 'paid'>('all');
  const [sortBy, setSortBy] = useState<'earnings' | 'commission' | 'name'>('earnings');
  const [isExporting, setIsExporting] = useState(false);

  // Mock data - replace with actual API calls
  const { data: commissionData, isLoading } = useQuery({
    queryKey: ['commission-breakdown', startDate, endDate, filterStatus, agencyId],
    queryFn: async () => {
      // Mock data
      const models: ModelCommission[] = [
        {
          model_id: '1',
          model_name: 'Sarah Johnson',
          model_avatar: 'S',
          gross_earnings: 25000,
          commission_rate: 20,
          commission_amount: 5000,
          net_earnings: 20000,
          transactions: 450,
          status: 'paid',
          performance_change: 15.5,
        },
        {
          model_id: '2',
          model_name: 'Emily Davis',
          model_avatar: 'E',
          gross_earnings: 18000,
          commission_rate: 25,
          commission_amount: 4500,
          net_earnings: 13500,
          transactions: 320,
          status: 'active',
          performance_change: -5.2,
        },
        {
          model_id: '3',
          model_name: 'Jessica Martinez',
          model_avatar: 'J',
          gross_earnings: 22000,
          commission_rate: 15,
          commission_amount: 3300,
          net_earnings: 18700,
          transactions: 380,
          status: 'active',
          performance_change: 22.8,
        },
        {
          model_id: '4',
          model_name: 'Ashley Thompson',
          model_avatar: 'A',
          gross_earnings: 15000,
          commission_rate: 20,
          commission_amount: 3000,
          net_earnings: 12000,
          transactions: 280,
          status: 'pending',
          performance_change: 8.3,
        },
        {
          model_id: '5',
          model_name: 'Megan Wilson',
          model_avatar: 'M',
          gross_earnings: 12000,
          commission_rate: 30,
          commission_amount: 3600,
          net_earnings: 8400,
          transactions: 220,
          status: 'active',
          performance_change: -12.5,
        },
      ];

      const summary: CommissionSummary = {
        total_gross_earnings: models.reduce((sum, m) => sum + m.gross_earnings, 0),
        total_commissions: models.reduce((sum, m) => sum + m.commission_amount, 0),
        total_net_earnings: models.reduce((sum, m) => sum + m.net_earnings, 0),
        average_commission_rate: models.reduce((sum, m) => sum + m.commission_rate, 0) / models.length,
        total_models: models.length,
        total_transactions: models.reduce((sum, m) => sum + m.transactions, 0),
      };

      return { models, summary };
    },
  });

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const getStatusColor = (status: ModelCommission['status']) => {
    switch (status) {
      case 'paid':
        return 'success';
      case 'active':
        return 'primary';
      case 'pending':
        return 'warning';
      default:
        return 'default';
    }
  };

  const handleExport = async (format: 'csv' | 'pdf') => {
    try {
      setIsExporting(true);
      // TODO: Implement export
      await new Promise(resolve => setTimeout(resolve, 2000));
      success(`Commission report exported as ${format.toUpperCase()}`);
    } catch (err) {
      error('Failed to export report');
    } finally {
      setIsExporting(false);
    }
  };

  const filteredModels = commissionData?.models.filter(model => 
    filterStatus === 'all' || model.status === filterStatus
  ).sort((a, b) => {
    switch (sortBy) {
      case 'earnings':
        return b.gross_earnings - a.gross_earnings;
      case 'commission':
        return b.commission_amount - a.commission_amount;
      case 'name':
        return a.model_name.localeCompare(b.model_name);
      default:
        return 0;
    }
  });

  const pieChartData = filteredModels?.map(model => ({
    name: model.model_name,
    value: model.commission_amount,
  }));

  const SummaryCards = () => (
    <Grid container spacing={3} sx={{ mb: 3 }}>
      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Box display="flex" justifyContent="space-between" alignItems="start">
              <Box>
                <Typography color="textSecondary" gutterBottom>
                  Total Gross Earnings
                </Typography>
                <Typography variant="h5">
                  {formatCurrency(commissionData?.summary.total_gross_earnings || 0)}
                </Typography>
              </Box>
              <TrendingUp color="success" />
            </Box>
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Box display="flex" justifyContent="space-between" alignItems="start">
              <Box>
                <Typography color="textSecondary" gutterBottom>
                  Total Commissions
                </Typography>
                <Typography variant="h5">
                  {formatCurrency(commissionData?.summary.total_commissions || 0)}
                </Typography>
              </Box>
              <AttachMoney color="primary" />
            </Box>
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Box display="flex" justifyContent="space-between" alignItems="start">
              <Box>
                <Typography color="textSecondary" gutterBottom>
                  Average Commission
                </Typography>
                <Typography variant="h5">
                  {commissionData?.summary.average_commission_rate.toFixed(1)}%
                </Typography>
              </Box>
              <Assessment color="warning" />
            </Box>
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Box display="flex" justifyContent="space-between" alignItems="start">
              <Box>
                <Typography color="textSecondary" gutterBottom>
                  Active Models
                </Typography>
                <Typography variant="h5">
                  {commissionData?.summary.total_models || 0}
                </Typography>
              </Box>
              <Person color="info" />
            </Box>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5">Commission Breakdown</Typography>
        <Box display="flex" gap={2}>
          <Button
            variant="outlined"
            startIcon={<Download />}
            onClick={() => handleExport('csv')}
            disabled={isExporting}
          >
            Export CSV
          </Button>
          <Button
            variant="contained"
            startIcon={<Download />}
            onClick={() => handleExport('pdf')}
            disabled={isExporting}
          >
            Export PDF
          </Button>
        </Box>
      </Box>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box display="flex" gap={2} alignItems="center" flexWrap="wrap">
          <LocalizationProvider dateAdapter={AdapterDateFns}>
            <DatePicker
              label="Start Date"
              value={startDate}
              onChange={setStartDate}
              slotProps={{
                textField: { size: 'small' }
              }}
            />
            <DatePicker
              label="End Date"
              value={endDate}
              onChange={setEndDate}
              slotProps={{
                textField: { size: 'small' }
              }}
            />
          </LocalizationProvider>

          <TextField
            select
            label="Status"
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value as any)}
            size="small"
            sx={{ minWidth: 120 }}
          >
            <MenuItem value="all">All</MenuItem>
            <MenuItem value="active">Active</MenuItem>
            <MenuItem value="pending">Pending</MenuItem>
            <MenuItem value="paid">Paid</MenuItem>
          </TextField>

          <TextField
            select
            label="Sort By"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            size="small"
            sx={{ minWidth: 120 }}
          >
            <MenuItem value="earnings">Gross Earnings</MenuItem>
            <MenuItem value="commission">Commission Amount</MenuItem>
            <MenuItem value="name">Model Name</MenuItem>
          </TextField>
        </Box>
      </Paper>

      <SummaryCards />

      <Grid container spacing={3}>
        {/* Commission Distribution Chart */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Commission Distribution
              </Typography>
              <Box sx={{ height: 300 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieChartData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, percent }) => `${name.split(' ')[0]} (${(percent * 100).toFixed(0)}%)`}
                      outerRadius={100}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {pieChartData?.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <RechartsTooltip formatter={(value) => formatCurrency(Number(value))} />
                  </PieChart>
                </ResponsiveContainer>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Performance Chart */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Model Performance
              </Typography>
              <Box sx={{ height: 300 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={filteredModels}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="model_name" angle={-45} textAnchor="end" height={80} />
                    <YAxis />
                    <RechartsTooltip formatter={(value) => formatCurrency(Number(value))} />
                    <Legend />
                    <Bar dataKey="gross_earnings" fill="#8884d8" name="Gross Earnings" />
                    <Bar dataKey="commission_amount" fill="#82ca9d" name="Commission" />
                  </BarChart>
                </ResponsiveContainer>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Detailed Table */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Detailed Commission Report
              </Typography>

              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Model</TableCell>
                      <TableCell align="right">Gross Earnings</TableCell>
                      <TableCell align="center">Commission Rate</TableCell>
                      <TableCell align="right">Commission Amount</TableCell>
                      <TableCell align="right">Net Earnings</TableCell>
                      <TableCell align="center">Transactions</TableCell>
                      <TableCell align="center">Performance</TableCell>
                      <TableCell align="center">Status</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {isLoading ? (
                      <TableRow>
                        <TableCell colSpan={8} align="center">
                          <LinearProgress />
                        </TableCell>
                      </TableRow>
                    ) : filteredModels?.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={8} align="center">
                          <Typography variant="body2" color="textSecondary">
                            No commission data found
                          </Typography>
                        </TableCell>
                      </TableRow>
                    ) : (
                      filteredModels?.map((model) => (
                        <TableRow key={model.model_id}>
                          <TableCell>
                            <Box display="flex" alignItems="center" gap={1}>
                              <Avatar sx={{ width: 32, height: 32 }}>
                                {model.model_avatar}
                              </Avatar>
                              <Typography variant="body2">
                                {model.model_name}
                              </Typography>
                            </Box>
                          </TableCell>
                          <TableCell align="right">
                            <Typography variant="body2" fontWeight="medium">
                              {formatCurrency(model.gross_earnings)}
                            </Typography>
                          </TableCell>
                          <TableCell align="center">
                            <Chip
                              label={`${model.commission_rate}%`}
                              size="small"
                              variant="outlined"
                            />
                          </TableCell>
                          <TableCell align="right">
                            <Typography variant="body2" color="primary.main" fontWeight="medium">
                              {formatCurrency(model.commission_amount)}
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            {formatCurrency(model.net_earnings)}
                          </TableCell>
                          <TableCell align="center">
                            {model.transactions}
                          </TableCell>
                          <TableCell align="center">
                            <Box display="flex" alignItems="center" justifyContent="center" gap={0.5}>
                              {model.performance_change > 0 ? (
                                <TrendingUp color="success" fontSize="small" />
                              ) : (
                                <TrendingDown color="error" fontSize="small" />
                              )}
                              <Typography
                                variant="body2"
                                color={model.performance_change > 0 ? 'success.main' : 'error.main'}
                              >
                                {model.performance_change > 0 ? '+' : ''}{model.performance_change}%
                              </Typography>
                            </Box>
                          </TableCell>
                          <TableCell align="center">
                            <Chip
                              label={model.status.toUpperCase()}
                              color={getStatusColor(model.status)}
                              size="small"
                            />
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* Commission Tiers Info */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1} mb={2}>
                <Info color="info" />
                <Typography variant="h6">Commission Structure</Typography>
              </Box>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6} md={3}>
                  <Paper variant="outlined" sx={{ p: 2 }}>
                    <Typography variant="subtitle2" color="textSecondary">
                      Standard Rate
                    </Typography>
                    <Typography variant="h6">20%</Typography>
                    <Typography variant="body2" color="textSecondary">
                      Default commission rate
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Paper variant="outlined" sx={{ p: 2 }}>
                    <Typography variant="subtitle2" color="textSecondary">
                      Premium Rate
                    </Typography>
                    <Typography variant="h6">15%</Typography>
                    <Typography variant="body2" color="textSecondary">
                      For top performers
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Paper variant="outlined" sx={{ p: 2 }}>
                    <Typography variant="subtitle2" color="textSecondary">
                      New Model Rate
                    </Typography>
                    <Typography variant="h6">25%</Typography>
                    <Typography variant="body2" color="textSecondary">
                      First 3 months
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Paper variant="outlined" sx={{ p: 2 }}>
                    <Typography variant="subtitle2" color="textSecondary">
                      VIP Rate
                    </Typography>
                    <Typography variant="h6">10%</Typography>
                    <Typography variant="body2" color="textSecondary">
                      Exclusive partners
                    </Typography>
                  </Paper>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};