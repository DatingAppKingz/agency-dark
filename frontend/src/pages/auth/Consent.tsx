/**
 * OAuth Consent Screen
 * Displays requested permissions and handles user consent
 */

import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Box,
  Container,
  Paper,
  Typography,
  Button,
  Checkbox,
  FormControlLabel,
  FormGroup,
  Divider,
  Alert,
  Avatar,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Stack,
  Chip,
  Link,
  Card,
  CardContent,
} from '@mui/material';
import {
  Security as SecurityIcon,
  AccountCircle as AccountIcon,
  Email as EmailIcon,
  Business as BusinessIcon,
  Storage as StorageIcon,
  Settings as SettingsIcon,
  VpnKey as VpnKeyIcon,
  Check as CheckIcon,
  Close as CloseIcon,
  Info as InfoIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';

// Scope definitions with descriptions and icons
const SCOPE_DEFINITIONS: Record<string, { name: string; description: string; icon: React.ElementType; required?: boolean }> = {
  'openid': {
    name: 'Basic Profile',
    description: 'Your basic account information',
    icon: AccountIcon,
    required: true,
  },
  'email': {
    name: 'Email Address',
    description: 'Your email address',
    icon: EmailIcon,
    required: true,
  },
  'profile': {
    name: 'Profile Information',
    description: 'Your profile details including name and picture',
    icon: AccountIcon,
  },
  'read': {
    name: 'Read Access',
    description: 'View your data and content',
    icon: StorageIcon,
  },
  'write': {
    name: 'Write Access',
    description: 'Create and modify your data',
    icon: StorageIcon,
  },
  'admin': {
    name: 'Admin Access',
    description: 'Full administrative permissions',
    icon: SettingsIcon,
  },
  'agency': {
    name: 'Agency Access',
    description: 'Access to your agency information',
    icon: BusinessIcon,
  },
  'api': {
    name: 'API Access',
    description: 'Programmatic access to your account',
    icon: VpnKeyIcon,
  },
};

// Client information interface
interface ClientInfo {
  client_id: string;
  client_name: string;
  client_uri?: string;
  logo_uri?: string;
  privacy_policy_uri?: string;
  terms_of_service_uri?: string;
  contacts?: string[];
}

/**
 * OAuth Consent Screen Component
 */
const Consent: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  
  // Extract parameters
  const clientId = searchParams.get('client_id') || '';
  const redirectUri = searchParams.get('redirect_uri') || '';
  const state = searchParams.get('state') || '';
  const scopeParam = searchParams.get('scope') || 'openid email profile';
  const responseType = searchParams.get('response_type') || 'code';
  const codeChallenge = searchParams.get('code_challenge') || '';
  const codeChallengeMethod = searchParams.get('code_challenge_method') || '';
  
  // Component state
  const [clientInfo, setClientInfo] = useState<ClientInfo | null>(null);
  const [requestedScopes, setRequestedScopes] = useState<string[]>([]);
  const [approvedScopes, setApprovedScopes] = useState<Set<string>>(new Set());
  const [rememberConsent, setRememberConsent] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Initialize component
   */
  useEffect(() => {
    // Parse scopes
    const scopes = scopeParam.split(' ').filter(Boolean);
    setRequestedScopes(scopes);
    
    // Set initial approved scopes (required ones)
    const required = new Set(
      scopes.filter(scope => SCOPE_DEFINITIONS[scope]?.required)
    );
    setApprovedScopes(required);
    
    // Fetch client information (mock for now)
    fetchClientInfo(clientId);
  }, [clientId, scopeParam]);

  /**
   * Fetch client information
   */
  const fetchClientInfo = async (clientId: string) => {
    // In production, this would fetch from the backend
    // Mock data for demonstration
    setClientInfo({
      client_id: clientId,
      client_name: 'Demo Application',
      client_uri: 'https://demo.example.com',
      logo_uri: 'https://via.placeholder.com/80',
      privacy_policy_uri: 'https://demo.example.com/privacy',
      terms_of_service_uri: 'https://demo.example.com/terms',
      contacts: ['support@demo.example.com'],
    });
  };

  /**
   * Handle scope toggle
   */
  const handleScopeToggle = (scope: string) => {
    // Don't allow toggling required scopes
    if (SCOPE_DEFINITIONS[scope]?.required) {
      return;
    }
    
    setApprovedScopes(prev => {
      const newSet = new Set(prev);
      if (newSet.has(scope)) {
        newSet.delete(scope);
      } else {
        newSet.add(scope);
      }
      return newSet;
    });
  };

  /**
   * Handle approve
   */
  const handleApprove = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      // Build consent response
      const consentParams = new URLSearchParams({
        client_id: clientId,
        redirect_uri: redirectUri,
        state: state,
        scope: Array.from(approvedScopes).join(' '),
        response_type: responseType,
        approved: 'true',
        remember: rememberConsent.toString(),
      });
      
      if (codeChallenge) {
        consentParams.append('code_challenge', codeChallenge);
        consentParams.append('code_challenge_method', codeChallengeMethod);
      }
      
      // Submit consent (in production, this would POST to the backend)
      // For now, redirect with approval
      const authorizationUrl = `/api/v1/oauth/authorize?${consentParams.toString()}`;
      window.location.href = authorizationUrl;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Consent submission failed';
      setError(message);
      setIsLoading(false);
    }
  };

  /**
   * Handle deny
   */
  const handleDeny = () => {
    // Redirect back with error
    const errorParams = new URLSearchParams({
      error: 'access_denied',
      error_description: 'User denied the consent request',
      state: state,
    });
    
    window.location.href = `${redirectUri}?${errorParams.toString()}`;
  };

  return (
    <Container component="main" maxWidth="md">
      <Box
        sx={{
          marginTop: 4,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
        }}
      >
        <Paper
          elevation={3}
          sx={{
            padding: 4,
            width: '100%',
          }}
        >
          {/* Header */}
          <Box textAlign="center" mb={4}>
            <Typography component="h1" variant="h4" gutterBottom>
              Authorization Request
            </Typography>
            <Typography variant="body1" color="text.secondary">
              Review and approve the permissions requested by the application
            </Typography>
          </Box>

          {/* Error Alert */}
          {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          )}

          {/* Client Information */}
          {clientInfo && (
            <Card sx={{ mb: 4, bgcolor: 'background.default' }}>
              <CardContent>
                <Box display="flex" alignItems="center" mb={2}>
                  <Avatar
                    src={clientInfo.logo_uri}
                    alt={clientInfo.client_name}
                    sx={{ width: 60, height: 60, mr: 2 }}
                  >
                    {clientInfo.client_name[0]}
                  </Avatar>
                  <Box flex={1}>
                    <Typography variant="h6">
                      {clientInfo.client_name}
                    </Typography>
                    {clientInfo.client_uri && (
                      <Link
                        href={clientInfo.client_uri}
                        target="_blank"
                        rel="noopener noreferrer"
                        color="primary"
                        underline="hover"
                      >
                        {clientInfo.client_uri}
                      </Link>
                    )}
                  </Box>
                </Box>
                
                <Typography variant="body2" color="text.secondary" paragraph>
                  This application is requesting access to your Agency Dark account.
                </Typography>
                
                <Stack direction="row" spacing={2}>
                  {clientInfo.privacy_policy_uri && (
                    <Link
                      href={clientInfo.privacy_policy_uri}
                      target="_blank"
                      rel="noopener noreferrer"
                      variant="body2"
                    >
                      Privacy Policy
                    </Link>
                  )}
                  {clientInfo.terms_of_service_uri && (
                    <Link
                      href={clientInfo.terms_of_service_uri}
                      target="_blank"
                      rel="noopener noreferrer"
                      variant="body2"
                    >
                      Terms of Service
                    </Link>
                  )}
                </Stack>
              </CardContent>
            </Card>
          )}

          {/* Requested Permissions */}
          <Box mb={4}>
            <Typography variant="h6" gutterBottom>
              <SecurityIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
              Requested Permissions
            </Typography>
            
            <Alert severity="info" icon={<InfoIcon />} sx={{ mb: 2 }}>
              This application will be able to:
            </Alert>
            
            <List>
              {requestedScopes.map((scope) => {
                const scopeInfo = SCOPE_DEFINITIONS[scope] || {
                  name: scope,
                  description: `Access to ${scope}`,
                  icon: VpnKeyIcon,
                };
                const Icon = scopeInfo.icon;
                const isRequired = scopeInfo.required;
                const isApproved = approvedScopes.has(scope);
                
                return (
                  <ListItem
                    key={scope}
                    sx={{
                      bgcolor: isApproved ? 'action.selected' : 'transparent',
                      borderRadius: 1,
                      mb: 1,
                    }}
                  >
                    <ListItemIcon>
                      <Icon color={isApproved ? 'primary' : 'disabled'} />
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <Box display="flex" alignItems="center" gap={1}>
                          {scopeInfo.name}
                          {isRequired && (
                            <Chip label="Required" size="small" color="primary" />
                          )}
                        </Box>
                      }
                      secondary={scopeInfo.description}
                    />
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={isApproved}
                          onChange={() => handleScopeToggle(scope)}
                          disabled={isRequired || isLoading}
                        />
                      }
                      label=""
                    />
                  </ListItem>
                );
              })}
            </List>
          </Box>

          <Divider sx={{ my: 3 }} />

          {/* Remember Consent */}
          <FormGroup sx={{ mb: 3 }}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={rememberConsent}
                  onChange={(e) => setRememberConsent(e.target.checked)}
                  disabled={isLoading}
                />
              }
              label={
                <Typography variant="body2">
                  Remember my decision for this application
                </Typography>
              }
            />
          </FormGroup>

          {/* Warning */}
          <Alert severity="warning" icon={<WarningIcon />} sx={{ mb: 3 }}>
            <Typography variant="body2">
              By approving, you allow this application to access your information
              and perform actions on your behalf. You can revoke access at any time
              from your account settings.
            </Typography>
          </Alert>

          {/* Actions */}
          <Stack direction="row" spacing={2} justifyContent="center">
            <Button
              variant="contained"
              color="primary"
              size="large"
              startIcon={<CheckIcon />}
              onClick={handleApprove}
              disabled={isLoading || approvedScopes.size === 0}
              sx={{ minWidth: 150 }}
            >
              Approve
            </Button>
            <Button
              variant="outlined"
              color="inherit"
              size="large"
              startIcon={<CloseIcon />}
              onClick={handleDeny}
              disabled={isLoading}
              sx={{ minWidth: 150 }}
            >
              Deny
            </Button>
          </Stack>
        </Paper>

        {/* Footer */}
        <Typography
          variant="body2"
          color="text.secondary"
          align="center"
          sx={{ mt: 4 }}
        >
          Secure OAuth 2.0 Authorization • Agency Dark
        </Typography>
      </Box>
    </Container>
  );
};

export default Consent;