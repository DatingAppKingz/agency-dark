import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Box,
  Typography,
  Alert,
  InputAdornment,
  IconButton,
  Stepper,
  Step,
  StepLabel,
  StepContent,
  Paper } from '@mui/material';
import {
  Visibility as ViewIcon,
  VisibilityOff as HideIcon,
  ContentCopy as CopyIcon,
  Warning as WarningIcon,
  CheckCircle as CheckIcon } from '@mui/icons-material';
import { ApiKey } from '@/types/apiKeys';
import { useRotateApiKey, useValidateApiKey } from '@/hooks/useApiKeys';
import { toast } from 'react-hot-toast';

interface ApiKeyRotateDialogProps {
  open: boolean;
  onClose: () => void;
  apiKey: ApiKey;
}

const ApiKeyRotateDialog: React.FC<ApiKeyRotateDialogProps> = ({
  open,
  onClose,
  apiKey }) => {
  const [activeStep, setActiveStep] = useState(0);
  const [newKey, setNewKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [setIsValidated] = useState(false);
  const [confirmText, setConfirmText] = useState('');

  const rotateKey = useRotateApiKey();
  const validateKey = useValidateApiKey();

  const handleValidateNewKey = async () => {
    try {
      const result = await validateKey.mutateAsync({
        provider: apiKey.provider,
        key: newKey });
      
      if (result.valid) {
        setIsValidated(true);
        setActiveStep(1);
      } else {
        toast.error('Invalid API key. Please check and try again.');
      }
    } catch (error) {
      toast.error('Failed to validate API key');
    }
  };

  const handleRotate = async () => {
    if (confirmText !== apiKey.name) {
      toast.error('Please type the API key name correctly to confirm');
      return;
    }

    try {
      await rotateKey.mutateAsync({
        id: apiKey.id,
        data: { new_key: newKey } });
      setActiveStep(2);
    } catch (error) {
      // Error is handled by the hook
    }
  };

  const handleCopyKey = () => {
    if (apiKey.key_prefix) {
      navigator.clipboard.writeText(apiKey.key_prefix + '...');
      toast.success('Key prefix copied to clipboard');
    }
  };

  const handleClose = () => {
    setActiveStep(0);
    setNewKey('');
    setShowKey(false);
    setIsValidated(false);
    setConfirmText('');
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box display="flex" alignItems="center" gap={1}>
          <WarningIcon color="warning" />
          <Typography variant="h6">Rotate API Key</Typography>
        </Box>
      </DialogTitle>
      
      <DialogContent>
        <Alert severity="warning" sx={{ mb: 3 }}>
          <Typography variant="body2">
            Rotating this API key will invalidate the current key. Make sure to update 
            your integrations with the new key immediately to avoid service disruption.
          </Typography>
        </Alert>

        <Box mb={3}>
          <Typography variant="subtitle2" gutterBottom>Current API Key</Typography>
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Box display="flex" justifyContent="space-between" alignItems="center">
              <Typography variant="body2" fontFamily="monospace">
                {apiKey.name} ({apiKey.key_prefix}...)
              </Typography>
              <IconButton size="small" onClick={handleCopyKey}>
                <CopyIcon fontSize="small" />
              </IconButton>
            </Box>
          </Paper>
        </Box>

        <Stepper activeStep={activeStep} orientation="vertical">
          <Step>
            <StepLabel>Enter New API Key</StepLabel>
            <StepContent>
              <TextField
                label="New API Key"
                type={showKey ? 'text' : 'password'}
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                fullWidth
                required
                placeholder={`New ${apiKey.provider} API key`}
                sx={{ mt: 2, mb: 2 }}
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        onClick={() => setShowKey(!showKey)}
                        edge="end"
                      >
                        {showKey ? <HideIcon /> : <ViewIcon />}
                      </IconButton>
                    </InputAdornment>
                  ) }}
              />
              <Button
                variant="contained"
                onClick={handleValidateNewKey}
                disabled={!newKey || validateKey.isPending}
              >
                {validateKey.isPending ? 'Validating...' : 'Validate & Continue'}
              </Button>
            </StepContent>
          </Step>

          <Step>
            <StepLabel>Confirm Rotation</StepLabel>
            <StepContent>
              <Alert severity="error" sx={{ mb: 2 }}>
                <Typography variant="body2">
                  This action cannot be undone. The current API key will be 
                  permanently invalidated.
                </Typography>
              </Alert>
              
              <Typography variant="body2" gutterBottom>
                Type <strong>{apiKey.name}</strong> to confirm:
              </Typography>
              
              <TextField
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                fullWidth
                placeholder={apiKey.name}
                sx={{ mt: 1, mb: 2 }}
              />
              
              <Box display="flex" gap={1}>
                <Button
                  variant="contained"
                  color="error"
                  onClick={handleRotate}
                  disabled={
                    confirmText !== apiKey.name || 
                    rotateKey.isPending
                  }
                >
                  {rotateKey.isPending ? 'Rotating...' : 'Rotate API Key'}
                </Button>
                <Button onClick={() => setActiveStep(0)}>Back</Button>
              </Box>
            </StepContent>
          </Step>

          <Step>
            <StepLabel>Rotation Complete</StepLabel>
            <StepContent>
              <Alert severity="success" icon={<CheckIcon />} sx={{ mb: 2 }}>
                <Typography variant="body2">
                  API key has been successfully rotated. The old key is no longer valid.
                </Typography>
              </Alert>
              
              <Typography variant="body2" color="text.secondary">
                Make sure to update all your integrations with the new API key.
              </Typography>
            </StepContent>
          </Step>
        </Stepper>
      </DialogContent>
      
      <DialogActions>
        {activeStep < 2 && <Button onClick={handleClose}>Cancel</Button>}
        {activeStep === 2 && (
          <Button variant="contained" onClick={handleClose}>
            Done
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};

export default ApiKeyRotateDialog;
