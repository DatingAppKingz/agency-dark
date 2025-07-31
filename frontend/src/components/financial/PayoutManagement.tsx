import { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
  Alert,
  Chip,
  IconButton,
  Tooltip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  CircularProgress,
  InputAdornment,
  Grid } from '@mui/material';
import {
  Add,
  Cancel,
  Download,
  Refresh,
  Search,
  AccountBalance,
  PaymentOutlined } from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { financialApi } from '@/services/api/financial';
import type { Payout, PaymentMethod } from '@/types/financial';

const requestPayoutSchema = z.object({
  amount: z.number().min(10, 'Minimum payout amount is $10'),
  payment_method_id: z.string().min(1, 'Payment method is required') });

type RequestPayoutForm = z.infer<typeof requestPayoutSchema>;

interface PayoutManagementProps {
  modelId?: string;
  agencyId?: string;
}

export const PayoutManagement = ({ modelId, agencyId }: PayoutManagementProps) => {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [statusFilter, setStatusFilter] = useState<Payout['status'] | ''>('');
  const [searchTerm, setSearchTerm] = useState('');
  const [requestDialogOpen, setRequestDialogOpen] = useState(false);
  const [selectedPayout, setSelectedPayout] = useState<Payout | null>(null);

  const { register, handleSubmit, formState: { errors }, reset } = useForm<RequestPayoutForm>({
    resolver: zodResolver(requestPayoutSchema) });

  const { data: paymentMethods } = useQuery({
    queryKey: ['payment-methods'],
    queryFn: () => financialApi.getPaymentMethods() });

  const { data: summary } = useQuery({
    queryKey: ['financial-summary', modelId, agencyId],
    queryFn: () => financialApi.getFinancialSummary({ model_id: modelId, agency_id: agencyId }) });

  const { data: payouts, isPending, refetch } = useQuery({
    queryKey: ['payouts', page, rowsPerPage, statusFilter, searchTerm, modelId, agencyId],
    queryFn: () => financialApi.getPayouts({
      page: page + 1,
      size: rowsPerPage,
      status: statusFilter || undefined,
      search: searchTerm || undefined,
      model_id: modelId,
      agency_id: agencyId }) });

  const requestPayoutMutation = useMutation({
    mutationFn: financialApi.createPayout,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payouts'] });
      queryClient.invalidateQueries({ queryKey: ['financial-summary'] });
      setRequestDialogOpen(false);
      reset();
    } });

  const cancelPayoutMutation = useMutation({
    mutationFn: financialApi.cancelPayout,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payouts'] });
      queryClient.invalidateQueries({ queryKey: ['financial-summary'] });
    } });

  const onSubmitRequest = (data: RequestPayoutForm) => {
    requestPayoutMutation.mutate({
      ...data,
      model_id: modelId
    });
  };

  const handleCancelPayout = (payoutId: string) => {
    if (window.confirm('Are you sure you want to cancel this payout?')) {
      cancelPayoutMutation.mutate(payoutId);
    }
  };

  const getStatusColor = (status: Payout['status']) => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'pending':
        return 'warning';
      case 'processing':
        return 'info';
      case 'failed':
        return 'error';
      default:
        return 'default';
    }
  };

  const formatCurrency = (amount: number, currency = 'USD') => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency }).format(amount);
  };

  const formatDate = (date: string) => {
    return new Date(date).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit' });
  };

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5">Payout Management</Typography>
        <Box display="flex" gap={2}>
          <Tooltip title="Refresh">
            <IconButton onClick={() => refetch()}>
              <Refresh />
            </IconButton>
          </Tooltip>
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={() => setRequestDialogOpen(true)}
            disabled={!summary?.available_balance || summary.available_balance < 10}
          >
            Request Payout
          </Button>
        </Box>
      </Box>

      {summary && (
        <Grid container spacing={3} mb={3}>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" gap={1}>
                  <AccountBalance color="primary" />
                  <Box>
                    <Typography variant="body2" color="textSecondary">
                      Available Balance
                    </Typography>
                    <Typography variant="h6">
                      {formatCurrency(summary.available_balance, summary.currency)}
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" gap={1}>
                  <PaymentOutlined color="warning" />
                  <Box>
                    <Typography variant="body2" color="textSecondary">
                      Pending Payouts
                    </Typography>
                    <Typography variant="h6">
                      {formatCurrency(summary.pending_payouts, summary.currency)}
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      <Card>
        <CardContent>
          <Box display="flex" gap={2} mb={2}>
            <TextField
              placeholder="Search payouts..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              size="small"
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Search />
                  </InputAdornment>
                ) }}
            />
            <TextField
              select
              label="Status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as Payout['status'] | '')}
              size="small"
              sx={{ minWidth: 150 }}
            >
              <MenuItem value="">All</MenuItem>
              <MenuItem value="pending">Pending</MenuItem>
              <MenuItem value="processing">Processing</MenuItem>
              <MenuItem value="completed">Completed</MenuItem>
              <MenuItem value="failed">Failed</MenuItem>
            </TextField>
          </Box>

          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Date</TableCell>
                  <TableCell>Amount</TableCell>
                  <TableCell>Method</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Processed</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {isPending ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center">
                      <CircularProgress size={40} />
                    </TableCell>
                  </TableRow>
                ) : payouts?.data?.items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center">
                      <Typography variant="body2" color="textSecondary">
                        No payouts found
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  payouts?.items?.map((payout: any) => (
                    <TableRow key={payout.id}>
                      <TableCell>{formatDate(payout.requested_at)}</TableCell>
                      <TableCell>
                        {formatCurrency(payout.amount, payout.currency)}
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={payout.method.replace('_', ' ').toUpperCase()}
                          size="small"
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={payout.status.toUpperCase()}
                          color={getStatusColor(payout.status)}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        {payout.processed_at ? formatDate(payout.processed_at) : '-'}
                      </TableCell>
                      <TableCell align="right">
                        {payout.status === 'pending' && (
                          <Tooltip title="Cancel Payout">
                            <IconButton
                              size="small"
                              onClick={() => handleCancelPayout(payout.id)}
                              disabled={cancelPayoutMutation.isPending}
                            >
                              <Cancel />
                            </IconButton>
                          </Tooltip>
                        )}
                        <Tooltip title="View Details">
                          <IconButton
                            size="small"
                            onClick={() => setSelectedPayout(payout)}
                          >
                            <Download />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>

          {payouts?.data && (
            <TablePagination
              component="div"
              count={payouts.data.total}
              page={page}
              onPageChange={(_, newPage) => setPage(newPage)}
              rowsPerPage={rowsPerPage}
              onRowsPerPageChange={(e) => {
                setRowsPerPage(parseInt(e.target.value, 10));
                setPage(0);
              }}
            />
          )}
        </CardContent>
      </Card>

      <Dialog open={requestDialogOpen} onClose={() => setRequestDialogOpen(false)} maxWidth="sm" fullWidth>
        <form onSubmit={handleSubmit(onSubmitRequest)}>
          <DialogTitle>Request Payout</DialogTitle>
          <DialogContent>
            <Box display="flex" flexDirection="column" gap={2} pt={1}>
              <Alert severity="info">
                Available balance: {formatCurrency(summary?.available_balance || 0)}
              </Alert>
              <TextField
                label="Amount"
                type="number"
                fullWidth
                {...register('amount', { valueAsNumber: true })}
                error={!!errors.amount}
                helperText={errors.amount?.message}
                InputProps={{
                  startAdornment: <InputAdornment position="start">$</InputAdornment> }}
              />
              <TextField
                select
                label="Payment Method"
                fullWidth
                {...register('payment_method_id')}
                error={!!errors.payment_method_id}
                helperText={errors.payment_method_id?.message}
              >
                {paymentMethods?.map((method: any) => (
                  <MenuItem key={method.id} value={method.id}>
                    {method.type.replace('_', ' ').toUpperCase()}
                    {method.is_default && ' (Default)'}
                  </MenuItem>
                ))}
              </TextField>
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setRequestDialogOpen(false)}>Cancel</Button>
            <Button
              type="submit"
              variant="contained"
              disabled={requestPayoutMutation.isPending}
            >
              {requestPayoutMutation.isPending ? 'Requesting...' : 'Request Payout'}
            </Button>
          </DialogActions>
        </form>
      </Dialog>

      <Dialog
        open={!!selectedPayout}
        onClose={() => setSelectedPayout(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Payout Details</DialogTitle>
        <DialogContent>
          {selectedPayout && (
            <Box display="flex" flexDirection="column" gap={2}>
              <Box>
                <Typography variant="body2" color="textSecondary">
                  Payout ID
                </Typography>
                <Typography>{selectedPayout.id}</Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="textSecondary">
                  Amount
                </Typography>
                <Typography>
                  {formatCurrency(selectedPayout.amount, selectedPayout.currency)}
                </Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="textSecondary">
                  Status
                </Typography>
                <Chip
                  label={selectedPayout.status.toUpperCase()}
                  color={getStatusColor(selectedPayout.status)}
                  size="small"
                />
              </Box>
              {selectedPayout.failure_reason && (
                <Alert severity="error">{selectedPayout.failure_reason}</Alert>
              )}
              <Box>
                <Typography variant="body2" color="textSecondary">
                  Requested At
                </Typography>
                <Typography>{formatDate(selectedPayout.requested_at)}</Typography>
              </Box>
              {selectedPayout.processed_at && (
                <Box>
                  <Typography variant="body2" color="textSecondary">
                    Processed At
                  </Typography>
                  <Typography>{formatDate(selectedPayout.processed_at)}</Typography>
                </Box>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelectedPayout(null)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
