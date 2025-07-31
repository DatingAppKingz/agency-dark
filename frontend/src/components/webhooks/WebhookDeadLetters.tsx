import React, { useState } from 'react';
import {
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Button,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tooltip,
  Alert,
  Skeleton,
  TablePagination } from '@mui/material';
import {
  Refresh as RefreshIcon,
  Delete as DeleteIcon,
  Visibility as ViewIcon,
  PlayArrow as ReprocessIcon } from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { format } from 'date-fns';
import { webhookService } from '@/services/api/webhooks';
import { WebhookDeadLetter } from '@/types/webhooks';

const WebhookDeadLetters: React.FC = () => {
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [selectedDeadLetter, setSelectedDeadLetter] = useState<WebhookDeadLetter | null>(null);
  const [showPayloadDialog, setShowPayloadDialog] = useState(false);

  const queryClient = useQueryClient();

  // Fetch dead letters
  const { data, isPending, refetch } = useQuery({
    queryKey: ['webhook-dead-letters', page, rowsPerPage],
    queryFn: () => webhookService.getDeadLetters({
      limit: rowsPerPage,
      offset: page * rowsPerPage }) });

  // Reprocess mutation
  const reprocessDeadLetter = useMutation({
    mutationFn: webhookService.reprocessDeadLetter,
    onSuccess: () => {
      toast.success('Dead letter reprocessed successfully');
      queryClient.invalidateQueries({ queryKey: ['webhook-dead-letters'] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to reprocess dead letter');
    } });

  // Delete mutation
  const deleteDeadLetter = useMutation({
    mutationFn: webhookService.deleteDeadLetter,
    onSuccess: () => {
      toast.success('Dead letter deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['webhook-dead-letters'] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to delete dead letter');
    } });

  const handleReprocess = (deadLetterId: string) => {
    if (window.confirm('Are you sure you want to reprocess this webhook?')) {
      reprocessDeadLetter.mutate(deadLetterId);
    }
  };

  const handleDelete = (deadLetterId: string) => {
    if (window.confirm('Are you sure you want to delete this dead letter?')) {
      deleteDeadLetter.mutate(deadLetterId);
    }
  };

  const formatErrorSummary = (error: string) => {
    if (error.length > 100) {
      return error.substring(0, 100) + '...';
    }
    return error;
  };

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h6">Dead Letter Queue</Typography>
          <Typography variant="body2" color="text.secondary">
            Failed webhooks that couldn't be delivered after all retry attempts
          </Typography>
        </Box>
        <Button
          startIcon={<RefreshIcon />}
          onClick={() => refetch()}
          disabled={isPending}
        >
          Refresh
        </Button>
      </Box>

      {/* Info Alert */}
      <Alert severity="info" sx={{ mb: 3 }}>
        <Typography variant="body2">
          Webhooks in the dead letter queue have failed all retry attempts. You can:
          <ul style={{ margin: '8px 0 0 0', paddingLeft: '20px' }}>
            <li>Reprocess them manually if the issue has been resolved</li>
            <li>View the payload to understand what failed</li>
            <li>Delete them if they're no longer needed</li>
          </ul>
          Dead letters are automatically deleted after 90 days.
        </Typography>
      </Alert>

      {/* Dead Letters Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Event Type</TableCell>
              <TableCell>Failed At</TableCell>
              <TableCell>Attempts</TableCell>
              <TableCell>Error</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isPending ? (
              [...Array(5)].map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton /></TableCell>
                  <TableCell><Skeleton /></TableCell>
                  <TableCell><Skeleton /></TableCell>
                  <TableCell><Skeleton /></TableCell>
                  <TableCell><Skeleton /></TableCell>
                  <TableCell><Skeleton /></TableCell>
                </TableRow>
              ))
            ) : data && data.items.length > 0 ? (
              data.items.map((deadLetter) => (
                <TableRow key={deadLetter.id}>
                  <TableCell>
                    <Box>
                      <Typography variant="body2">{deadLetter.event_type}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        ID: {deadLetter.event_id}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Tooltip title={format(new Date(deadLetter.last_attempt_at), 'PPpp')}>
                      <Typography variant="body2">
                        {format(new Date(deadLetter.last_attempt_at), 'MMM d, HH:mm')}
                      </Typography>
                    </Tooltip>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">{deadLetter.total_attempts}</Typography>
                  </TableCell>
                  <TableCell>
                    <Tooltip title={deadLetter.error_summary}>
                      <Typography variant="body2" sx={{ maxWidth: 300 }}>
                        {formatErrorSummary(deadLetter.error_summary)}
                      </Typography>
                    </Tooltip>
                  </TableCell>
                  <TableCell>
                    {deadLetter.is_reprocessed ? (
                      <Chip label="Reprocessed" size="small" color="success" />
                    ) : (
                      <Chip label="Failed" size="small" color="error" />
                    )}
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="View Payload">
                      <IconButton
                        size="small"
                        onClick={() => {
                          setSelectedDeadLetter(deadLetter);
                          setShowPayloadDialog(true);
                        }}
                      >
                        <ViewIcon />
                      </IconButton>
                    </Tooltip>
                    {!deadLetter.is_reprocessed && (
                      <Tooltip title="Reprocess">
                        <IconButton
                          size="small"
                          onClick={() => handleReprocess(deadLetter.id)}
                          disabled={reprocessDeadLetter.isPending}
                        >
                          <ReprocessIcon />
                        </IconButton>
                      </Tooltip>
                    )}
                    <Tooltip title="Delete">
                      <IconButton
                        size="small"
                        onClick={() => handleDelete(deadLetter.id)}
                        disabled={deleteDeadLetter.isPending}
                      >
                        <DeleteIcon />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  <Typography variant="body2" color="text.secondary" sx={{ py: 3 }}>
                    No dead letters found
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
        
        {data && data.total > 0 && (
          <TablePagination
            rowsPerPageOptions={[10, 25, 50, 100]}
            component="div"
            count={data.total}
            rowsPerPage={rowsPerPage}
            page={page}
            onPageChange={(_, newPage) => setPage(newPage)}
            onRowsPerPageChange={(e) => {
              setRowsPerPage(parseInt(e.target.value, 10));
              setPage(0);
            }}
          />
        )}
      </TableContainer>

      {/* Payload Dialog */}
      <Dialog
        open={showPayloadDialog}
        onClose={() => {
          setShowPayloadDialog(false);
          setSelectedDeadLetter(null);
        }}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Webhook Payload Details</DialogTitle>
        <DialogContent>
          {selectedDeadLetter && (
            <Box>
              <Typography variant="subtitle2" gutterBottom>
                Event Information
              </Typography>
              <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
                <Typography variant="body2">
                  <strong>Event Type:</strong> {selectedDeadLetter.event_type}
                </Typography>
                <Typography variant="body2">
                  <strong>Event ID:</strong> {selectedDeadLetter.event_id}
                </Typography>
                <Typography variant="body2">
                  <strong>First Attempt:</strong> {format(new Date(selectedDeadLetter.first_attempt_at), 'PPpp')}
                </Typography>
                <Typography variant="body2">
                  <strong>Last Attempt:</strong> {format(new Date(selectedDeadLetter.last_attempt_at), 'PPpp')}
                </Typography>
                <Typography variant="body2">
                  <strong>Total Attempts:</strong> {selectedDeadLetter.total_attempts}
                </Typography>
                {selectedDeadLetter.final_status_code && (
                  <Typography variant="body2">
                    <strong>Final Status Code:</strong> {selectedDeadLetter.final_status_code}
                  </Typography>
                )}
              </Paper>

              <Typography variant="subtitle2" gutterBottom>
                Error Details
              </Typography>
              <Paper variant="outlined" sx={{ p: 2, mb: 2, bgcolor: 'error.50' }}>
                <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                  {selectedDeadLetter.error_summary}
                </Typography>
              </Paper>

              <Typography variant="subtitle2" gutterBottom>
                Payload
              </Typography>
              <Paper variant="outlined" sx={{ p: 2, bgcolor: 'grey.50' }}>
                <pre style={{ margin: 0, overflow: 'auto' }}>
                  {JSON.stringify(selectedDeadLetter.payload, null, 2)}
                </pre>
              </Paper>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => {
            setShowPayloadDialog(false);
            setSelectedDeadLetter(null);
          }}>
            Close
          </Button>
          {selectedDeadLetter && !selectedDeadLetter.is_reprocessed && (
            <Button
              variant="contained"
              onClick={() => {
                handleReprocess(selectedDeadLetter.id);
                setShowPayloadDialog(false);
                setSelectedDeadLetter(null);
              }}
            >
              Reprocess
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default WebhookDeadLetters;
