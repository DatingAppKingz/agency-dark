import { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Grid,
  TextField,
  MenuItem,
  Button,
  Tab,
  Tabs,
  CircularProgress,
  Alert,
  IconButton,
  Divider,
  Paper,
  Chip,
} from '@mui/material';
import {
  Download,
  TrendingUp,
  TrendingDown,
  Assessment,
  CalendarToday,
  Print,
  Email,
  Schedule,
  FilterList,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { useQuery } from '@tanstack/react-query';
import { format, startOfMonth, endOfMonth, subMonths } from 'date-fns';
import { financialApi } from '@/services/api/financial';
import { useToast } from '@/components/common/Toaster';

interface FinancialReportsProps {
  modelId?: string;
  agencyId?: string;
}

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
      id={`financial-report-tabpanel-${index}`}
      aria-labelledby={`financial-report-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
};

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

export const FinancialReports = ({ modelId, agencyId }: FinancialReportsProps) => {
  const { error, success } = useToast();
  const [tab, setTab] = useState(0);
  const [reportType, setReportType] = useState<'monthly' | 'quarterly' | 'yearly'>('monthly');
  const [startDate, setStartDate] = useState<Date | null>(startOfMonth(subMonths(new Date(), 11)));
  const [endDate, setEndDate] = useState<Date | null>(endOfMonth(new Date()));
  const [isGenerating, setIsGenerating] = useState(false);

  // Mock data - replace with actual API calls
  const { data: summaryData, isLoading: isSummaryLoading } = useQuery({
    queryKey: ['financial-summary', startDate, endDate, modelId, agencyId],
    queryFn: async () => {
      // Mock data
      return {
        total_revenue: 125000,
        total_expenses: 45000,
        net_profit: 80000,
        growth_rate: 15.5,
        top_revenue_sources: [
          { source: 'Subscriptions', amount: 75000, percentage: 60 },
          { source: 'Tips', amount: 30000, percentage: 24 },
          { source: 'PPV Content', amount: 15000, percentage: 12 },
          { source: 'Custom Requests', amount: 5000, percentage: 4 },
        ],
        monthly_trends: [
          { month: 'Jan', revenue: 8000, expenses: 3000, profit: 5000 },
          { month: 'Feb', revenue: 9500, expenses: 3500, profit: 6000 },
          { month: 'Mar', revenue: 10000, expenses: 3800, profit: 6200 },
          { month: 'Apr', revenue: 11000, expenses: 4000, profit: 7000 },
          { month: 'May', revenue: 10500, expenses: 3900, profit: 6600 },
          { month: 'Jun', revenue: 12000, expenses: 4200, profit: 7800 },
          { month: 'Jul', revenue: 13500, expenses: 4500, profit: 9000 },
          { month: 'Aug', revenue: 14000, expenses: 4800, profit: 9200 },
          { month: 'Sep', revenue: 12500, expenses: 4300, profit: 8200 },
          { month: 'Oct', revenue: 11500, expenses: 4000, profit: 7500 },
          { month: 'Nov', revenue: 13000, expenses: 4500, profit: 8500 },
          { month: 'Dec', revenue: 15000, expenses: 5000, profit: 10000 },
        ],
        model_performance: [
          { model: 'Model A', revenue: 35000, growth: 25 },
          { model: 'Model B', revenue: 28000, growth: 18 },
          { model: 'Model C', revenue: 22000, growth: -5 },
          { model: 'Model D', revenue: 20000, growth: 10 },
          { model: 'Model E', revenue: 20000, growth: 30 },
        ],
      };
    },
  });

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const handleExportReport = async (format: 'pdf' | 'csv' | 'xlsx') => {
    try {
      setIsGenerating(true);
      // TODO: Implement export functionality
      success(`Report exported as ${format.toUpperCase()}`);
    } catch (err) {
      error('Failed to export report');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleScheduleReport = () => {
    // TODO: Implement scheduled reports
    success('Report scheduling coming soon');
  };

  const SummaryCards = () => (
    <Grid container spacing={3} sx={{ mb: 3 }}>
      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Box display="flex" justifyContent="space-between" alignItems="start">
              <Box>
                <Typography color="textSecondary" gutterBottom>
                  Total Revenue
                </Typography>
                <Typography variant="h4">
                  {formatCurrency(summaryData?.total_revenue || 0)}
                </Typography>
                <Box display="flex" alignItems="center" mt={1}>
                  <TrendingUp color="success" sx={{ mr: 0.5 }} />
                  <Typography variant="body2" color="success.main">
                    +{summaryData?.growth_rate || 0}%
                  </Typography>
                </Box>
              </Box>
              <Assessment color="primary" />
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
                  Total Expenses
                </Typography>
                <Typography variant="h4">
                  {formatCurrency(summaryData?.total_expenses || 0)}
                </Typography>
                <Box display="flex" alignItems="center" mt={1}>
                  <TrendingDown color="error" sx={{ mr: 0.5 }} />
                  <Typography variant="body2" color="error.main">
                    -8.5%
                  </Typography>
                </Box>
              </Box>
              <Assessment color="error" />
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
                  Net Profit
                </Typography>
                <Typography variant="h4">
                  {formatCurrency(summaryData?.net_profit || 0)}
                </Typography>
                <Box display="flex" alignItems="center" mt={1}>
                  <TrendingUp color="success" sx={{ mr: 0.5 }} />
                  <Typography variant="body2" color="success.main">
                    +22.3%
                  </Typography>
                </Box>
              </Box>
              <Assessment color="success" />
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
                  Profit Margin
                </Typography>
                <Typography variant="h4">
                  {summaryData ? ((summaryData.net_profit / summaryData.total_revenue) * 100).toFixed(1) : 0}%
                </Typography>
                <Box display="flex" alignItems="center" mt={1}>
                  <TrendingUp color="success" sx={{ mr: 0.5 }} />
                  <Typography variant="body2" color="success.main">
                    +3.2%
                  </Typography>
                </Box>
              </Box>
              <Assessment color="warning" />
            </Box>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );

  const RevenueBreakdown = () => (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Revenue Breakdown
        </Typography>
        <Box sx={{ height: 400 }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={summaryData?.top_revenue_sources || []}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percentage }) => `${name} (${percentage}%)`}
                outerRadius={120}
                fill="#8884d8"
                dataKey="amount"
              >
                {summaryData?.top_revenue_sources.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(value) => formatCurrency(Number(value))} />
            </PieChart>
          </ResponsiveContainer>
        </Box>
      </CardContent>
    </Card>
  );

  const TrendAnalysis = () => (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Financial Trends
        </Typography>
        <Box sx={{ height: 400 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={summaryData?.monthly_trends || []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis />
              <Tooltip formatter={(value) => formatCurrency(Number(value))} />
              <Legend />
              <Area
                type="monotone"
                dataKey="revenue"
                stackId="1"
                stroke="#0088FE"
                fill="#0088FE"
                name="Revenue"
              />
              <Area
                type="monotone"
                dataKey="expenses"
                stackId="1"
                stroke="#FF8042"
                fill="#FF8042"
                name="Expenses"
              />
            </AreaChart>
          </ResponsiveContainer>
        </Box>
      </CardContent>
    </Card>
  );

  const ProfitAnalysis = () => (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Profit Analysis
        </Typography>
        <Box sx={{ height: 400 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={summaryData?.monthly_trends || []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis />
              <Tooltip formatter={(value) => formatCurrency(Number(value))} />
              <Legend />
              <Line
                type="monotone"
                dataKey="profit"
                stroke="#00C49F"
                strokeWidth={3}
                name="Net Profit"
              />
            </LineChart>
          </ResponsiveContainer>
        </Box>
      </CardContent>
    </Card>
  );

  const ModelPerformance = () => (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Model Performance
        </Typography>
        <Box sx={{ height: 400 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={summaryData?.model_performance || []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="model" />
              <YAxis yAxisId="left" orientation="left" stroke="#8884d8" />
              <YAxis yAxisId="right" orientation="right" stroke="#82ca9d" />
              <Tooltip />
              <Legend />
              <Bar yAxisId="left" dataKey="revenue" fill="#8884d8" name="Revenue ($)" />
              <Bar yAxisId="right" dataKey="growth" fill="#82ca9d" name="Growth (%)" />
            </BarChart>
          </ResponsiveContainer>
        </Box>
      </CardContent>
    </Card>
  );

  if (isSummaryLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight={400}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5">Financial Reports</Typography>
        <Box display="flex" gap={2}>
          <Button
            variant="outlined"
            startIcon={<Schedule />}
            onClick={handleScheduleReport}
          >
            Schedule Reports
          </Button>
          <Button
            variant="contained"
            startIcon={<Download />}
            onClick={() => handleExportReport('pdf')}
            disabled={isGenerating}
          >
            Export Report
          </Button>
        </Box>
      </Box>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box display="flex" gap={2} alignItems="center" flexWrap="wrap">
          <TextField
            select
            label="Report Type"
            value={reportType}
            onChange={(e) => setReportType(e.target.value as 'monthly' | 'quarterly' | 'yearly')}
            size="small"
            sx={{ minWidth: 150 }}
          >
            <MenuItem value="monthly">Monthly</MenuItem>
            <MenuItem value="quarterly">Quarterly</MenuItem>
            <MenuItem value="yearly">Yearly</MenuItem>
          </TextField>

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

          <Button
            variant="outlined"
            startIcon={<FilterList />}
            size="small"
          >
            More Filters
          </Button>
        </Box>
      </Paper>

      {/* Summary Cards */}
      <SummaryCards />

      {/* Report Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs
          value={tab}
          onChange={(_, newValue) => setTab(newValue)}
          variant="scrollable"
          scrollButtons="auto"
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab label="Overview" />
          <Tab label="Revenue Analysis" />
          <Tab label="Expense Analysis" />
          <Tab label="Model Performance" />
          <Tab label="Comparative Analysis" />
        </Tabs>
      </Paper>

      <TabPanel value={tab} index={0}>
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <RevenueBreakdown />
          </Grid>
          <Grid item xs={12} md={6}>
            <TrendAnalysis />
          </Grid>
          <Grid item xs={12}>
            <ProfitAnalysis />
          </Grid>
        </Grid>
      </TabPanel>

      <TabPanel value={tab} index={1}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <TrendAnalysis />
          </Grid>
          <Grid item xs={12} md={6}>
            <RevenueBreakdown />
          </Grid>
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Revenue Growth Rate
                </Typography>
                <Box sx={{ height: 300 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={summaryData?.monthly_trends || []}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="month" />
                      <YAxis />
                      <Tooltip />
                      <Line
                        type="monotone"
                        dataKey="revenue"
                        stroke="#8884d8"
                        strokeWidth={2}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>

      <TabPanel value={tab} index={2}>
        <Alert severity="info" sx={{ mb: 2 }}>
          Expense analysis helps identify cost-saving opportunities and optimize spending.
        </Alert>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Expense Categories
                </Typography>
                <Box sx={{ height: 400 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={[
                          { name: 'Platform Fees', value: 15000 },
                          { name: 'Marketing', value: 10000 },
                          { name: 'Content Creation', value: 8000 },
                          { name: 'Staff Salaries', value: 7000 },
                          { name: 'Other', value: 5000 },
                        ]}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={({ name, value }) => `${name}: ${formatCurrency(value)}`}
                        outerRadius={120}
                        fill="#8884d8"
                        dataKey="value"
                      >
                        {[0, 1, 2, 3, 4].map((index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value) => formatCurrency(Number(value))} />
                    </PieChart>
                  </ResponsiveContainer>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>

      <TabPanel value={tab} index={3}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <ModelPerformance />
          </Grid>
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Top Performing Models
                </Typography>
                <Box sx={{ mt: 2 }}>
                  {summaryData?.model_performance.map((model, index) => (
                    <Box key={index} sx={{ mb: 2 }}>
                      <Box display="flex" justifyContent="space-between" alignItems="center">
                        <Typography variant="subtitle1">{model.model}</Typography>
                        <Box display="flex" alignItems="center" gap={2}>
                          <Typography variant="body2">
                            {formatCurrency(model.revenue)}
                          </Typography>
                          <Chip
                            label={`${model.growth > 0 ? '+' : ''}${model.growth}%`}
                            color={model.growth > 0 ? 'success' : 'error'}
                            size="small"
                          />
                        </Box>
                      </Box>
                      <Box sx={{ width: '100%', mt: 1 }}>
                        <Box
                          sx={{
                            height: 8,
                            backgroundColor: 'divider',
                            borderRadius: 1,
                            overflow: 'hidden',
                          }}
                        >
                          <Box
                            sx={{
                              width: `${(model.revenue / 35000) * 100}%`,
                              height: '100%',
                              backgroundColor: 'primary.main',
                            }}
                          />
                        </Box>
                      </Box>
                    </Box>
                  ))}
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>

      <TabPanel value={tab} index={4}>
        <Alert severity="info" sx={{ mb: 2 }}>
          Compare performance across different time periods to identify trends and patterns.
        </Alert>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Year-over-Year Comparison
                </Typography>
                <Box sx={{ height: 400 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={[
                        { month: 'Jan', thisYear: 15000, lastYear: 12000 },
                        { month: 'Feb', thisYear: 18000, lastYear: 14000 },
                        { month: 'Mar', thisYear: 20000, lastYear: 16000 },
                        { month: 'Apr', thisYear: 22000, lastYear: 18000 },
                        { month: 'May', thisYear: 21000, lastYear: 17000 },
                        { month: 'Jun', thisYear: 24000, lastYear: 19000 },
                      ]}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="month" />
                      <YAxis />
                      <Tooltip formatter={(value) => formatCurrency(Number(value))} />
                      <Legend />
                      <Bar dataKey="lastYear" fill="#8884d8" name="Last Year" />
                      <Bar dataKey="thisYear" fill="#82ca9d" name="This Year" />
                    </BarChart>
                  </ResponsiveContainer>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>
    </Box>
  );
};