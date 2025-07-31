import { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  TextField,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Chip,
  CircularProgress,
  InputAdornment,
  Button,
  Menu } from '@mui/material';
import {
  Search,
  Download,
  TrendingUp,
  TrendingDown,
  SwapHoriz,
  Receipt,
  Description } from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { useQuery } from '@tanstack/react-query';
import { financialApi } from '@/services/api/financial';
import { InvoiceGenerator } from './InvoiceGenerator';
import type { Transaction } from '@/types/financial';

interface TransactionHistoryProps {
  modelId?: string;
  agencyId?: string;
}

export const TransactionHistory = ({ modelId, agencyId }: TransactionHistoryProps) => {
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [typeFilter, setTypeFilter] = useState<Transaction['type'] | ''>('');
  const [statusFilter, setStatusFilter] = useState<Transaction['status'] | ''>('');
  const [searchTerm, setSearchTerm] = useState('');
  const [startDate, setStartDate] = useState<Date | null>(null);
  const [endDate, setEndDate] = useState<Date | null>(null);
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
  const [invoiceOpen, setInvoiceOpen] = useState(false);

  const { data: transactions, isPending } = useQuery({
    queryKey: ['transactions', page, rowsPerPage, typeFilter, statusFilter, searchTerm, startDate, endDate, modelId, agencyId],
    queryFn: () => financialApi.getTransactions({
      page: page + 1,
      size: rowsPerPage,
      type: typeFilter || undefined,
      status: statusFilter || undefined,
      search: searchTerm || undefined,
      start_date: startDate?.toISOString(),
      end_date: endDate?.toISOString(),
      model_id: modelId,
      agency_id: agencyId }) });

  const getTypeIcon = (type: Transaction['type']) => {
    switch (type) {
      case 'credit':
        return <TrendingUp sx={{ fontSize: 20 }} />;
      case 'debit':
        return <TrendingDown sx={{ fontSize: 20 }} />;
      case 'payout':
        return <SwapHoriz sx={{ fontSize: 20 }} />;
      case 'commission':
        return <Receipt sx={{ fontSize: 20 }} />;
      default:
        return null;
    }
  };

  const getTypeColor = (type: Transaction['type']) => {
    switch (type) {
      case 'credit':
        return 'success';
      case 'debit':
        return 'error';
      case 'payout':
        return 'info';
      case 'commission':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getStatusColor = (status: Transaction['status']) => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'pending':
        return 'warning';
      case 'failed':
        return 'error';
      case 'cancelled':
        return 'default';
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

  const handleExport = async (format: 'csv' | 'pdf') => {
    try {
      const response = await financialApi.exportTransactions({
        type: typeFilter || undefined,
        status: statusFilter || undefined,
        search: searchTerm || undefined,
        start_date: startDate?.toISOString(),
        end_date: endDate?.toISOString(),
        model_id: modelId,
        agency_id: agencyId,
        format });

      const blob = new Blob([response.data], {
        type: format === 'csv' ? 'text/csv' : 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `transactions-${new Date().toISOString().split('T')[0]}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Export failed:', error);
    }
    setMenuAnchor(null);
  };

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5">Transaction History</Typography>
        <Box display="flex" gap={1}>
          <Button
            variant="outlined"
            startIcon={<Description />}
            onClick={() => setInvoiceOpen(true)}
          >
            Generate Invoice
          </Button>
          <Button
            variant="outlined"
            startIcon={<Download />}
            onClick={(event) => setMenuAnchor(eevent.currentTarget)}
          >
            Export
          </Button>
          <Menu
            anchorEl={menuAnchor}
            open={Boolean(menuAnchor)}
            onClose={() => setMenuAnchor(null)}
          >
            <MenuItem onClick={() => handleExport('csv')}>Export as CSV</MenuItem>
            <MenuItem onClick={() => handleExport('pdf')}>Export as PDF</MenuItem>
          </Menu>
        </Box>
      </Box>

      <Card>
        <CardContent>
          <Box display="flex" gap={2} mb={2} flexWrap="wrap">
            <TextField
              placeholder="Search transactions..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              size="small"
              sx={{ minWidth: 250 }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Search />
                  </InputAdornment>
                ) }}
            />
            <TextField
              select
              label="Type"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value as Transaction['type'] | '')}
              size="small"
              sx={{ minWidth: 120 }}
            >
              <MenuItem value="">All</MenuItem>
              <MenuItem value="credit">Credit</MenuItem>
              <MenuItem value="debit">Debit</MenuItem>
              <MenuItem value="payout">Payout</MenuItem>
              <MenuItem value="commission">Commission</MenuItem>
            </TextField>
            <TextField
              select
              label="Status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as Transaction['status'] | '')}
              size="small"
              sx={{ minWidth: 120 }}
            >
              <MenuItem value="">All</MenuItem>
              <MenuItem value="pending">Pending</MenuItem>
              <MenuItem value="completed">Completed</MenuItem>
              <MenuItem value="failed">Failed</MenuItem>
              <MenuItem value="cancelled">Cancelled</MenuItem>
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
          </Box>

          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Date</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Description</TableCell>
                  <TableCell align="right">Amount</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Reference</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {isPending ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center">
                      <CircularProgress size={40} />
                    </TableCell>
                  </TableRow>
                ) : transactions?.data?.items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center">
                      <Typography variant="body2" color="textSecondary">
                        No transactions found
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  transactions?.data?.items.map((transaction) => (
                    <TableRow key={transaction.id}>
                      <TableCell>{formatDate(transaction.created_at)}</TableCell>
                      <TableCell>
                        <Box display="flex" alignItems="center" gap={1}>
                          <Box
                            sx={{
                              color: `${getTypeColor(transaction.type)}.main`,
                              display: 'flex',
                              alignItems: 'center' }}
                          >
                            {getTypeIcon(transaction.type)}
                          </Box>
                          <Typography variant="body2">
                            {transaction.type.charAt(0).toUpperCase() + transaction.type.slice(1)}
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>{transaction.description}</TableCell>
                      <TableCell align="right">
                        <Typography
                          variant="body2"
                          color={transaction.type === 'credit' ? 'success.main' : 'error.main'}
                          fontWeight="medium"
                        >
                          {transaction.type === 'credit' ? '+' : '-'}
                          {formatCurrency(transaction.amount, transaction.currency)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={transaction.status.toUpperCase()}
                          color={getStatusColor(transaction.status)}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="textSecondary">
                          {transaction.reference_id || '-'}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>

          {transactions?.data && (
            <TablePagination
              component="div"
              count={transactions.data.total}
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

      <InvoiceGenerator
        open={invoiceOpen}
        onClose={() => setInvoiceOpen(false)}
        onSave={async (invoice) => {
          // TODO: Implement invoice save
          console.log('Saving invoice:', invoice);
        }}
      />
    </Box>
  );
};
