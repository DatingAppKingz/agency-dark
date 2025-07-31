import { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Grid,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
  TextField,
  MenuItem,
  Paper,
  Divider,
  LinearProgress } from '@mui/material';
import {
  Download,
  Email,
  Print,
  Receipt,
  Visibility } from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { useQuery } from '@tanstack/react-query';
import { format, startOfMonth, endOfMonth, subMonths } from 'date-fns';
import { useToast } from '@/components/common/Toaster';

import { useReactToPrint } from 'react-to-print';
import { useRef } from 'react';

interface EarningsStatementsProps {
  modelId?: string;
  agencyId?: string;
}

interface EarningsStatement {
  id: string;
  period: string;
  start_date: string;
  end_date: string;
  gross_earnings: number;
  deductions: {
    platform_fees: number;
    payment_processing: number;
    chargebacks: number;
    other: number;
  };
  net_earnings: number;
  status: 'draft' | 'final' | 'paid';
  generated_at: string;
  paid_at?: string;
}

interface EarningsBreakdown {
  subscriptions: number;
  tips: number;
  ppv_content: number;
  custom_requests: number;
  referrals: number;
  other: number;
}

export const EarningsStatements = ({ modelId, agencyId }: EarningsStatementsProps) => {
  const { error, success } = useToast();
  const statementRef = useRef<HTMLDivElement>(null);
  const [selectedPeriod, setSelectedPeriod] = useState<'monthly' | 'weekly' | 'custom'>('monthly');
  const [startDate, setStartDate] = useState<Date | null>(startOfMonth(subMonths(new Date(), 1)));
  const [endDate, setEndDate] = useState<Date | null>(endOfMonth(subMonths(new Date(), 1)));
  const [selectedStatement, setSelectedStatement] = useState<EarningsStatement | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  // Mock data - replace with actual API calls
  const { data: statements, isPending: isStatementsLoading } = useQuery({
    queryKey: ['earnings-statements', selectedPeriod, startDate, endDate, modelId, agencyId],
    queryFn: async () => {
      // Mock data
      return [
        {
          id: '1',
          period: 'December 2024',
          start_date: '2024-12-01',
          end_date: '2024-12-31',
          gross_earnings: 15000,
          deductions: {
            platform_fees: 3000,
            payment_processing: 450,
            chargebacks: 100,
            other: 50 },
          net_earnings: 11400,
          status: 'paid' as const,
          generated_at: '2025-01-01T00:00:00Z',
          paid_at: '2025-01-05T00:00:00Z' },
        {
          id: '2',
          period: 'November 2024',
          start_date: '2024-11-01',
          end_date: '2024-11-30',
          gross_earnings: 13000,
          deductions: {
            platform_fees: 2600,
            payment_processing: 390,
            chargebacks: 50,
            other: 0 },
          net_earnings: 9960,
          status: 'final' as const,
          generated_at: '2024-12-01T00:00:00Z' },
        {
          id: '3',
          period: 'October 2024',
          start_date: '2024-10-01',
          end_date: '2024-10-31',
          gross_earnings: 11500,
          deductions: {
            platform_fees: 2300,
            payment_processing: 345,
            chargebacks: 200,
            other: 25 },
          net_earnings: 8630,
          status: 'paid' as const,
          generated_at: '2024-11-01T00:00:00Z',
          paid_at: '2024-11-05T00:00:00Z' },
      ];
    } });

  const { data: earningsBreakdown } = useQuery({
    queryKey: ['earnings-breakdown', selectedStatement?.id],
    queryFn: async () => {
      // Mock data
      return {
        subscriptions: 7500,
        tips: 3000,
        ppv_content: 2500,
        custom_requests: 1500,
        referrals: 500,
        other: 0 };
    },
    enabled: !!selectedStatement });

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD' }).format(amount);
  };

  const getStatusColor = (status: EarningsStatement['status']) => {
    switch (status) {
      case 'paid':
        return 'success';
      case 'final':
        return 'warning';
      case 'draft':
        return 'default';
      default:
        return 'default';
    }
  };

  const handlePrint = useReactToPrint({
    contentRef: statementRef,
    documentTitle: `Earnings_Statement_${selectedStatement?.period}` });

  const handleGenerateStatement = async () => {
    try {
      setIsGenerating(true);
      // TODO: Implement generation
      await new Promise(resolve => setTimeout(resolve, 2000));
      success('Statement generated successfully');
    } catch (err) {
      error('Failed to generate statement');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownloadStatement = async (_statement: EarningsStatement) => {
    try {
      // TODO: Implement download
      success('Statement downloaded successfully');
    } catch (err) {
      error('Failed to download statement');
    }
  };

  const handleEmailStatement = async (_statement: EarningsStatement) => {
    try {
      // TODO: Implement email
      success('Statement sent via email');
    } catch (err) {
      error('Failed to send statement');
    }
  };

  const StatementPreview = () => (
    <Box ref={statementRef} sx={{ p: 4, backgroundColor: 'white' }}>
      <Grid container spacing={3}>
        {/* Header */}
        <Grid item xs={12}>
          <Box display="flex" justifyContent="space-between" alignItems="start">
            <Box>
              <Typography variant="h4" gutterBottom>
                Earnings Statement
              </Typography>
              <Typography variant="subtitle1" color="text.secondary">
                {selectedStatement?.period}
              </Typography>
            </Box>
            <Box textAlign="right">
              <Typography variant="h6" gutterBottom>
                Agency Dark
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Statement #{selectedStatement?.id}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Generated: {selectedStatement && format(new Date(selectedStatement.generated_at), 'MMM dd, yyyy')}
              </Typography>
            </Box>
          </Box>
        </Grid>

        <Grid item xs={12}>
          <Divider />
        </Grid>

        {/* Period Info */}
        <Grid item xs={12}>
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={4}>
                <Typography variant="body2" color="text.secondary">
                  Statement Period
                </Typography>
                <Typography variant="body1">
                  {selectedStatement && format(new Date(selectedStatement.start_date), 'MMM dd, yyyy')} - 
                  {selectedStatement && format(new Date(selectedStatement.end_date), 'MMM dd, yyyy')}
                </Typography>
              </Grid>
              <Grid item xs={12} sm={4}>
                <Typography variant="body2" color="text.secondary">
                  Payment Status
                </Typography>
                <Chip
                  label={selectedStatement?.status.toUpperCase()}
                  color={getStatusColor(selectedStatement?.status || 'draft')}
                  size="small"
                />
              </Grid>
              <Grid item xs={12} sm={4}>
                <Typography variant="body2" color="text.secondary">
                  Payment Date
                </Typography>
                <Typography variant="body1">
                  {selectedStatement?.paid_at 
                    ? format(new Date(selectedStatement.paid_at), 'MMM dd, yyyy')
                    : 'Pending'
                  }
                </Typography>
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        {/* Earnings Breakdown */}
        <Grid item xs={12} md={6}>
          <Typography variant="h6" gutterBottom>
            Earnings Breakdown
          </Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableBody>
                <TableRow>
                  <TableCell>Subscriptions</TableCell>
                  <TableCell align="right">
                    {formatCurrency(earningsBreakdown?.subscriptions || 0)}
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Tips</TableCell>
                  <TableCell align="right">
                    {formatCurrency(earningsBreakdown?.tips || 0)}
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>PPV Content</TableCell>
                  <TableCell align="right">
                    {formatCurrency(earningsBreakdown?.ppv_content || 0)}
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Custom Requests</TableCell>
                  <TableCell align="right">
                    {formatCurrency(earningsBreakdown?.custom_requests || 0)}
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Referrals</TableCell>
                  <TableCell align="right">
                    {formatCurrency(earningsBreakdown?.referrals || 0)}
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Other</TableCell>
                  <TableCell align="right">
                    {formatCurrency(earningsBreakdown?.other || 0)}
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell><strong>Gross Earnings</strong></TableCell>
                  <TableCell align="right">
                    <strong>{formatCurrency(selectedStatement?.gross_earnings || 0)}</strong>
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>
        </Grid>

        {/* Deductions */}
        <Grid item xs={12} md={6}>
          <Typography variant="h6" gutterBottom>
            Deductions
          </Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableBody>
                <TableRow>
                  <TableCell>Platform Fees (20%)</TableCell>
                  <TableCell align="right" sx={{ color: 'error.main' }}>
                    -{formatCurrency(selectedStatement?.deductions.platform_fees || 0)}
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Payment Processing (3%)</TableCell>
                  <TableCell align="right" sx={{ color: 'error.main' }}>
                    -{formatCurrency(selectedStatement?.deductions.payment_processing || 0)}
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Chargebacks</TableCell>
                  <TableCell align="right" sx={{ color: 'error.main' }}>
                    -{formatCurrency(selectedStatement?.deductions.chargebacks || 0)}
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Other Deductions</TableCell>
                  <TableCell align="right" sx={{ color: 'error.main' }}>
                    -{formatCurrency(selectedStatement?.deductions.other || 0)}
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell><strong>Total Deductions</strong></TableCell>
                  <TableCell align="right" sx={{ color: 'error.main' }}>
                    <strong>
                      -{formatCurrency(
                        (selectedStatement?.deductions.platform_fees || 0) +
                        (selectedStatement?.deductions.payment_processing || 0) +
                        (selectedStatement?.deductions.chargebacks || 0) +
                        (selectedStatement?.deductions.other || 0)
                      )}
                    </strong>
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>
        </Grid>

        {/* Net Earnings */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3, backgroundColor: 'primary.light' }}>
            <Grid container alignItems="center">
              <Grid item xs>
                <Typography variant="h5">Net Earnings</Typography>
              </Grid>
              <Grid item>
                <Typography variant="h4" color="primary.main">
                  {formatCurrency(selectedStatement?.net_earnings || 0)}
                </Typography>
              </Grid>
            </Grid>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5">Earnings Statements</Typography>
        <Box display="flex" gap={2} alignItems="center">
          <TextField
            select
            label="Period"
            value={selectedPeriod}
            onChange={ (e) => setSelectedPeriod(e.target.value as 'monthly' | 'weekly' | 'custom')    }
            size="small"
            sx={{ minWidth: 120 }}
          >
            <MenuItem value="monthly">Monthly</MenuItem>
            <MenuItem value="weekly">Weekly</MenuItem>
            <MenuItem value="custom">Custom</MenuItem>
          </TextField>

          {selectedPeriod === 'custom' && (
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
          )}

          <Button
            variant="contained"
            startIcon={<Receipt />}
            onClick={handleGenerateStatement}
            disabled={isGenerating}
          >
            Generate Statement
          </Button>
        </Box>
      </Box>

      <Grid container spacing={3}>
        {/* Statements */}
        <Grid item xs={12} md={selectedStatement ? 4 : 12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Statement History
              </Typography>

              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Period</TableCell>
                      <TableCell align="right">Net Earnings</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell align="center">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {isStatementsLoading ? (
                      <TableRow>
                        <TableCell colSpan={4} align="center">
                          <LinearProgress />
                        </TableCell>
                      </TableRow>
                    ) : statements?.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={4} align="center">
                          <Typography variant="body2" color="textSecondary">
                            No statements found
                          </Typography>
                        </TableCell>
                      </TableRow>
                    ) : (
                      statements?.map((statement) => (
                        <TableRow
                          key={statement.id}
                          hover
                          selected={selectedStatement?.id === statement.id}
                          sx={{ cursor: 'pointer' }}
                          onClick={() => setSelectedStatement(statement)}
                        >
                          <TableCell>{statement.period}</TableCell>
                          <TableCell align="right">
                            <Typography variant="body2" fontWeight="medium">
                              {formatCurrency(statement.net_earnings)}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={statement.status.toUpperCase()}
                              color={getStatusColor(statement.status)}
                              size="small"
                            />
                          </TableCell>
                          <TableCell align="center">
                            <Box display="flex" justifyContent="center" gap={0.5}>
                              <IconButton
                                size="small"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setSelectedStatement(statement);
                                }}
                              >
                                <Visibility />
                              </IconButton>
                              <IconButton
                                size="small"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDownloadStatement(statement);
                                }}
                              >
                                <Download />
                              </IconButton>
                              <IconButton
                                size="small"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleEmailStatement(statement);
                                }}
                              >
                                <Email />
                              </IconButton>
                            </Box>
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

        {/* Statement Preview */}
        {selectedStatement && (
          <Grid item xs={12} md={8}>
            <Card>
              <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Typography variant="h6">Statement Details</Typography>
                  <Box display="flex" gap={1}>
                    <Button
                      startIcon={<Print />}
                      onClick={handlePrint}
                    >
                      Print
                    </Button>
                    <Button
                      startIcon={<Download />}
                      onClick={() => handleDownloadStatement(selectedStatement)}
                    >
                      Download
                    </Button>
                    <Button
                      startIcon={<Email />}
                      onClick={() => handleEmailStatement(selectedStatement)}
                    >
                      Email
                    </Button>
                  </Box>
                </Box>
                <Divider sx={{ mb: 2 }} />
                <StatementPreview />
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>
    </Box>
  );
};
