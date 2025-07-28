import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Timeline,
  TimelineItem,
  TimelineSeparator,
  TimelineConnector,
  TimelineContent,
  TimelineDot,
  TimelineOppositeContent,
  Chip,
  Alert,
  Skeleton,
  IconButton,
  Tooltip,
  Paper,
} from '@mui/material';
import {
  Add as CreateIcon,
  Visibility as ViewIcon,
  Edit as UpdateIcon,
  RotateRight as RotateIcon,
  Delete as DeleteIcon,
  PlayArrow as UseIcon,
  Error as FailIcon,
  ContentCopy as CopyIcon,
} from '@mui/icons-material';
import { format, formatDistanceToNow } from 'date-fns';
import { ApiKey, ApiKeyAction, ApiKeyAuditLog } from '@/types/apiKeys';
import { useApiKeyAuditLogs } from '@/hooks/useApiKeys';
import { toast } from 'react-hot-toast';

interface ApiKeyAuditDialogProps {
  open: boolean;
  onClose: () => void;
  apiKey: ApiKey;
}

const ApiKeyAuditDialog: React.FC<ApiKeyAuditDialogProps> = ({
  open,
  onClose,
  apiKey,
}) => {
  const { data: logs, isLoading, error } = useApiKeyAuditLogs(apiKey.id);

  const getActionIcon = (action: ApiKeyAction) => {
    switch (action) {
      case ApiKeyAction.CREATED:
        return <CreateIcon />;
      case ApiKeyAction.VIEWED:
        return <ViewIcon />;
      case ApiKeyAction.UPDATED:
        return <UpdateIcon />;
      case ApiKeyAction.ROTATED:
        return <RotateIcon />;
      case ApiKeyAction.DELETED:
        return <DeleteIcon />;
      case ApiKeyAction.USED:
        return <UseIcon />;
      case ApiKeyAction.FAILED:
        return <FailIcon />;
      default:
        return null;
    }
  };

  const getActionColor = (action: ApiKeyAction): 'primary' | 'secondary' | 'error' | 'warning' | 'info' | 'success' => {
    switch (action) {
      case ApiKeyAction.CREATED:
        return 'success';
      case ApiKeyAction.VIEWED:
        return 'info';
      case ApiKeyAction.UPDATED:
        return 'primary';
      case ApiKeyAction.ROTATED:
        return 'warning';
      case ApiKeyAction.DELETED:
        return 'error';
      case ApiKeyAction.USED:
        return 'secondary';
      case ApiKeyAction.FAILED:
        return 'error';
      default:
        return 'primary';
    }
  };

  const getActionDescription = (log: ApiKeyAuditLog): string => {
    switch (log.action) {
      case ApiKeyAction.CREATED:
        return `API key created by ${log.user_email}`;
      case ApiKeyAction.VIEWED:
        return `API key details viewed by ${log.user_email}`;
      case ApiKeyAction.UPDATED:
        return `API key updated by ${log.user_email}`;
      case ApiKeyAction.ROTATED:
        return `API key rotated by ${log.user_email}`;
      case ApiKeyAction.DELETED:
        return `API key deleted by ${log.user_email}`;
      case ApiKeyAction.USED:
        return `API key used successfully`;
      case ApiKeyAction.FAILED:
        return `API key usage failed: ${log.metadata?.error || 'Unknown error'}`;
      default:
        return `${log.action} by ${log.user_email}`;
    }
  };

  const handleCopyDetails = (log: ApiKeyAuditLog) => {
    const details = `
Action: ${log.action}
User: ${log.user_email}
IP: ${log.ip_address}
Time: ${format(new Date(log.created_at), 'PPpp')}
User Agent: ${log.user_agent}
Metadata: ${JSON.stringify(log.metadata, null, 2)}
`;
    navigator.clipboard.writeText(details);
    toast.success('Audit details copied to clipboard');
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">Audit Logs - {apiKey.name}</Typography>
          <Chip label={apiKey.provider} size="small" color="primary" />
        </Box>
      </DialogTitle>
      
      <DialogContent>
        {isLoading && (
          <Box>
            {[1, 2, 3, 4, 5].map((i) => (
              <Box key={i} mb={2}>
                <Skeleton variant="rectangular" height={60} />
              </Box>
            ))}
          </Box>
        )}

        {error && (
          <Alert severity="error">
            Failed to load audit logs. Please try again later.
          </Alert>
        )}

        {logs && logs.length === 0 && (
          <Alert severity="info">
            No audit logs found for this API key.
          </Alert>
        )}

        {logs && logs.length > 0 && (
          <Timeline position="alternate">
            {logs.map((log, index) => (
              <TimelineItem key={log.id}>
                <TimelineOppositeContent
                  sx={{ m: 'auto 0' }}
                  align={index % 2 === 0 ? 'right' : 'left'}
                  variant="body2"
                  color="text.secondary"
                >
                  <Typography variant="caption" display="block">
                    {format(new Date(log.created_at), 'MMM dd, yyyy')}
                  </Typography>
                  <Typography variant="caption">
                    {format(new Date(log.created_at), 'HH:mm:ss')}
                  </Typography>
                </TimelineOppositeContent>
                
                <TimelineSeparator>
                  <TimelineConnector sx={{ bgcolor: 'grey.300' }} />
                  <TimelineDot color={getActionColor(log.action)}>
                    {getActionIcon(log.action)}
                  </TimelineDot>
                  <TimelineConnector sx={{ bgcolor: 'grey.300' }} />
                </TimelineSeparator>
                
                <TimelineContent sx={{ py: '12px', px: 2 }}>
                  <Paper elevation={2} sx={{ p: 2 }}>
                    <Box display="flex" justifyContent="space-between" alignItems="flex-start">
                      <Box flex={1}>
                        <Typography variant="subtitle2" gutterBottom>
                          {getActionDescription(log)}
                        </Typography>
                        
                        <Box display="flex" gap={1} flexWrap="wrap" mt={1}>
                          <Chip
                            label={log.action}
                            size="small"
                            color={getActionColor(log.action)}
                          />
                          <Chip
                            label={log.ip_address}
                            size="small"
                            variant="outlined"
                          />
                        </Box>
                        
                        {log.metadata && Object.keys(log.metadata).length > 0 && (
                          <Box mt={1}>
                            <Typography variant="caption" color="text.secondary">
                              Additional details available
                            </Typography>
                          </Box>
                        )}
                        
                        <Typography variant="caption" color="text.secondary" display="block" mt={1}>
                          {formatDistanceToNow(new Date(log.created_at), { addSuffix: true })}
                        </Typography>
                      </Box>
                      
                      <Tooltip title="Copy audit details">
                        <IconButton
                          size="small"
                          onClick={() => handleCopyDetails(log)}
                        >
                          <CopyIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </Paper>
                </TimelineContent>
              </TimelineItem>
            ))}
          </Timeline>
        )}
      </DialogContent>
      
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

export default ApiKeyAuditDialog;