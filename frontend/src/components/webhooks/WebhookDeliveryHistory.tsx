import React from 'react';
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
  Skeleton,
  Alert,
} from '@mui/material';
import { format } from 'date-fns';
import { useQuery } from '@tanstack/react-query';
import { webhookService } from '@/services/api/webhooks';
import { DeliveryStatus } from '@/types/webhooks';

interface WebhookDeliveryHistoryProps {
  webhookId: string;
}

const WebhookDeliveryHistory: React.FC<WebhookDeliveryHistoryProps> = ({ webhookId }) => {
  const { data: deliveries, isPending } = useQuery({
    queryKey: ['webhook-deliveries', webhookId],
    queryFn: () => webhookService.getWebhookDeliveries(webhookId),
    enabled: !!webhookId,
  });

  const getStatusColor = (status: DeliveryStatus): 'default' | 'primary' | 'success' | 'error' | 'warning' => {
    switch (status) {
      case DeliveryStatus.PENDING:
        return 'default';
      case DeliveryStatus.SUCCESS:
        return 'success';
      case DeliveryStatus.FAILED:
        return 'error';
      case DeliveryStatus.RETRYING:
        return 'warning';
      default:
        return 'default';
    }
  };

  const formatResponseTime = (ms?: number) => {
    if (!ms) return '-';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Delivery History
        </Typography>

        {isPending ? (
          <Box>
            {[...Array(3)].map((_, i) => (
              <Skeleton key={i} height={60} sx={{ my: 1 }} />
            ))}
          </Box>
        ) : deliveries && deliveries.length > 0 ? (
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Event</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Response</TableCell>
                  <TableCell>Time</TableCell>
                  <TableCell>Attempts</TableCell>
                  <TableCell>Delivered At</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {deliveries.map((delivery) => (
                  <TableRow key={delivery.id}>
                    <TableCell>
                      <Box>
                        <Typography variant="body2">{delivery.event_type}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          {delivery.event_id}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={delivery.status}
                        size="small"
                        color={getStatusColor(delivery.status)}
                      />
                    </TableCell>
                    <TableCell>
                      {delivery.response_status_code ? (
                        <Chip
                          label={delivery.response_status_code}
                          size="small"
                          color={
                            delivery.response_status_code >= 200 && delivery.response_status_code < 300
                              ? 'success'
                              : 'error'
                          }
                        />
                      ) : delivery.error_message ? (
                        <Typography variant="caption" color="error">
                          {delivery.error_message.substring(0, 50)}...
                        </Typography>
                      ) : (
                        '-'
                      )}
                    </TableCell>
                    <TableCell>{formatResponseTime(delivery.response_time_ms)}</TableCell>
                    <TableCell>{delivery.attempts}</TableCell>
                    <TableCell>
                      {delivery.delivered_at ? (
                        <Typography variant="body2">
                          {format(new Date(delivery.delivered_at), 'MMM d, HH:mm:ss')}
                        </Typography>
                      ) : (
                        '-'
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        ) : (
          <Alert severity="info">No delivery history available</Alert>
        )}
      </CardContent>
    </Card>
  );
};

export default WebhookDeliveryHistory;
