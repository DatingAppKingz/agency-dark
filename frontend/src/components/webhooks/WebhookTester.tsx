import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Button,
  Alert,
  Paper,
  Divider,
  Grid,
  Chip,
} from '@mui/material';
import { Send as SendIcon } from '@mui/icons-material';
import { useMutation } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { webhookService } from '@/services/api/webhooks';
import { WebhookEvent, WebhookResponse } from '@/types/webhooks';

interface WebhookTesterProps {
  webhooks: WebhookResponse[];
}

const WebhookTester: React.FC<WebhookTesterProps> = ({ webhooks }) => {
  const [selectedWebhook, setSelectedWebhook] = useState<string>('');
  const [selectedEvent, setSelectedEvent] = useState<WebhookEvent | ''>('');
  const [customPayload, setCustomPayload] = useState<string>('');
  const [testResult, setTestResult] = useState<any>(null);

  // Test webhook mutation
  const testWebhook = useMutation({
    mutationFn: ({ webhookId, event, payload }: { webhookId: string; event?: WebhookEvent; payload?: any }) => {
      if (event && payload) {
        return webhookService.sendTestWebhook(webhookId, { 
          event, 
          event_id: `test_${Date.now()}`,
          timestamp: new Date().toISOString(),
          data: payload || {}
        });
      }
      return webhookService.testWebhook(webhookId);
    },
    onSuccess: (data) => {
      toast.success('Test webhook sent successfully');
      setTestResult(data);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to send test webhook');
      setTestResult({
        success: false,
        error: error.response?.data?.detail || error.message,
      });
    },
  });

  const selectedWebhookData = webhooks.find(w => w.id === selectedWebhook);

  const getDefaultPayload = (event: WebhookEvent) => {
    const basePayload = {
      event,
      event_id: `test_${Date.now()}`,
      timestamp: new Date().toISOString(),
    };

    switch (event) {
      case WebhookEvent.MESSAGE_RECEIVED:
        return {
          ...basePayload,
          data: {
            message_id: '123e4567-e89b-12d3-a456-426614174000',
            model_id: '123e4567-e89b-12d3-a456-426614174001',
            fan_id: '123e4567-e89b-12d3-a456-426614174002',
            content: 'Test message from webhook tester',
            sender: 'fan',
            created_at: new Date().toISOString(),
          },
        };
      case WebhookEvent.FAN_SUBSCRIBED:
        return {
          ...basePayload,
          data: {
            fan_id: '123e4567-e89b-12d3-a456-426614174000',
            model_id: '123e4567-e89b-12d3-a456-426614174001',
            username: 'test_fan',
            subscription_status: 'active',
            subscription_price: 9.99,
            created_at: new Date().toISOString(),
          },
        };
      case WebhookEvent.PAYMENT_RECEIVED:
        return {
          ...basePayload,
          data: {
            payment_id: '123e4567-e89b-12d3-a456-426614174000',
            model_id: '123e4567-e89b-12d3-a456-426614174001',
            fan_id: '123e4567-e89b-12d3-a456-426614174002',
            amount: 50.00,
            currency: 'USD',
            payment_type: 'tip',
            status: 'completed',
            created_at: new Date().toISOString(),
          },
        };
      default:
        return {
          ...basePayload,
          data: {
            test: true,
            message: 'This is a test webhook',
          },
        };
    }
  };

  const handleSendTest = () => {
    if (!selectedWebhook) {
      toast.error('Please select a webhook');
      return;
    }

    if (customPayload) {
      try {
        const payload = JSON.parse(customPayload);
        testWebhook.mutate({ webhookId: selectedWebhook, event: selectedEvent || undefined, payload });
      } catch (error) {
        toast.error('Invalid JSON payload');
      }
    } else if (selectedEvent) {
      const payload = getDefaultPayload(selectedEvent);
      testWebhook.mutate({ webhookId: selectedWebhook, event: selectedEvent, payload });
    } else {
      testWebhook.mutate({ webhookId: selectedWebhook });
    }
  };

  const handleEventChange = (event: WebhookEvent | '') => {
    setSelectedEvent(event);
    if (event) {
      setCustomPayload(JSON.stringify(getDefaultPayload(event), null, 2));
    } else {
      setCustomPayload('');
    }
  };

  return (
    <Box>
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Test Configuration
              </Typography>
              
              <Box display="flex" flexDirection="column" gap={2}>
                <FormControl fullWidth>
                  <InputLabel>Select Webhook</InputLabel>
                  <Select
                    value={selectedWebhook}
                    onChange={(e) => setSelectedWebhook(e.target.value)}
                    label="Select Webhook"
                  >
                    {webhooks.map((webhook) => (
                      <MenuItem key={webhook.id} value={webhook.id}>
                        <Box>
                          <Typography variant="body2">{webhook.url}</Typography>
                          {webhook.description && (
                            <Typography variant="caption" color="text.secondary">
                              {webhook.description}
                            </Typography>
                          )}
                        </Box>
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                {selectedWebhookData && (
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Subscribed Events:
                    </Typography>
                    <Box display="flex" gap={0.5} flexWrap="wrap" mt={0.5}>
                      {selectedWebhookData.events.map((event) => (
                        <Chip key={event} label={event} size="small" />
                      ))}
                    </Box>
                  </Box>
                )}

                <FormControl fullWidth>
                  <InputLabel>Event Type (Optional)</InputLabel>
                  <Select
                    value={selectedEvent}
                    onChange={(e) => handleEventChange(e.target.value as WebhookEvent | '')}
                    label="Event Type (Optional)"
                  >
                    <MenuItem value="">
                      <em>Default Test Event</em>
                    </MenuItem>
                    {selectedWebhookData?.events.map((event) => (
                      <MenuItem key={event} value={event}>
                        {event}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                <TextField
                  label="Custom Payload (JSON)"
                  multiline
                  rows={10}
                  value={customPayload}
                  onChange={(e) => setCustomPayload(e.target.value)}
                  fullWidth
                  helperText="Leave empty to use default test payload"
                />

                <Button
                  variant="contained"
                  startIcon={<SendIcon />}
                  onClick={handleSendTest}
                  disabled={!selectedWebhook || testWebhook.isPending}
                  fullWidth
                >
                  Send Test Webhook
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Test Result
              </Typography>
              
              {testResult ? (
                <Box>
                  {testResult.success ? (
                    <Alert severity="success" sx={{ mb: 2 }}>
                      Test webhook sent successfully!
                    </Alert>
                  ) : (
                    <Alert severity="error" sx={{ mb: 2 }}>
                      Test failed: {testResult.error}
                    </Alert>
                  )}
                  
                  {testResult.response_time_ms && (
                    <Typography variant="body2" gutterBottom>
                      <strong>Response Time:</strong> {testResult.response_time_ms}ms
                    </Typography>
                  )}
                  
                  {testResult.status_code && (
                    <Typography variant="body2" gutterBottom>
                      <strong>Status Code:</strong> {testResult.status_code}
                    </Typography>
                  )}
                  
                  {testResult.response && (
                    <>
                      <Divider sx={{ my: 2 }} />
                      <Typography variant="subtitle2" gutterBottom>
                        Response:
                      </Typography>
                      <Paper variant="outlined" sx={{ p: 2, bgcolor: 'grey.50' }}>
                        <pre style={{ margin: 0, overflow: 'auto' }}>
                          {JSON.stringify(testResult.response, null, 2)}
                        </pre>
                      </Paper>
                    </>
                  )}
                </Box>
              ) : (
                <Alert severity="info">
                  Select a webhook and send a test to see the result here
                </Alert>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default WebhookTester;
