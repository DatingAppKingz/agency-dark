import React, { useState } from 'react';
import {
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  Typography,
  IconButton,
  InputAdornment,
  Chip,
  FormHelperText,
  CircularProgress,
  Stack,
} from '@mui/material';
import {
  Visibility as ViewIcon,
  VisibilityOff as HideIcon,
  Close as CloseIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import { ApiKey, ApiKeyProvider, ApiKeyCreateRequest } from '@/types/apiKeys';
import { useCreateApiKey, useValidateApiKey, useProviderScopes } from '@/hooks/useApiKeys';

interface ApiKeyFormProps {
  onClose: () => void;
  editingKey?: ApiKey | null;
}

const ApiKeyForm: React.FC<ApiKeyFormProps> = ({ onClose, editingKey }) => {
  const [formData, setFormData] = useState<ApiKeyCreateRequest>({
    name: '',
    provider: ApiKeyProvider.INFLOW,
    key: '',
    scopes: [],
  });
  const [showKey, setShowKey] = useState(false);
  const [validationResult, setValidationResult] = useState<any>(null);
  const [isValidating, setIsValidating] = useState(false);

  const createKey = useCreateApiKey();
  const validateKey = useValidateApiKey();
  const { data: availableScopes } = useProviderScopes(formData.provider);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate before creating
    if (!validationResult?.valid) {
      await handleValidate();
      return;
    }

    await createKey.mutateAsync(formData);
    onClose();
  };

  const handleValidate = async () => {
    if (!formData.key || !formData.provider) return;
    
    setIsValidating(true);
    try {
      const result = await validateKey.mutateAsync({
        provider: formData.provider,
        key: formData.key,
      });
      setValidationResult(result);
      
      // Auto-populate scopes if available
      if (result.scopes) {
        setFormData(prev => ({ ...prev, scopes: result.scopes || [] }));
      }
    } catch (error) {
      setValidationResult({ valid: false, message: 'Invalid API key' });
    } finally {
      setIsValidating(false);
    }
  };

  const getProviderInfo = (provider: ApiKeyProvider) => {
    switch (provider) {
      case ApiKeyProvider.INFLOW:
        return {
          placeholder: 'inf_live_...',
          helpText: 'Your Inflow API key from the dashboard',
          docsUrl: 'https://docs.inflow.com/api-keys',
        };
      case ApiKeyProvider.ONLYFANS:
        return {
          placeholder: 'of_...',
          helpText: 'Your OnlyFans API key',
          docsUrl: 'https://docs.onlyfansapi.com',
        };
      case ApiKeyProvider.STRIPE:
        return {
          placeholder: 'sk_live_...',
          helpText: 'Your Stripe secret key',
          docsUrl: 'https://stripe.com/docs/keys',
        };
      case ApiKeyProvider.PAYPAL:
        return {
          placeholder: 'A21AAI...',
          helpText: 'Your PayPal API secret',
          docsUrl: 'https://developer.paypal.com/api/rest/',
        };
      default:
        return {
          placeholder: 'Enter your API key',
          helpText: 'Your API key for the custom provider',
          docsUrl: null,
        };
    }
  };

  const providerInfo = getProviderInfo(formData.provider);

  return (
    <>
      <DialogTitle>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">
            {editingKey ? 'Edit API Key' : 'Add API Key'}
          </Typography>
          <IconButton onClick={onClose} size="small">
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>
      
      <form onSubmit={handleSubmit}>
        <DialogContent>
          <Stack spacing={3}>
            <TextField
              label="Name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              fullWidth
              required
              placeholder="Production API Key"
              helperText="A descriptive name to identify this API key"
            />

            <FormControl fullWidth required>
              <InputLabel>Provider</InputLabel>
              <Select
                value={formData.provider}
                onChange={(e) => {
                  setFormData({ 
                    ...formData, 
                    provider: e.target.value as ApiKeyProvider,
                    scopes: [] // Reset scopes when provider changes
                  });
                  setValidationResult(null);
                }}
                label="Provider"
              >
                <MenuItem value={ApiKeyProvider.INFLOW}>Inflow</MenuItem>
                <MenuItem value={ApiKeyProvider.ONLYFANS}>OnlyFans</MenuItem>
                <MenuItem value={ApiKeyProvider.STRIPE}>Stripe</MenuItem>
                <MenuItem value={ApiKeyProvider.PAYPAL}>PayPal</MenuItem>
                <MenuItem value={ApiKeyProvider.CUSTOM}>Custom</MenuItem>
              </Select>
            </FormControl>

            <Box>
              <TextField
                label="API Key"
                type={showKey ? 'text' : 'password'}
                value={formData.key}
                onChange={(e) => {
                  setFormData({ ...formData, key: e.target.value });
                  setValidationResult(null);
                }}
                fullWidth
                required
                placeholder={providerInfo.placeholder}
                helperText={providerInfo.helpText}
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
                  ),
                }}
                onBlur={handleValidate}
              />
              {providerInfo.docsUrl && (
                <Box mt={1}>
                  <Button
                    size="small"
                    startIcon={<InfoIcon />}
                    href={providerInfo.docsUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    View Documentation
                  </Button>
                </Box>
              )}
            </Box>

            {isValidating && (
              <Box display="flex" alignItems="center" gap={1}>
                <CircularProgress size={20} />
                <Typography variant="body2">Validating API key...</Typography>
              </Box>
            )}

            {validationResult && (
              <Alert severity={validationResult.valid ? 'success' : 'error'}>
                {validationResult.message || 
                  (validationResult.valid ? 'API key is valid' : 'Invalid API key')
                }
                {validationResult.rate_limits && (
                  <Box mt={1}>
                    <Typography variant="caption" display="block">
                      Rate Limits: {validationResult.rate_limits.requests_per_minute}/min, 
                      {validationResult.rate_limits.requests_per_day}/day
                    </Typography>
                  </Box>
                )}
              </Alert>
            )}

            {availableScopes && availableScopes.length > 0 && (
              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  Permissions (Scopes)
                </Typography>
                <Box display="flex" flexWrap="wrap" gap={1}>
                  {availableScopes.map((scope) => (
                    <Chip
                      key={scope}
                      label={scope}
                      onClick={() => {
                        const isSelected = formData.scopes.includes(scope);
                        setFormData({
                          ...formData,
                          scopes: isSelected
                            ? formData.scopes.filter(s => s !== scope)
                            : [...formData.scopes, scope]
                        });
                      }}
                      color={formData.scopes.includes(scope) ? 'primary' : 'default'}
                      variant={formData.scopes.includes(scope) ? 'filled' : 'outlined'}
                    />
                  ))}
                </Box>
                <FormHelperText>
                  Select the permissions this API key should have
                </FormHelperText>
              </Box>
            )}

            <Alert severity="info" icon={<InfoIcon />}>
              <Typography variant="body2">
                API keys are encrypted and stored securely. You can rotate or revoke 
                them at any time from this dashboard.
              </Typography>
            </Alert>
          </Stack>
        </DialogContent>
        
        <DialogActions>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            type="submit"
            variant="contained"
            disabled={
              !formData.name || 
              !formData.key || 
              createKey.isPending ||
              isValidating
            }
          >
            {createKey.isPending ? 'Creating...' : 'Create API Key'}
          </Button>
        </DialogActions>
      </form>
    </>
  );
};

export default ApiKeyForm;
