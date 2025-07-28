import React, { useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  LinearProgress,
  Chip,
  IconButton,
  Alert,
  Button,
  Collapse,
  Table,
  TableBody,
  TableCell,
  TableRow,
  Divider,
} from '@mui/material';
import {
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Cancel as CancelIcon,
  ExpandMore as ExpandIcon,
  ExpandLess as CollapseIcon,
  Refresh as RefreshIcon,
  Download as DownloadIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { bulkOperationsService } from '@/services/api/bulkOperations';
import { BulkOperationStatus } from '@/types/bulkOperations';

interface BulkOperationProgressProps {
  operationId: string;
  onComplete?: () => void;
  showDetails?: boolean;
}

const BulkOperationProgress: React.FC<BulkOperationProgressProps> = ({
  operationId,
  onComplete,
  showDetails = true,
}) => {
  const [expanded, setExpanded] = React.useState(false);
  const queryClient = useQueryClient();

  // Fetch operation details
  const { data: operation, isLoading } = useQuery({
    queryKey: ['bulk-operation', operationId],
    queryFn: () => bulkOperationsService.getBulkOperation(operationId),
    refetchInterval: (data) => {
      // Poll while operation is in progress
      if (data?.status === BulkOperationStatus.PROCESSING || 
          data?.status === BulkOperationStatus.VALIDATING) {
        return 1000; // Poll every second
      }
      return false;
    },
  });

  // Cancel operation
  const cancelOperation = useMutation({
    mutationFn: () => bulkOperationsService.cancelBulkOperation(operationId),
    onSuccess: () => {
      toast.success('Operation cancelled');
      queryClient.invalidateQueries({ queryKey: ['bulk-operation', operationId] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to cancel operation');
    },
  });

  // Retry operation
  const retryOperation = useMutation({
    mutationFn: () => bulkOperationsService.retryBulkOperation(operationId),
    onSuccess: () => {
      toast.success('Operation retry started');
      queryClient.invalidateQueries({ queryKey: ['bulk-operation', operationId] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to retry operation');
    },
  });

  useEffect(() => {
    if (operation && onComplete) {
      if (operation.status === BulkOperationStatus.COMPLETED || 
          operation.status === BulkOperationStatus.FAILED ||
          operation.status === BulkOperationStatus.CANCELLED) {
        onComplete();
      }
    }
  }, [operation, onComplete]);

  if (isLoading || !operation) {
    return (
      <Card>
        <CardContent>
          <LinearProgress />
        </CardContent>
      </Card>
    );
  }

  const getStatusColor = (status: BulkOperationStatus) => {
    switch (status) {
      case BulkOperationStatus.COMPLETED:
        return 'success';
      case BulkOperationStatus.FAILED:
        return 'error';
      case BulkOperationStatus.CANCELLED:
        return 'warning';
      case BulkOperationStatus.PROCESSING:
      case BulkOperationStatus.VALIDATING:
        return 'primary';
      default:
        return 'default';
    }
  };

  const getStatusIcon = (status: BulkOperationStatus) => {
    switch (status) {
      case BulkOperationStatus.COMPLETED:
        return <SuccessIcon />;
      case BulkOperationStatus.FAILED:
        return <ErrorIcon />;
      case BulkOperationStatus.CANCELLED:
        return <WarningIcon />;
      default:
        return null;
    }
  };

  const isInProgress = operation.status === BulkOperationStatus.PROCESSING || 
                      operation.status === BulkOperationStatus.VALIDATING;

  const canCancel = operation.status === BulkOperationStatus.PENDING || 
                   operation.status === BulkOperationStatus.SCHEDULED ||
                   operation.status === BulkOperationStatus.PROCESSING;

  const canRetry = operation.status === BulkOperationStatus.FAILED;

  return (
    <Card>
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Box display="flex" alignItems="center" gap={1}>
            <Typography variant="subtitle1">
              {operation.operation_type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
            </Typography>
            <Chip
              label={operation.status}
              size="small"
              color={getStatusColor(operation.status)}
              icon={getStatusIcon(operation.status)}
            />
          </Box>
          <Box display="flex" gap={1}>
            {canCancel && (
              <IconButton
                size="small"
                onClick={() => cancelOperation.mutate()}
                disabled={cancelOperation.isLoading}
              >
                <CancelIcon />
              </IconButton>
            )}
            {canRetry && (
              <IconButton
                size="small"
                onClick={() => retryOperation.mutate()}
                disabled={retryOperation.isLoading}
              >
                <RefreshIcon />
              </IconButton>
            )}
            {operation.result_url && (
              <IconButton
                size="small"
                onClick={() => window.open(operation.result_url, '_blank')}
              >
                <DownloadIcon />
              </IconButton>
            )}
            {showDetails && (
              <IconButton
                size="small"
                onClick={() => setExpanded(!expanded)}
              >
                {expanded ? <CollapseIcon /> : <ExpandIcon />}
              </IconButton>
            )}
          </Box>
        </Box>

        {/* Progress Bar */}
        {isInProgress && (
          <Box mb={2}>
            <Box display="flex" justifyContent="space-between" mb={0.5}>
              <Typography variant="caption" color="text.secondary">
                Progress
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {operation.progress_percentage}%
              </Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={operation.progress_percentage}
              sx={{ height: 8, borderRadius: 1 }}
            />
          </Box>
        )}

        {/* Summary Stats */}
        <Box display="flex" gap={3}>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Total Items
            </Typography>
            <Typography variant="h6">
              {operation.total_count}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Processed
            </Typography>
            <Typography variant="h6">
              {operation.processed_count}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Success
            </Typography>
            <Typography variant="h6" color="success.main">
              {operation.success_count}
            </Typography>
          </Box>
          {operation.failed_count > 0 && (
            <Box>
              <Typography variant="caption" color="text.secondary">
                Failed
              </Typography>
              <Typography variant="h6" color="error.main">
                {operation.failed_count}
              </Typography>
            </Box>
          )}
        </Box>

        {/* Error Message */}
        {operation.error_message && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {operation.error_message}
          </Alert>
        )}

        {/* Detailed Information */}
        {showDetails && (
          <Collapse in={expanded}>
            <Divider sx={{ my: 2 }} />
            <Table size="small">
              <TableBody>
                <TableRow>
                  <TableCell>Entity Type</TableCell>
                  <TableCell>{operation.entity_type}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Created</TableCell>
                  <TableCell>
                    {new Date(operation.created_at).toLocaleString()}
                  </TableCell>
                </TableRow>
                {operation.started_at && (
                  <TableRow>
                    <TableCell>Started</TableCell>
                    <TableCell>
                      {new Date(operation.started_at).toLocaleString()}
                    </TableCell>
                  </TableRow>
                )}
                {operation.completed_at && (
                  <TableRow>
                    <TableCell>Completed</TableCell>
                    <TableCell>
                      {new Date(operation.completed_at).toLocaleString()}
                    </TableCell>
                  </TableRow>
                )}
                {operation.notes && (
                  <TableRow>
                    <TableCell>Notes</TableCell>
                    <TableCell>{operation.notes}</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>

            {/* Failed Items */}
            {operation.failed_items && operation.failed_items.length > 0 && (
              <Box mt={2}>
                <Typography variant="subtitle2" gutterBottom>
                  Failed Items
                </Typography>
                <Alert severity="error" variant="outlined">
                  <ul style={{ margin: 0, paddingLeft: 20 }}>
                    {operation.failed_items.slice(0, 5).map((item, idx) => (
                      <li key={idx}>
                        {item.entity_id}: {item.error}
                      </li>
                    ))}
                    {operation.failed_items.length > 5 && (
                      <li>... and {operation.failed_items.length - 5} more</li>
                    )}
                  </ul>
                </Alert>
              </Box>
            )}
          </Collapse>
        )}
      </CardContent>
    </Card>
  );
};

export default BulkOperationProgress;