import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  IconButton,
  Menu,
  MenuItem,
  LinearProgress,
  Avatar,
  Tooltip,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  Tabs,
  Tab,
  TextField,
  InputAdornment,
  TablePagination,
} from '@mui/material';
import {
  MoreVert as MoreIcon,
  Refresh as RefreshIcon,
  Download as DownloadIcon,
  Cancel as CancelIcon,
  Replay as RetryIcon,
  Info as InfoIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Schedule as PendingIcon,
  Search as SearchIcon,
  FilterList as FilterIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { bulkOperationsService } from '@/services/api/bulkOperations';
import { BulkOperation, BulkOperationStatus, BulkOperationType } from '@/types/bulkOperations';
import BulkOperationProgress from './BulkOperationProgress';

const BulkOperationHistory: React.FC = () => {
  const [selectedOperation, setSelectedOperation] = useState<BulkOperation | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [showProgress, setShowProgress] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [activeTab, setActiveTab] = useState<BulkOperationStatus | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const queryClient = useQueryClient();

  // Fetch operations
  const { data: operations, isLoading, refetch } = useQuery({
    queryKey: ['bulk-operations', activeTab, searchQuery, page, rowsPerPage],
    queryFn: () => bulkOperationsService.getBulkOperations({
      status: activeTab === 'all' ? undefined : activeTab,
      search: searchQuery || undefined,
      limit: rowsPerPage,
      offset: page * rowsPerPage,
    }),
  });

  // Cancel operation
  const cancelOperation = useMutation({
    mutationFn: (id: string) => bulkOperationsService.cancelBulkOperation(id),
    onSuccess: () => {
      toast.success('Operation cancelled');
      queryClient.invalidateQueries({ queryKey: ['bulk-operations'] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to cancel operation');
    },
  });

  // Retry operation
  const retryOperation = useMutation({
    mutationFn: (id: string) => bulkOperationsService.retryBulkOperation(id),
    onSuccess: () => {
      toast.success('Operation restarted');
      queryClient.invalidateQueries({ queryKey: ['bulk-operations'] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to retry operation');
    },
  });

  // Download results
  const downloadResults = async (operation: BulkOperation) => {
    try {
      const blob = await bulkOperationsService.downloadBulkOperationResults(operation.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = `bulk-operation-${operation.id}-results.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success('Results downloaded');
    } catch (error: any) {
      toast.error('Failed to download results');
    }
  };

  const handleMenuClick = (event: React.MouseEvent<HTMLElement>, operation: BulkOperation) => {
    setAnchorEl(event.currentTarget);
    setSelectedOperation(operation);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const getStatusIcon = (status: BulkOperationStatus) => {
    switch (status) {
      case BulkOperationStatus.COMPLETED:
        return <SuccessIcon color="success" />;
      case BulkOperationStatus.FAILED:
        return <ErrorIcon color="error" />;
      case BulkOperationStatus.IN_PROGRESS:
      case BulkOperationStatus.PROCESSING:
        return <LinearProgress sx={{ width: 20, height: 20 }} />;
      case BulkOperationStatus.PENDING:
        return <PendingIcon color="action" />;
      case BulkOperationStatus.CANCELLED:
        return <CancelIcon color="action" />;
      case BulkOperationStatus.PARTIALLY_COMPLETED:
        return <WarningIcon color="warning" />;
      default:
        return null;
    }
  };

  const getStatusChip = (status: BulkOperationStatus) => {
    const statusConfig = {
      [BulkOperationStatus.COMPLETED]: { color: 'success' as const, label: 'Completed' },
      [BulkOperationStatus.FAILED]: { color: 'error' as const, label: 'Failed' },
      [BulkOperationStatus.IN_PROGRESS]: { color: 'primary' as const, label: 'In Progress' },
      [BulkOperationStatus.PROCESSING]: { color: 'primary' as const, label: 'Processing' },
      [BulkOperationStatus.PENDING]: { color: 'default' as const, label: 'Pending' },
      [BulkOperationStatus.CANCELLED]: { color: 'default' as const, label: 'Cancelled' },
      [BulkOperationStatus.PARTIALLY_COMPLETED]: { color: 'warning' as const, label: 'Partial' },
    };

    const config = statusConfig[status] || { color: 'default' as const, label: status };
    return <Chip size="small" color={config.color} label={config.label} />;
  };

  const getOperationTypeLabel = (type: BulkOperationType) => {
    const labels = {
      [BulkOperationType.USER_CREATE]: 'Create Users',
      [BulkOperationType.USER_UPDATE]: 'Update Users',
      [BulkOperationType.USER_DELETE]: 'Delete Users',
      [BulkOperationType.USER_ACTIVATE]: 'Activate Users',
      [BulkOperationType.USER_DEACTIVATE]: 'Deactivate Users',
      [BulkOperationType.USER_EXPORT]: 'Export Users',
      [BulkOperationType.MESSAGE_SEND]: 'Send Messages',
      [BulkOperationType.MESSAGE_DELETE]: 'Delete Messages',
      [BulkOperationType.CONTENT_UPLOAD]: 'Upload Content',
      [BulkOperationType.CONTENT_DELETE]: 'Delete Content',
      [BulkOperationType.CONTENT_PUBLISH]: 'Publish Content',
      [BulkOperationType.ANALYTICS_EXPORT]: 'Export Analytics',
    };
    return labels[type] || type;
  };

  const handleChangePage = (event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const filteredOperations = operations?.items || [];
  const totalCount = operations?.total || 0;

  return (
    <Box>
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
            <Typography variant="h6">Operation History</Typography>
            <Box display="flex" gap={1}>
              <Button
                startIcon={<RefreshIcon />}
                onClick={() => refetch()}
                disabled={isLoading}
              >
                Refresh
              </Button>
            </Box>
          </Box>

          {/* Search and Filters */}
          <Box display="flex" gap={2} mb={3}>
            <TextField
              size="small"
              placeholder="Search operations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon />
                  </InputAdornment>
                ),
              }}
              sx={{ flexGrow: 1 }}
            />
          </Box>

          {/* Status Tabs */}
          <Tabs 
            value={activeTab} 
            onChange={(_, value) => {
              setActiveTab(value);
              setPage(0);
            }}
            sx={{ mb: 2 }}
          >
            <Tab label="All" value="all" />
            <Tab label="In Progress" value={BulkOperationStatus.IN_PROGRESS} />
            <Tab label="Completed" value={BulkOperationStatus.COMPLETED} />
            <Tab label="Failed" value={BulkOperationStatus.FAILED} />
            <Tab label="Cancelled" value={BulkOperationStatus.CANCELLED} />
          </Tabs>

          {/* Operations Table */}
          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Status</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Created</TableCell>
                  <TableCell>Progress</TableCell>
                  <TableCell>Completed</TableCell>
                  <TableCell>Notes</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={7} align="center">
                      <LinearProgress />
                    </TableCell>
                  </TableRow>
                ) : filteredOperations.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} align="center">
                      <Typography color="text.secondary">
                        No operations found
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredOperations.map((operation) => (
                    <TableRow key={operation.id}>
                      <TableCell>
                        <Box display="flex" alignItems="center" gap={1}>
                          {getStatusIcon(operation.status)}
                          {getStatusChip(operation.status)}
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {getOperationTypeLabel(operation.operation_type)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {format(new Date(operation.created_at), 'MMM d, yyyy HH:mm')}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Box display="flex" alignItems="center" gap={1}>
                          <Typography variant="body2">
                            {operation.progress_current}/{operation.progress_total}
                          </Typography>
                          {operation.progress_total > 0 && (
                            <LinearProgress
                              variant="determinate"
                              value={(operation.progress_current / operation.progress_total) * 100}
                              sx={{ width: 60, ml: 1 }}
                            />
                          )}
                        </Box>
                      </TableCell>
                      <TableCell>
                        {operation.completed_at && (
                          <Typography variant="body2">
                            {format(new Date(operation.completed_at), 'MMM d, yyyy HH:mm')}
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" noWrap sx={{ maxWidth: 200 }}>
                          {operation.notes}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <IconButton
                          size="small"
                          onClick={(e) => handleMenuClick(e, operation)}
                        >
                          <MoreIcon />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
            <TablePagination
              rowsPerPageOptions={[5, 10, 25, 50]}
              component="div"
              count={totalCount}
              rowsPerPage={rowsPerPage}
              page={page}
              onPageChange={handleChangePage}
              onRowsPerPageChange={handleChangeRowsPerPage}
            />
          </TableContainer>
        </CardContent>
      </Card>

      {/* Action Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem
          onClick={() => {
            setShowDetails(true);
            handleMenuClose();
          }}
        >
          <InfoIcon sx={{ mr: 1 }} fontSize="small" />
          View Details
        </MenuItem>
        {selectedOperation?.status === BulkOperationStatus.IN_PROGRESS && (
          <MenuItem
            onClick={() => {
              setShowProgress(true);
              handleMenuClose();
            }}
          >
            <InfoIcon sx={{ mr: 1 }} fontSize="small" />
            View Progress
          </MenuItem>
        )}
        {selectedOperation?.status === BulkOperationStatus.COMPLETED && (
          <MenuItem
            onClick={() => {
              if (selectedOperation) {
                downloadResults(selectedOperation);
              }
              handleMenuClose();
            }}
          >
            <DownloadIcon sx={{ mr: 1 }} fontSize="small" />
            Download Results
          </MenuItem>
        )}
        {(selectedOperation?.status === BulkOperationStatus.IN_PROGRESS ||
          selectedOperation?.status === BulkOperationStatus.PENDING) && (
          <MenuItem
            onClick={() => {
              if (selectedOperation) {
                cancelOperation.mutate(selectedOperation.id);
              }
              handleMenuClose();
            }}
          >
            <CancelIcon sx={{ mr: 1 }} fontSize="small" />
            Cancel
          </MenuItem>
        )}
        {selectedOperation?.status === BulkOperationStatus.FAILED && (
          <MenuItem
            onClick={() => {
              if (selectedOperation) {
                retryOperation.mutate(selectedOperation.id);
              }
              handleMenuClose();
            }}
          >
            <RetryIcon sx={{ mr: 1 }} fontSize="small" />
            Retry
          </MenuItem>
        )}
      </Menu>

      {/* Details Dialog */}
      <Dialog
        open={showDetails}
        onClose={() => setShowDetails(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Operation Details</DialogTitle>
        <DialogContent>
          {selectedOperation && (
            <Box>
              <Typography variant="subtitle2" gutterBottom>
                Operation ID
              </Typography>
              <Typography variant="body2" sx={{ mb: 2 }}>
                {selectedOperation.id}
              </Typography>

              <Typography variant="subtitle2" gutterBottom>
                Type
              </Typography>
              <Typography variant="body2" sx={{ mb: 2 }}>
                {getOperationTypeLabel(selectedOperation.operation_type)}
              </Typography>

              <Typography variant="subtitle2" gutterBottom>
                Status
              </Typography>
              <Box sx={{ mb: 2 }}>
                {getStatusChip(selectedOperation.status)}
              </Box>

              <Typography variant="subtitle2" gutterBottom>
                Created By
              </Typography>
              <Typography variant="body2" sx={{ mb: 2 }}>
                {selectedOperation.created_by}
              </Typography>

              <Typography variant="subtitle2" gutterBottom>
                Parameters
              </Typography>
              <Paper variant="outlined" sx={{ p: 2, mb: 2, bgcolor: 'background.default' }}>
                <pre style={{ margin: 0, fontSize: '0.875rem' }}>
                  {JSON.stringify(selectedOperation.operation_params, null, 2)}
                </pre>
              </Paper>

              {selectedOperation.error_message && (
                <>
                  <Typography variant="subtitle2" gutterBottom color="error">
                    Error Message
                  </Typography>
                  <Alert severity="error" sx={{ mb: 2 }}>
                    {selectedOperation.error_message}
                  </Alert>
                </>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowDetails(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Progress Dialog */}
      <Dialog
        open={showProgress}
        onClose={() => setShowProgress(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Operation Progress</DialogTitle>
        <DialogContent>
          {selectedOperation && (
            <BulkOperationProgress operationId={selectedOperation.id} />
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowProgress(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default BulkOperationHistory;