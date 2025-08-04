import React, { useState } from 'react';
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
  FormControlLabel,
  Checkbox,
  Alert,
  Divider,
} from '@mui/material';
import { PaymentMethodType } from '@/types/financial';

interface PaymentMethodFormProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: PaymentMethodFormData) => void;
  editData?: PaymentMethodFormData | null;
  loading?: boolean;
}

export interface PaymentMethodFormData {
  id?: number;
  method_type: PaymentMethodType;
  is_primary: boolean;
  is_active: boolean;
  nickname?: string;
  // Bank transfer
  bank_name?: string;
  account_holder_name?: string;
  account_number?: string;
  routing_number?: string;
  swift_code?: string;
  iban?: string;
  // PayPal
  paypal_email?: string;
  // Crypto
  crypto_currency?: string;
  crypto_address?: string;
  crypto_network?: string;
  // Settings
  minimum_payout?: number;
  processing_days?: number;
}

export const PaymentMethodForm: React.FC<PaymentMethodFormProps> = ({
  open,
  onClose,
  onSubmit,
  editData,
  loading = false,
}) => {
  const [formData, setFormData] = useState<PaymentMethodFormData>({
    method_type: editData?.method_type || PaymentMethodType.BANK_TRANSFER,
    is_primary: editData?.is_primary || false,
    is_active: editData?.is_active ?? true,
    nickname: editData?.nickname || '',
    bank_name: editData?.bank_name || '',
    account_holder_name: editData?.account_holder_name || '',
    account_number: editData?.account_number || '',
    routing_number: editData?.routing_number || '',
    swift_code: editData?.swift_code || '',
    iban: editData?.iban || '',
    paypal_email: editData?.paypal_email || '',
    crypto_currency: editData?.crypto_currency || 'USDT',
    crypto_address: editData?.crypto_address || '',
    crypto_network: editData?.crypto_network || 'ERC20',
    minimum_payout: editData?.minimum_payout || 100,
    processing_days: editData?.processing_days || 3,
  });

  const [errors, setErrors] = useState<Partial<Record<keyof PaymentMethodFormData, string>>>({});

  const validate = (): boolean => {
    const newErrors: Partial<Record<keyof PaymentMethodFormData, string>> = {};

    if (formData.method_type === PaymentMethodType.BANK_TRANSFER) {
      if (!formData.bank_name) {
        newErrors.bank_name = 'Bank name is required';
      }
      if (!formData.account_holder_name) {
        newErrors.account_holder_name = 'Account holder name is required';
      }
      if (!formData.account_number) {
        newErrors.account_number = 'Account number is required';
      }
      if (!formData.routing_number && !formData.iban) {
        newErrors.routing_number = 'Routing number or IBAN is required';
      }
    } else if (formData.method_type === PaymentMethodType.PAYPAL) {
      if (!formData.paypal_email) {
        newErrors.paypal_email = 'PayPal email is required';
      } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.paypal_email)) {
        newErrors.paypal_email = 'Invalid email format';
      }
    } else if (formData.method_type === PaymentMethodType.CRYPTO) {
      if (!formData.crypto_currency) {
        newErrors.crypto_currency = 'Cryptocurrency is required';
      }
      if (!formData.crypto_address) {
        newErrors.crypto_address = 'Wallet address is required';
      }
      if (!formData.crypto_network) {
        newErrors.crypto_network = 'Network is required';
      }
    }

    if (formData.minimum_payout && formData.minimum_payout < 0) {
      newErrors.minimum_payout = 'Minimum payout must be positive';
    }
    if (formData.processing_days && formData.processing_days < 0) {
      newErrors.processing_days = 'Processing days must be positive';
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
      method_type: PaymentMethodType.BANK_TRANSFER,
      is_primary: false,
      is_active: true,
      nickname: '',
      minimum_payout: 100,
      processing_days: 3,
    });
    setErrors({});
    onClose();
  };

  const renderMethodFields = () => {
    switch (formData.method_type) {
      case PaymentMethodType.BANK_TRANSFER:
        return (
          <>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Bank Name"
                value={formData.bank_name}
                onChange={(e) => setFormData({ ...formData, bank_name: e.target.value })}
                error={!!errors.bank_name}
                helperText={errors.bank_name}
                required
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Account Holder Name"
                value={formData.account_holder_name}
                onChange={(e) => setFormData({ ...formData, account_holder_name: e.target.value })}
                error={!!errors.account_holder_name}
                helperText={errors.account_holder_name}
                required
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Account Number"
                value={formData.account_number}
                onChange={(e) => setFormData({ ...formData, account_number: e.target.value })}
                error={!!errors.account_number}
                helperText={errors.account_number || 'Will be encrypted'}
                required
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Routing Number"
                value={formData.routing_number}
                onChange={(e) => setFormData({ ...formData, routing_number: e.target.value })}
                error={!!errors.routing_number}
                helperText={errors.routing_number || 'US banks only'}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="SWIFT/BIC Code"
                value={formData.swift_code}
                onChange={(e) => setFormData({ ...formData, swift_code: e.target.value })}
                helperText="For international transfers"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="IBAN"
                value={formData.iban}
                onChange={(e) => setFormData({ ...formData, iban: e.target.value })}
                helperText="International Bank Account Number"
              />
            </Grid>
          </>
        );

      case PaymentMethodType.PAYPAL:
        return (
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="PayPal Email"
              type="email"
              value={formData.paypal_email}
              onChange={(e) => setFormData({ ...formData, paypal_email: e.target.value })}
              error={!!errors.paypal_email}
              helperText={errors.paypal_email}
              required
            />
          </Grid>
        );

      case PaymentMethodType.CRYPTO:
        return (
          <>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth error={!!errors.crypto_currency}>
                <InputLabel>Cryptocurrency</InputLabel>
                <Select
                  value={formData.crypto_currency}
                  onChange={(e) => setFormData({ ...formData, crypto_currency: e.target.value })}
                  label="Cryptocurrency"
                >
                  <MenuItem value="USDT">USDT (Tether)</MenuItem>
                  <MenuItem value="USDC">USDC</MenuItem>
                  <MenuItem value="BTC">Bitcoin</MenuItem>
                  <MenuItem value="ETH">Ethereum</MenuItem>
                  <MenuItem value="BNB">BNB</MenuItem>
                  <MenuItem value="TRX">Tron</MenuItem>
                </Select>
                {errors.crypto_currency && (
                  <Typography variant="caption" color="error">
                    {errors.crypto_currency}
                  </Typography>
                )}
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth error={!!errors.crypto_network}>
                <InputLabel>Network</InputLabel>
                <Select
                  value={formData.crypto_network}
                  onChange={(e) => setFormData({ ...formData, crypto_network: e.target.value })}
                  label="Network"
                >
                  <MenuItem value="ERC20">ERC20 (Ethereum)</MenuItem>
                  <MenuItem value="TRC20">TRC20 (Tron)</MenuItem>
                  <MenuItem value="BEP20">BEP20 (BSC)</MenuItem>
                  <MenuItem value="Bitcoin">Bitcoin Network</MenuItem>
                  <MenuItem value="Polygon">Polygon</MenuItem>
                </Select>
                {errors.crypto_network && (
                  <Typography variant="caption" color="error">
                    {errors.crypto_network}
                  </Typography>
                )}
              </FormControl>
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Wallet Address"
                value={formData.crypto_address}
                onChange={(e) => setFormData({ ...formData, crypto_address: e.target.value })}
                error={!!errors.crypto_address}
                helperText={errors.crypto_address || 'Double-check for accuracy'}
                required
              />
            </Grid>
          </>
        );

      default:
        return null;
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>
        {editData ? 'Edit Payment Method' : 'Add Payment Method'}
      </DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 2 }}>
          <Grid container spacing={3}>
            {/* Method Type */}
            <Grid item xs={12}>
              <FormControl fullWidth>
                <InputLabel>Payment Method Type</InputLabel>
                <Select
                  value={formData.method_type}
                  onChange={(e) => setFormData({ ...formData, method_type: e.target.value as PaymentMethodType })}
                  label="Payment Method Type"
                  disabled={!!editData}
                >
                  <MenuItem value={PaymentMethodType.BANK_TRANSFER}>Bank Transfer</MenuItem>
                  <MenuItem value={PaymentMethodType.PAYPAL}>PayPal</MenuItem>
                  <MenuItem value={PaymentMethodType.CRYPTO}>Cryptocurrency</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            {/* Nickname */}
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Nickname (Optional)"
                value={formData.nickname}
                onChange={(e) => setFormData({ ...formData, nickname: e.target.value })}
                helperText="A friendly name to identify this payment method"
              />
            </Grid>

            <Grid item xs={12}>
              <Divider sx={{ my: 1 }} />
              <Typography variant="subtitle2" gutterBottom>
                Payment Details
              </Typography>
            </Grid>

            {/* Method-specific fields */}
            {renderMethodFields()}

            <Grid item xs={12}>
              <Divider sx={{ my: 1 }} />
              <Typography variant="subtitle2" gutterBottom>
                Settings
              </Typography>
            </Grid>

            {/* Settings */}
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Minimum Payout Amount"
                type="number"
                value={formData.minimum_payout}
                onChange={(e) => setFormData({ ...formData, minimum_payout: parseInt(e.target.value) || 0 })}
                error={!!errors.minimum_payout}
                helperText={errors.minimum_payout || 'Minimum amount for this payment method'}
                InputProps={{
                  startAdornment: '$',
                }}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Processing Time (Days)"
                type="number"
                value={formData.processing_days}
                onChange={(e) => setFormData({ ...formData, processing_days: parseInt(e.target.value) || 0 })}
                error={!!errors.processing_days}
                helperText={errors.processing_days || 'Expected processing time'}
              />
            </Grid>

            {/* Checkboxes */}
            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={formData.is_primary}
                    onChange={(e) => setFormData({ ...formData, is_primary: e.target.checked })}
                  />
                }
                label="Set as primary payment method"
              />
            </Grid>
            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={formData.is_active}
                    onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  />
                }
                label="Active (can receive payments)"
              />
            </Grid>
          </Grid>

          <Alert severity="info" sx={{ mt: 2 }}>
            All sensitive information is encrypted and stored securely. Only authorized personnel can access payment details.
          </Alert>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={loading}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={loading}
        >
          {editData ? 'Update' : 'Add'} Payment Method
        </Button>
      </DialogActions>
    </Dialog>
  );
};