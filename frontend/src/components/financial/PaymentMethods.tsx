import React, { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Button,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
  CircularProgress,
  Divider } from '@mui/material';
import {
  Add,
  Delete,
  Edit,
  StarBorder,
  AccountBalance,
  CreditCard,
  Currency as Bitcoin } from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { financialApi } from '@/services/api/financial';
import type { PaymentMethod, BankDetails, PayPalDetails, CryptoWalletDetails } from '@/types/financial';

const bankDetailsSchema = z.object({
  account_holder: z.string().min(1, 'Account holder name is required'),
  account_number: z.string().min(1, 'Account number is required'),
  routing_number: z.string().optional(),
  bank_name: z.string().min(1, 'Bank name is required'),
  swift_code: z.string().optional(),
  iban: z.string().optional() });

const paypalDetailsSchema = z.object({
  email: z.string().email('Valid email is required') });

const cryptoDetailsSchema = z.object({
  currency: z.string().min(1, 'Currency is required'),
  address: z.string().min(1, 'Wallet address is required'),
  network: z.string().optional() });

const paymentMethodSchema = z.object({
  type: z.enum(['bank_account', 'paypal', 'crypto_wallet']),
  is_default: z.boolean().optional() });

type PaymentMethodForm = z.infer<typeof paymentMethodSchema> & {
  bank_details?: z.infer<typeof bankDetailsSchema>;
  paypal_details?: z.infer<typeof paypalDetailsSchema>;
  crypto_details?: z.infer<typeof cryptoDetailsSchema>;
};

