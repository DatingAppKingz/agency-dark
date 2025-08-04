import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Grid,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  Box,
  Alert,
  InputAdornment,
  CircularProgress,
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { format, startOfMonth, endOfMonth } from 'date-fns';
import { useModels } from '@/hooks/useModels';
import { usePaymentMethods } from '@/hooks/usePaymentMethods';
import { ModelProfile } from '@/types/models';
import { PaymentMethod } from '@/types/financial';

interface PayoutFormProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: PayoutFormData) => void;
  modelId?: number;
  loading?: boolean;
}

export interface PayoutFormData {
  model_id: number;
  period_start: string;
  period_end: string;
  payment_method_id: number;
  adjustments: number;
  notes?: string;
  scheduled_date?: string;
}

export const PayoutForm: React.FC<PayoutFormProps> = ({
  open,
  onClose,
  onSubmit,
  modelId,
  loading = false,
}) => {
  const { data: models = [] } = useModels();
  const [selectedModelId, setSelectedModelId] = useState<number | ''>(modelId || '');
  const { data: paymentMethods = [] } = usePaymentMethods(selectedModelId || undefined);
  
  const [formData, setFormData] = useState<PayoutFormData>({
    model_id: modelId || 0,
    period_start: format(startOfMonth(new Date()), 'yyyy-MM-dd'),
    period_end: format(endOfMonth(new Date()), 'yyyy-MM-dd'),
    payment_method_id: 0,
    adjustments: 0,
    notes: '',
    scheduled_date: format(new Date(), 'yyyy-MM-dd'),
  });

  const [errors, setErrors] = useState<Partial<Record<keyof PayoutFormData, string>>>({});

  useEffect(() => {
    if (modelId) {
      setSelectedModelId(modelId);
      setFormData(prev => ({ ...prev, model_id: modelId }));
    }
  }, [modelId]);

  useEffect(() => {
    // Reset payment method when model changes
    setFormData(prev => ({ ...prev, payment_method_id: 0 }));
  }, [selectedModelId]);

  const handleModelChange = (value: number) => {
    setSelectedModelId(value);
    setFormData(prev => ({ ...prev, model_id: value }));
  };

  const validate = (): boolean => {
    const newErrors: Partial<Record<keyof PayoutFormData, string>> = {};

    if (!formData.model_id) {
      newErrors.model_id = 'Model is required';
    }
    if (!formData.payment_method_id) {
      newErrors.payment_method_id = 'Payment method is required';
    }
    if (!formData.period_start) {
      newErrors.period_start = 'Period start is required';
    }
    if (!formData.period_end) {
      newErrors.period_end = 'Period end is required';
    }
    if (new Date(formData.period_start) > new Date(formData.period_end)) {
      newErrors.period_end = 'End date must be after start date';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = () => {
    if (validate()) {
      onSubmit(formData);
    }
  };

  const handleClose = () => {
    setFormData({
      model_id: modelId || 0,
      period_start: format(startOfMonth(new Date()), 'yyyy-MM-dd'),
      period_end: format(endOfMonth(new Date()), 'yyyy-MM-dd'),
      payment_method_id: 0,
      adjustments: 0,
      notes: '',
      scheduled_date: format(new Date(), 'yyyy-MM-dd'),
    });
    setErrors({});
    onClose();
  };

  const activePaymentMethods = paymentMethods.filter(pm => pm.is_active);

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>Create Payout</DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 2 }}>
          <Grid container spacing={3}>
            {/* Model Selection */}
            <Grid item xs={12}>
              <FormControl fullWidth error={!!errors.model_id}>
                <InputLabel>Model</InputLabel>
                <Select
                  value={selectedModelId}
                  onChange={(e) => handleModelChange(e.target.value as number)}
                  label="Model"
                  disabled={!!modelId}
                >
                  {models.map((model: ModelProfile) => (
                    <MenuItem key={model.id} value={model.id}>
                      {model.stage_name} ({model.first_name} {model.last_name})
                    </MenuItem>
                  ))}
                </Select>
                {errors.model_id && (
                  <Typography variant="caption" color="error">
                    {errors.model_id}
                  </Typography>
                )}
              </FormControl>
            </Grid>

            {/* Period Selection */}
            <Grid item xs={12} sm={6}>
              <LocalizationProvider dateAdapter={AdapterDateFns}>
                <DatePicker
                  label="Period Start"
                  value={new Date(formData.period_start)}
                  onChange={(date) => {
                    if (date) {
                      setFormData(prev => ({
                        ...prev,
                        period_start: format(date, 'yyyy-MM-dd'),
                      }));
                    }
                  }}
                  slotProps={{
                    textField: {
                      fullWidth: true,
                      error: !!errors.period_start,
                      helperText: errors.period_start,
                    },
                  }}
                />
              </LocalizationProvider>
            </Grid>

            <Grid item xs={12} sm={6}>
              <LocalizationProvider dateAdapter={AdapterDateFns}>
                <DatePicker
                  label="Period End"
                  value={new Date(formData.period_end)}
                  onChange={(date) => {
                    if (date) {
                      setFormData(prev => ({
                        ...prev,
                        period_end: format(date, 'yyyy-MM-dd'),
                      }));
                    }
                  }}
                  slotProps={{
                    textField: {
                      fullWidth: true,
                      error: !!errors.period_end,
                      helperText: errors.period_end,
                    },
                  }}
                />
              </LocalizationProvider>
            </Grid>

            {/* Payment Method */}
            <Grid item xs={12}>
              <FormControl fullWidth error={!!errors.payment_method_id}>
                <InputLabel>Payment Method</InputLabel>
                <Select
                  value={formData.payment_method_id || ''}
                  onChange={(e) => setFormData(prev => ({
                    ...prev,
                    payment_method_id: e.target.value as number,
                  }))}
                  label="Payment Method"
                  disabled={!selectedModelId || activePaymentMethods.length === 0}
                >
                  {activePaymentMethods.map((method: PaymentMethod) => (
                    <MenuItem key={method.id} value={method.id}>
                      {method.nickname || method.display_name} 
                      {method.is_primary && ' (Primary)'}
                    </MenuItem>
                  ))}
                </Select>
                {errors.payment_method_id && (
                  <Typography variant="caption" color="error">
                    {errors.payment_method_id}
                  </Typography>
                )}
                {selectedModelId && activePaymentMethods.length === 0 && (
                  <Typography variant="caption" color="textSecondary">
                    No payment methods found for this model
                  </Typography>
                )}
              </FormControl>
            </Grid>

            {/* Adjustments */}
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Adjustments"
                type="number"
                value={formData.adjustments}
                onChange={(e) => setFormData(prev => ({
                  ...prev,
                  adjustments: parseFloat(e.target.value) || 0,
                }))}
                InputProps={{
                  startAdornment: <InputAdornment position="start">$</InputAdornment>,
                }}
                helperText="Positive for additions, negative for deductions"
              />
            </Grid>

            {/* Scheduled Date */}
            <Grid item xs={12} sm={6}>
              <LocalizationProvider dateAdapter={AdapterDateFns}>
                <DatePicker
                  label="Scheduled Date"
                  value={formData.scheduled_date ? new Date(formData.scheduled_date) : null}
                  onChange={(date) => {
                    if (date) {
                      setFormData(prev => ({
                        ...prev,
                        scheduled_date: format(date, 'yyyy-MM-dd'),
                      }));
                    }
                  }}
                  slotProps={{
                    textField: {
                      fullWidth: true,
                    },
                  }}
                />
              </LocalizationProvider>
            </Grid>

            {/* Notes */}
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Notes"
                multiline
                rows={3}
                value={formData.notes}
                onChange={(e) => setFormData(prev => ({
                  ...prev,
                  notes: e.target.value,
                }))}
                placeholder="Optional notes about this payout"
              />
            </Grid>
          </Grid>

          {selectedModelId && activePaymentMethods.length === 0 && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              This model has no active payment methods. Please add a payment method before creating a payout.
            </Alert>
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={loading}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={loading || (selectedModelId && activePaymentMethods.length === 0)}
          startIcon={loading && <CircularProgress size={20} />}
        >
          Create Payout
        </Button>
      </DialogActions>
    </Dialog>
  );
};