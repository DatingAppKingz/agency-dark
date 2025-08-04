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
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Grid,
  Typography,
  Checkbox,
  Toolbar,
  Tooltip,
  Menu,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import {
  Visibility as ViewIcon,
  GetApp as DownloadIcon,
  MoreVert as MoreIcon,
  CheckCircle as ApproveIcon,
  Cancel as CancelIcon,
  Refresh as RefreshIcon,
  FilterList as FilterIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { useNavigate } from 'react-router-dom';
import { PayoutStatus } from '@/types/financial';
import { formatCurrency } from '@/utils/formatters';

interface Payout {
  id: number;
  payout_number: string;
  model_id: number;
  model_name: string;
  status: PayoutStatus;
  period_start: string;
  period_end: string;
  gross_earnings: number;
  commission_amount: number;
  adjustments: number;
  net_amount: number;
  currency: string;
  payment_method: any;
  scheduled_date: string;
  processed_date?: string;
  completed_date?: string;
  notes?: string;
  earnings_count: number;
  created_at: string;
  updated_at: string;
}

interface PayoutListProps {
  payouts: Payout[];
  loading?: boolean;
  onRefresh?: () => void;
  onApprove?: (payoutIds: number[]) => void;
  onCancel?: (payoutIds: number[]) => void;
  onProcess?: (payoutIds: number[]) => void;
  showBulkActions?: boolean;
  userRole?: string;
}

export const PayoutList: React.FC<PayoutListProps> = ({
  payouts,
  loading = false,
  onRefresh,
  onApprove,
  onCancel,
  onProcess,
  showBulkActions = true,
  userRole = 'agency_admin',
}) => {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [selected, setSelected] = useState<number[]>([]);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [currentPayout, setCurrentPayout] = useState<Payout | null>(null);
  const [filters, setFilters] = useState({
    status: '',
    modelId: '',
    startDate: '',
    endDate: '',
  });

  const handleSelectAll = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.checked) {
      const newSelected = payouts.map((p) => p.id);
      setSelected(newSelected);
    } else {
      setSelected([]);
    }
  };

  const handleSelect = (id: number) => {
    const selectedIndex = selected.indexOf(id);
    let newSelected: number[] = [];

    if (selectedIndex === -1) {
      newSelected = newSelected.concat(selected, id);
    } else if (selectedIndex === 0) {
      newSelected = newSelected.concat(selected.slice(1));
    } else if (selectedIndex === selected.length - 1) {
      newSelected = newSelected.concat(selected.slice(0, -1));
    } else if (selectedIndex > 0) {
      newSelected = newSelected.concat(
        selected.slice(0, selectedIndex),
        selected.slice(selectedIndex + 1)
      );
    }

    setSelected(newSelected);
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, payout: Payout) => {
    setAnchorEl(event.currentTarget);
    setCurrentPayout(payout);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setCurrentPayout(null);
  };

  const getStatusColor = (status: PayoutStatus) => {
    switch (status) {
      case PayoutStatus.PENDING:
        return 'warning';
      case PayoutStatus.PROCESSING:
        return 'info';
      case PayoutStatus.COMPLETED:
        return 'success';
      case PayoutStatus.FAILED:
        return 'error';
      case PayoutStatus.CANCELLED:
        return 'default';
      default:
        return 'default';
    }
  };

  const isActionDisabled = () => {
    return selected.length === 0;
  };

  const canApprove = () => {
    return selected.every(id => {
      const payout = payouts.find(p => p.id === id);
      return payout?.status === PayoutStatus.PENDING;
    });
  };

  const canProcess = () => {
    return selected.every(id => {
      const payout = payouts.find(p => p.id === id);
      return payout?.status === PayoutStatus.PROCESSING;
    });
  };

  const canCancel = () => {
    return selected.every(id => {
      const payout = payouts.find(p => p.id === id);
      return payout?.status === PayoutStatus.PENDING || payout?.status === PayoutStatus.PROCESSING;
    });
  };

  return (
    <Box>
      {/* Filters */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} sm={3}>
            <FormControl fullWidth size="small">
              <InputLabel>Status</InputLabel>
              <Select
                value={filters.status}
                onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                label="Status"
              >
                <MenuItem value="">All</MenuItem>
                <MenuItem value={PayoutStatus.PENDING}>Pending</MenuItem>
                <MenuItem value={PayoutStatus.PROCESSING}>Processing</MenuItem>
                <MenuItem value={PayoutStatus.COMPLETED}>Completed</MenuItem>
                <MenuItem value={PayoutStatus.FAILED}>Failed</MenuItem>
                <MenuItem value={PayoutStatus.CANCELLED}>Cancelled</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={3}>
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
          <Grid item xs={12} sm={3}>
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
          <Grid item xs={12} sm={3}>
            <Button
              fullWidth
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={onRefresh}
              disabled={loading}
            >
              Refresh
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {/* Bulk Actions Toolbar */}
      {showBulkActions && selected.length > 0 && (
        <Paper sx={{ mb: 2 }}>
          <Toolbar
            sx={{
              pl: { sm: 2 },
              pr: { xs: 1, sm: 1 },
              bgcolor: 'action.selected',
            }}
          >
            <Typography sx={{ flex: '1 1 100%' }} color="inherit" variant="subtitle1">
              {selected.length} selected
            </Typography>
            {onApprove && canApprove() && (
              <Tooltip title="Approve">
                <IconButton onClick={() => onApprove(selected)} color="success">
                  <ApproveIcon />
                </IconButton>
              </Tooltip>
            )}
            {onProcess && canProcess() && (
              <Tooltip title="Mark as Processed">
                <IconButton onClick={() => onProcess(selected)} color="info">
                  <CheckCircle />
                </IconButton>
              </Tooltip>
            )}
            {onCancel && canCancel() && (
              <Tooltip title="Cancel">
                <IconButton onClick={() => onCancel(selected)} color="error">
                  <CancelIcon />
                </IconButton>
              </Tooltip>
            )}
          </Toolbar>
        </Paper>
      )}

      {/* Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              {showBulkActions && (
                <TableCell padding="checkbox">
                  <Checkbox
                    color="primary"
                    indeterminate={selected.length > 0 && selected.length < payouts.length}
                    checked={payouts.length > 0 && selected.length === payouts.length}
                    onChange={handleSelectAll}
                  />
                </TableCell>
              )}
              <TableCell>Payout #</TableCell>
              <TableCell>Model</TableCell>
              <TableCell>Period</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Gross</TableCell>
              <TableCell align="right">Commission</TableCell>
              <TableCell align="right">Net Amount</TableCell>
              <TableCell>Payment Method</TableCell>
              <TableCell>Scheduled</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {payouts
              .slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)
              .map((payout) => {
                const isSelected = selected.indexOf(payout.id) !== -1;
                
                return (
                  <TableRow
                    key={payout.id}
                    hover
                    selected={isSelected}
                    sx={{ cursor: 'pointer' }}
                  >
                    {showBulkActions && (
                      <TableCell padding="checkbox">
                        <Checkbox
                          color="primary"
                          checked={isSelected}
                          onChange={() => handleSelect(payout.id)}
                        />
                      </TableCell>
                    )}
                    <TableCell>{payout.payout_number}</TableCell>
                    <TableCell>{payout.model_name}</TableCell>
                    <TableCell>
                      {format(new Date(payout.period_start), 'MMM d')} - 
                      {format(new Date(payout.period_end), 'MMM d, yyyy')}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={payout.status}
                        color={getStatusColor(payout.status)}
                        size="small"
                      />
                    </TableCell>
                    <TableCell align="right">
                      {formatCurrency(payout.gross_earnings, payout.currency)}
                    </TableCell>
                    <TableCell align="right">
                      {formatCurrency(payout.commission_amount, payout.currency)}
                    </TableCell>
                    <TableCell align="right">
                      <strong>{formatCurrency(payout.net_amount, payout.currency)}</strong>
                    </TableCell>
                    <TableCell>{payout.payment_method.method_type}</TableCell>
                    <TableCell>
                      {format(new Date(payout.scheduled_date), 'MMM d, yyyy')}
                    </TableCell>
                    <TableCell align="center">
                      <IconButton
                        size="small"
                        onClick={(e) => handleMenuOpen(e, payout)}
                      >
                        <MoreIcon />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                );
              })}
          </TableBody>
        </Table>
        <TablePagination
          rowsPerPageOptions={[5, 10, 25, 50]}
          component="div"
          count={payouts.length}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={(_, newPage) => setPage(newPage)}
          onRowsPerPageChange={(e) => {
            setRowsPerPage(parseInt(e.target.value, 10));
            setPage(0);
          }}
        />
      </TableContainer>

      {/* Actions Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem
          onClick={() => {
            navigate(`/dashboard/financial/payouts/${currentPayout?.id}`);
            handleMenuClose();
          }}
        >
          <ListItemIcon>
            <ViewIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>View Details</ListItemText>
        </MenuItem>
        <MenuItem
          onClick={() => {
            // TODO: Implement download invoice
            handleMenuClose();
          }}
        >
          <ListItemIcon>
            <DownloadIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Download Invoice</ListItemText>
        </MenuItem>
      </Menu>
    </Box>
  );
}