export const PaymentMethods = () => {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingMethod, setEditingMethod] = useState<PaymentMethod | null>(null);
  const [formType, setFormType] = useState<PaymentMethod['type']>('bank_account');

  const { register, handleSubmit, formState: { errors }, reset, watch } = useForm<PaymentMethodForm>({
    resolver: zodResolver(paymentMethodSchema),
    defaultValues: {
      type: 'bank_account',
      is_default: false } });

  const type = watch('type');

  const { data: paymentMethods, isPending } = useQuery({
    queryKey: ['payment-methods'],
    queryFn: () => financialApi.getPaymentMethods() });

  const createMutation = useMutation({
    mutationFn: financialApi.createPaymentMethod,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payment-methods'] });
      handleCloseDialog();
    } });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<PaymentMethod> }) =>
      financialApi.updatePaymentMethod(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payment-methods'] });
      handleCloseDialog();
    } });

  const deleteMutation = useMutation({
    mutationFn: financialApi.deletePaymentMethod,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payment-methods'] });
    } });

  const setDefaultMutation = useMutation({
    mutationFn: financialApi.setDefaultPaymentMethod,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payment-methods'] });
    } });

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditingMethod(null);
    reset();
  };

  const handleEdit = (method: PaymentMethod) => {
    setEditingMethod(method);
    setFormType(method.type);
    reset({
      type: method.type,
      is_default: method.is_default });
    setDialogOpen(true);
  };

  const handleDelete = (id: string) => {
    if (window.confirm('Are you sure you want to delete this payment method?')) {
      deleteMutation.mutate(id);
    }
  };

  const onSubmit = (data: PaymentMethodForm) => {
    const payload: any = {
      type: data.type,
      is_default: data.is_default,
      details: {} };

    switch (data.type) {
      case 'bank_account':
        payload.details = data.bank_details;
        break;
      case 'paypal':
        payload.details = data.paypal_details;
        break;
      case 'crypto_wallet':
        payload.details = data.crypto_details;
        break;
    }

    if (editingMethod) {
      updateMutation.mutate({ id: editingMethod.id, data: payload });
    } else {
      createMutation.mutate(payload);
    }
  };

  const getMethodIcon = (type: PaymentMethod['type']) => {
    switch (type) {
      case 'bank_account':
        return <AccountBalance />;
      case 'paypal':
        return <CreditCard />;
      case 'crypto_wallet':
        return <Bitcoin />;
      default:
        return null;
    }
  };

  const getMethodDetails = (method: PaymentMethod) => { switch (method.type) {
      case 'bank_account':
        const bank = method.details as BankDetails;
        return `${bank.bank_name } - ****${bank.account_number.slice(-4)}`;
      case 'paypal':
        const paypal = method.details as PayPalDetails;
        return paypal.email;
      case 'crypto_wallet':
        const crypto = method.details as CryptoWalletDetails;
        return `${crypto.currency} - ${crypto.address.slice(0, 6)}...${crypto.address.slice(-4)}`;
      default:
        return '';
    }
  };

  if (isPending) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight={300}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5">Payment Methods</Typography>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={() => setDialogOpen(true)}
        >
          Add Payment Method
        </Button>
      </Box>

      <Card>
        <CardContent>
          {paymentMethods?.length === 0 ? (
            <Box textAlign="center" py={4}>
              <Typography variant="body1" color="textSecondary" gutterBottom>
                No payment methods added yet
              </Typography>
              <Button
                variant="outlined"
                startIcon={<Add />}
                onClick={() => setDialogOpen(true)}
                sx={{ mt: 2 }}
              >
                Add Your First Payment Method
              </Button>
            </Box>
          ) : (
            <List>
              {paymentMethods?.map((method, index) => (
                <React.Fragment key={method.id}>
                  {index > 0 && <Divider />}
                  <ListItem>
                    <Box display="flex" alignItems="center" gap={2} flex={1}>
                      <Box
                        sx={{
                          backgroundColor: 'action.hover',
                          borderRadius: 2,
                          p: 1,
                          display: 'flex',
                          alignItems: 'center' }}
                      >
                        {getMethodIcon(method.type)}
                      </Box>
                      <ListItemText
                        primary={
                          <Box display="flex" alignItems="center" gap={1}>
                            <Typography variant="body1">
                              {method.type.replace('_', ' ').toUpperCase()}
                            </Typography>
                            {method.is_default && (
                              <Chip label="Default" size="small" color="primary" />
                            )}
                          </Box>
                        }
                        secondary={getMethodDetails(method)}
                      />
                    </Box>
                    <ListItemSecondaryAction>
                      {!method.is_default && (
                        <IconButton
                          edge="end"
                          onClick={() => setDefaultMutation.mutate(method.id)}
                          disabled={setDefaultMutation.isPending}
                        >
                          <StarBorder />
                        </IconButton>
                      )}
                      <IconButton edge="end" onClick={() => handleEdit(method)}>
                        <Edit />
                      </IconButton>
                      <IconButton
                        edge="end"
                        onClick={() => handleDelete(method.id)}
                        disabled={deleteMutation.isPending}
                      >
                        <Delete />
                      </IconButton>
                    </ListItemSecondaryAction>
                  </ListItem>
                </React.Fragment>
              ))}
            </List>
          )}
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogTitle>
            {editingMethod ? 'Edit Payment Method' : 'Add Payment Method'}
          </DialogTitle>
          <DialogContent>
            <Box display="flex" flexDirection="column" gap={2} pt={1}>
              {!editingMethod && (
                <TextField
                  select
                  label="Payment Method Type"
                  fullWidth
                  {...register('type')}
                  error={!!errors.type}
                  helperText={errors.type?.message}
                  onChange={ (e) => setFormType(e.target.value as PaymentMethod['type']) }
                >
                  <MenuItem value="bank_account">Bank Account</MenuItem>
                  <MenuItem value="paypal">PayPal</MenuItem>
                  <MenuItem value="crypto_wallet">Crypto Wallet</MenuItem>
                </TextField>
              )}

              {formType === 'bank_account' && (
                <>
                  <TextField
                    label="Account Holder Name"
                    fullWidth
                    {...register('bank_details.account_holder')}
                    error={!!errors.bank_details?.account_holder}
                    helperText={errors.bank_details?.account_holder?.message}
                  />
                  <TextField
                    label="Bank Name"
                    fullWidth
                    {...register('bank_details.bank_name')}
                    error={!!errors.bank_details?.bank_name}
                    helperText={errors.bank_details?.bank_name?.message}
                  />
                  <TextField
                    label="Account Number"
                    fullWidth
                    {...register('bank_details.account_number')}
                    error={!!errors.bank_details?.account_number}
                    helperText={errors.bank_details?.account_number?.message}
                  />
                  <TextField
                    label="Routing Number (Optional)"
                    fullWidth
                    {...register('bank_details.routing_number')}
                  />
                  <TextField
                    label="SWIFT Code (Optional)"
                    fullWidth
                    {...register('bank_details.swift_code')}
                  />
                  <TextField
                    label="IBAN (Optional)"
                    fullWidth
                    {...register('bank_details.iban')}
                  />
                </>
              )}

              {formType === 'paypal' && (
                <TextField
                  label="PayPal Email"
                  type="email"
                  fullWidth
                  {...register('paypal_details.email')}
                  error={!!errors.paypal_details?.email}
                  helperText={errors.paypal_details?.email?.message}
                />
              )}

              {formType === 'crypto_wallet' && (
                <>
                  <TextField
                    select
                    label="Currency"
                    fullWidth
                    {...register('crypto_details.currency')}
                    error={!!errors.crypto_details?.currency}
                    helperText={errors.crypto_details?.currency?.message}
                  >
                    <MenuItem value="BTC">Bitcoin (BTC)</MenuItem>
                    <MenuItem value="ETH">Ethereum (ETH)</MenuItem>
                    <MenuItem value="USDT">Tether (USDT)</MenuItem>
                    <MenuItem value="USDC">USD Coin (USDC)</MenuItem>
                  </TextField>
                  <TextField
                    label="Wallet Address"
                    fullWidth
                    {...register('crypto_details.address')}
                    error={!!errors.crypto_details?.address}
                    helperText={errors.crypto_details?.address?.message}
                  />
                  <TextField
                    label="Network (Optional)"
                    fullWidth
                    {...register('crypto_details.network')}
                    helperText="e.g., ERC-20, TRC-20"
                  />
                </>
              )}
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleCloseDialog}>Cancel</Button>
            <Button
              type="submit"
              variant="contained"
              disabled={createMutation.isPending || updateMutation.isPending}
            >
              {editingMethod ? 'Update' : 'Add'} Payment Method
            </Button>
          </DialogActions>
        </form>
      </Dialog>
    </Box>
  );
};
