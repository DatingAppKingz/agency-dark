import React, { useState } from 'react';
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Chip,
  IconButton,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Grid,
  Typography,
  Tooltip,
  Button,
} from '@mui/material';
import {
  Visibility as ViewIcon,
  Receipt as ReceiptIcon,
  FilterList as FilterIcon,
  Download as DownloadIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { TransactionType, TransactionStatus } from '@/types/financial';
import { formatCurrency } from '@/utils/formatters';

interface Transaction {
  id: number;
  type: TransactionType;
  status: TransactionStatus;
  platform_transaction_id?: string;
  gross_amount: number;
  platform_fee: number;
  agency_commission: number;
  net_amount: number;
  currency: string;
  fan_id: string;
  fan_username: string;
  transaction_date: string;
  processed_at?: string;
  description?: string;
  model_id: number;
  model_name: string;
}

interface TransactionListProps {
  transactions: Transaction[];
  loading?: boolean;
  onRefresh?: () => void;
  onViewDetails?: (transaction: Transaction) => void;
  showModelColumn?: boolean;
}

export const TransactionList: React.FC<TransactionListProps> = ({
  transactions,
  loading = false,
  onRefresh,
  onViewDetails,
  showModelColumn = true,
}) => {
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [filters, setFilters] = useState({
    type: '',
    status: '',
    startDate: '',
    endDate: '',
    search: '',
  });

  const getTypeColor = (type: TransactionType) => {
    switch (type) {
      case TransactionType.TIP:
        return 'success';
      case TransactionType.PPV:
        return 'primary';
      case TransactionType.SUBSCRIPTION:
        return 'info';
      case TransactionType.MESSAGE:
        return 'secondary';
      case TransactionType.REFERRAL:
        return 'warning';
      case TransactionType.CHARGEBACK:
      case TransactionType.REFUND:
        return 'error';
      default:
        return 'default';
    }
  };

  const getStatusColor = (status: TransactionStatus) => {
    switch (status) {
      case TransactionStatus.COMPLETED:
        return 'success';
      case TransactionStatus.PENDING:
        return 'warning';
      case TransactionStatus.FAILED:
        return 'error';
      case TransactionStatus.REFUNDED:
      case TransactionStatus.DISPUTED:
        return 'error';
      default:
        return 'default';
    }
  };

  const filteredTransactions = transactions.filter(transaction => {
    if (filters.type && transaction.type !== filters.type) return false;
    if (filters.status && transaction.status !== filters.status) return false;
    if (filters.startDate && new Date(transaction.transaction_date) < new Date(filters.startDate)) return false;
    if (filters.endDate && new Date(transaction.transaction_date) > new Date(filters.endDate)) return false;
    if (filters.search) {
      const searchLower = filters.search.toLowerCase();
      return (
        transaction.fan_username.toLowerCase().includes(searchLower) ||
        transaction.platform_transaction_id?.toLowerCase().includes(searchLower) ||
        transaction.description?.toLowerCase().includes(searchLower)
      );
    }
    return true;
  });

  const handleExport = () => {
    // TODO: Implement CSV export
    console.log('Export transactions');
  };

  return (
    <Box>
      {/* Filters */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} sm={6} md={2}>
            <FormControl fullWidth size="small">
              <InputLabel>Type</InputLabel>
              <Select
                value={filters.type}
                onChange={(e) => setFilters({ ...filters, type: e.target.value })}
                label="Type"
              >
                <MenuItem value="">All</MenuItem>
                <MenuItem value={TransactionType.TIP}>Tips</MenuItem>
                <MenuItem value={TransactionType.PPV}>PPV</MenuItem>
                <MenuItem value={TransactionType.SUBSCRIPTION}>Subscriptions</MenuItem>
                <MenuItem value={TransactionType.MESSAGE}>Messages</MenuItem>
                <MenuItem value={TransactionType.REFERRAL}>Referrals</MenuItem>
                <MenuItem value={TransactionType.ADJUSTMENT}>Adjustments</MenuItem>
                <MenuItem value={TransactionType.CHARGEBACK}>Chargebacks</MenuItem>
                <MenuItem value={TransactionType.REFUND}>Refunds</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={2}>
            <FormControl fullWidth size="small">
              <InputLabel>Status</InputLabel>
              <Select
                value={filters.status}
                onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                label="Status"
              >
                <MenuItem value="">All</MenuItem>
                <MenuItem value={TransactionStatus.PENDING}>Pending</MenuItem>
                <MenuItem value={TransactionStatus.COMPLETED}>Completed</MenuItem>
                <MenuItem value={TransactionStatus.FAILED}>Failed</MenuItem>
                <MenuItem value={TransactionStatus.REFUNDED}>Refunded</MenuItem>
                <MenuItem value={TransactionStatus.DISPUTED}>Disputed</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={2}>
            <TextField
              fullWidth
              size="small"
              label="Start Date"
              type="date"
              value={filters.startDate}
              onChange={(e) => setFilters({ ...filters, startDate: e.target.value })}
              InputLabelProps={{ shrink: true }}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={2}>
            <TextField
              fullWidth
              size="small"
              label="End Date"
              type="date"
              value={filters.endDate}
              onChange={(e) => setFilters({ ...filters, endDate: e.target.value })}
              InputLabelProps={{ shrink: true }}
            />
          </Grid>
          <Grid item xs={12} sm={8} md={2}>
            <TextField
              fullWidth
              size="small"
              label="Search"
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              placeholder="Fan, ID, description..."
            />
          </Grid>
          <Grid item xs={12} sm={4} md={2}>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                variant="outlined"
                startIcon={<RefreshIcon />}
                onClick={onRefresh}
                disabled={loading}
              >
                Refresh
              </Button>
              <Tooltip title="Export CSV">
                <IconButton onClick={handleExport}>
                  <DownloadIcon />
                </IconButton>
              </Tooltip>
            </Box>
          </Grid>
        </Grid>
      </Paper>

      {/* Summary Stats */}
      <Grid container spacing={2} sx={{ mb: 2 }}>
        <Grid item xs={6} sm={3}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h6">
              {formatCurrency(
                filteredTransactions.reduce((sum, t) => sum + t.gross_amount, 0),
                'USD'
              )}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Total Gross
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={6} sm={3}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h6">
              {formatCurrency(
                filteredTransactions.reduce((sum, t) => sum + t.platform_fee, 0),
                'USD'
              )}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Platform Fees
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={6} sm={3}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h6">
              {formatCurrency(
                filteredTransactions.reduce((sum, t) => sum + t.agency_commission, 0),
                'USD'
              )}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Agency Commission
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={6} sm={3}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <Typography variant="h6">
              {formatCurrency(
                filteredTransactions.reduce((sum, t) => sum + t.net_amount, 0),
                'USD'
              )}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Model Earnings
            </Typography>
          </Paper>
        </Grid>
      </Grid>

      {/* Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Date</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Fan</TableCell>
              {showModelColumn && <TableCell>Model</TableCell>}
              <TableCell align="right">Gross</TableCell>
              <TableCell align="right">Fees</TableCell>
              <TableCell align="right">Commission</TableCell>
              <TableCell align="right">Net</TableCell>
              <TableCell>Transaction ID</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredTransactions
              .slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)
              .map((transaction) => (
                <TableRow key={transaction.id} hover>
                  <TableCell>
                    {format(new Date(transaction.transaction_date), 'MMM d, yyyy HH:mm')}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={transaction.type}
                      color={getTypeColor(transaction.type)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={transaction.status}
                      color={getStatusColor(transaction.status)}
                      size="small"
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">{transaction.fan_username}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {transaction.fan_id}
                    </Typography>
                  </TableCell>
                  {showModelColumn && (
                    <TableCell>{transaction.model_name}</TableCell>
                  )}
                  <TableCell align="right">
                    {formatCurrency(transaction.gross_amount, transaction.currency)}
                  </TableCell>
                  <TableCell align="right">
                    {formatCurrency(transaction.platform_fee, transaction.currency)}
                  </TableCell>
                  <TableCell align="right">
                    {formatCurrency(transaction.agency_commission, transaction.currency)}
                  </TableCell>
                  <TableCell align="right">
                    <strong>{formatCurrency(transaction.net_amount, transaction.currency)}</strong>
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption">
                      {transaction.platform_transaction_id || '-'}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    <Tooltip title="View Details">
                      <IconButton
                        size="small"
                        onClick={() => onViewDetails?.(transaction)}
                      >
                        <ViewIcon />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
        <TablePagination
          rowsPerPageOptions={[5, 10, 25, 50]}
          component="div"
          count={filteredTransactions.length}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={(_, newPage) => setPage(newPage)}
          onRowsPerPageChange={(e) => {
            setRowsPerPage(parseInt(e.target.value, 10));
            setPage(0);
          }}
        />
      </TableContainer>
    </Box>
  );
};