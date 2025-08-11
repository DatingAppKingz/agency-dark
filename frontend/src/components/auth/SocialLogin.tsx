/**
 * Social Login Components
 * Reusable components for OAuth provider authentication
 */

import React, { useState } from 'react';
import {
  Button,
  Box,
  Stack,
  Typography,
  Alert,
  CircularProgress,
  Tooltip,
  IconButton,
  Card,
  CardContent,
  Chip,
  Avatar,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  ListItemSecondaryAction,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from '@mui/material';
import {
  Google as GoogleIcon,
  Instagram as InstagramIcon,
  Microsoft as MicrosoftIcon,
  Facebook as FacebookIcon,
  Twitter as TwitterIcon,
  LinkedIn as LinkedInIcon,
  GitHub as GitHubIcon,
  Link as LinkIcon,
  LinkOff as LinkOffIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  Refresh as RefreshIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';

// Provider configuration
export interface SocialProvider {
  id: string;
  name: string;
  icon: React.ElementType;
  color: string;
  enabled: boolean;
  description?: string;
  scopes?: string[];
}

// Default providers
export const DEFAULT_PROVIDERS: SocialProvider[] = [
  {
    id: 'google',
    name: 'Google',
    icon: GoogleIcon,
    color: '#4285F4',
    enabled: true,
    description: 'Sign in with your Google account',
    scopes: ['openid', 'email', 'profile'],
  },
  {
    id: 'instagram',
    name: 'Instagram',
    icon: InstagramIcon,
    color: '#E4405F',
    enabled: true,
    description: 'Connect your Instagram account',
    scopes: ['basic', 'media'],
  },
  {
    id: 'microsoft',
    name: 'Microsoft',
    icon: MicrosoftIcon,
    color: '#0078D4',
    enabled: true,
    description: 'Sign in with your Microsoft account',
    scopes: ['openid', 'email', 'profile'],
  },
  {
    id: 'facebook',
    name: 'Facebook',
    icon: FacebookIcon,
    color: '#1877F2',
    enabled: false,
    description: 'Connect your Facebook account',
    scopes: ['email', 'public_profile'],
  },
  {
    id: 'twitter',
    name: 'Twitter',
    icon: TwitterIcon,
    color: '#1DA1F2',
    enabled: false,
    description: 'Connect your Twitter account',
    scopes: ['tweet.read', 'users.read'],
  },
  {
    id: 'linkedin',
    name: 'LinkedIn',
    icon: LinkedInIcon,
    color: '#0A66C2',
    enabled: false,
    description: 'Connect your LinkedIn account',
    scopes: ['r_liteprofile', 'r_emailaddress'],
  },
  {
    id: 'github',
    name: 'GitHub',
    icon: GitHubIcon,
    color: '#333',
    enabled: false,
    description: 'Connect your GitHub account',
    scopes: ['user', 'email'],
  },
];

// Props for SocialLoginButton
interface SocialLoginButtonProps {
  provider: SocialProvider;
  onConnect: (providerId: string) => Promise<void>;
  variant?: 'contained' | 'outlined' | 'text';
  size?: 'small' | 'medium' | 'large';
  fullWidth?: boolean;
  disabled?: boolean;
  showDescription?: boolean;
}

/**
 * Social Login Button Component
 */
export const SocialLoginButton: React.FC<SocialLoginButtonProps> = ({
  provider,
  onConnect,
  variant = 'outlined',
  size = 'medium',
  fullWidth = true,
  disabled = false,
  showDescription = false,
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const Icon = provider.icon;
  
  const handleClick = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      await onConnect(provider.id);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Connection failed';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };
  
  const buttonContent = (
    <>
      {isLoading ? (
        <CircularProgress size={20} color="inherit" />
      ) : (
        <Icon />
      )}
      <Box ml={1}>
        {showDescription && provider.description
          ? provider.description
          : `Continue with ${provider.name}`}
      </Box>
    </>
  );
  
  return (
    <Box>
      <Tooltip title={!provider.enabled ? 'This provider is not available' : ''}>
        <span style={{ width: fullWidth ? '100%' : 'auto' }}>
          <Button
            variant={variant}
            size={size}
            fullWidth={fullWidth}
            onClick={handleClick}
            disabled={disabled || !provider.enabled || isLoading}
            startIcon={!isLoading && <Icon />}
            sx={{
              borderColor: variant === 'outlined' ? provider.color : undefined,
              color: variant === 'outlined' ? provider.color : undefined,
              backgroundColor: variant === 'contained' ? provider.color : undefined,
              '&:hover': {
                borderColor: provider.color,
                backgroundColor: 
                  variant === 'contained' 
                    ? provider.color 
                    : `${provider.color}10`,
              },
            }}
          >
            {showDescription && provider.description
              ? provider.description
              : `Continue with ${provider.name}`}
          </Button>
        </span>
      </Tooltip>
      
      {error && (
        <Alert severity="error" sx={{ mt: 1 }}>
          {error}
        </Alert>
      )}
    </Box>
  );
};

// Props for SocialLoginGroup
interface SocialLoginGroupProps {
  providers?: SocialProvider[];
  onConnect: (providerId: string) => Promise<void>;
  direction?: 'row' | 'column';
  spacing?: number;
  variant?: 'contained' | 'outlined' | 'text';
  size?: 'small' | 'medium' | 'large';
  showOnlyEnabled?: boolean;
}

/**
 * Social Login Group Component
 */
export const SocialLoginGroup: React.FC<SocialLoginGroupProps> = ({
  providers = DEFAULT_PROVIDERS,
  onConnect,
  direction = 'column',
  spacing = 2,
  variant = 'outlined',
  size = 'medium',
  showOnlyEnabled = true,
}) => {
  const displayProviders = showOnlyEnabled 
    ? providers.filter(p => p.enabled)
    : providers;
  
  return (
    <Stack direction={direction} spacing={spacing}>
      {displayProviders.map((provider) => (
        <SocialLoginButton
          key={provider.id}
          provider={provider}
          onConnect={onConnect}
          variant={variant}
          size={size}
          fullWidth={direction === 'column'}
        />
      ))}
    </Stack>
  );
};

// Connected account interface
export interface ConnectedAccount {
  provider: string;
  providerName: string;
  accountId?: string;
  accountName?: string;
  email?: string;
  picture?: string;
  connectedAt: Date;
  lastSync?: Date;
  status: 'connected' | 'error' | 'expired';
  error?: string;
}

// Props for ConnectedAccounts
interface ConnectedAccountsProps {
  accounts: ConnectedAccount[];
  onDisconnect: (provider: string) => Promise<void>;
  onRefresh: (provider: string) => Promise<void>;
  onConnect: (provider: string) => Promise<void>;
  availableProviders?: SocialProvider[];
  showAddButton?: boolean;
}

/**
 * Connected Accounts Component
 */
export const ConnectedAccounts: React.FC<ConnectedAccountsProps> = ({
  accounts,
  onDisconnect,
  onRefresh,
  onConnect,
  availableProviders = DEFAULT_PROVIDERS,
  showAddButton = true,
}) => {
  const [confirmDisconnect, setConfirmDisconnect] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<string | null>(null);
  
  const handleDisconnect = async (provider: string) => {
    setIsLoading(provider);
    
    try {
      await onDisconnect(provider);
    } catch (err) {
      console.error(`Failed to disconnect ${provider}:`, err);
    } finally {
      setIsLoading(null);
      setConfirmDisconnect(null);
    }
  };
  
  const handleRefresh = async (provider: string) => {
    setIsLoading(provider);
    
    try {
      await onRefresh(provider);
    } catch (err) {
      console.error(`Failed to refresh ${provider}:`, err);
    } finally {
      setIsLoading(null);
    }
  };
  
  const getProviderInfo = (providerId: string) => {
    return availableProviders.find(p => p.id === providerId) || {
      id: providerId,
      name: providerId,
      icon: LinkIcon,
      color: '#666',
      enabled: false,
    };
  };
  
  const connectedProviderIds = accounts.map(a => a.provider);
  const availableToConnect = availableProviders.filter(
    p => p.enabled && !connectedProviderIds.includes(p.id)
  );
  
  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Connected Accounts
      </Typography>
      
      {accounts.length === 0 ? (
        <Alert severity="info">
          No accounts connected yet. Connect your social accounts to enable single sign-on.
        </Alert>
      ) : (
        <List>
          {accounts.map((account) => {
            const providerInfo = getProviderInfo(account.provider);
            const Icon = providerInfo.icon;
            const isProcessing = isLoading === account.provider;
            
            return (
              <ListItem key={account.provider}>
                <ListItemAvatar>
                  <Avatar
                    src={account.picture}
                    sx={{ 
                      bgcolor: providerInfo.color,
                      color: 'white',
                    }}
                  >
                    <Icon />
                  </Avatar>
                </ListItemAvatar>
                
                <ListItemText
                  primary={
                    <Box display="flex" alignItems="center" gap={1}>
                      <Typography variant="subtitle1">
                        {account.providerName}
                      </Typography>
                      {account.status === 'connected' && (
                        <CheckCircleIcon color="success" fontSize="small" />
                      )}
                      {account.status === 'error' && (
                        <ErrorIcon color="error" fontSize="small" />
                      )}
                      {account.status === 'expired' && (
                        <WarningIcon color="warning" fontSize="small" />
                      )}
                    </Box>
                  }
                  secondary={
                    <>
                      {account.accountName && (
                        <Typography variant="body2" component="span">
                          {account.accountName}
                        </Typography>
                      )}
                      {account.email && (
                        <Typography variant="body2" component="span">
                          {' • '}{account.email}
                        </Typography>
                      )}
                      {account.error && (
                        <Typography variant="body2" color="error" component="div">
                          {account.error}
                        </Typography>
                      )}
                    </>
                  }
                />
                
                <ListItemSecondaryAction>
                  <Stack direction="row" spacing={1}>
                    {(account.status === 'error' || account.status === 'expired') && (
                      <Tooltip title="Refresh connection">
                        <IconButton
                          onClick={() => handleRefresh(account.provider)}
                          disabled={isProcessing}
                        >
                          {isProcessing ? (
                            <CircularProgress size={20} />
                          ) : (
                            <RefreshIcon />
                          )}
                        </IconButton>
                      </Tooltip>
                    )}
                    
                    <Tooltip title="Disconnect account">
                      <IconButton
                        onClick={() => setConfirmDisconnect(account.provider)}
                        disabled={isProcessing}
                      >
                        <LinkOffIcon />
                      </IconButton>
                    </Tooltip>
                  </Stack>
                </ListItemSecondaryAction>
              </ListItem>
            );
          })}
        </List>
      )}
      
      {showAddButton && availableToConnect.length > 0 && (
        <Box mt={2}>
          <Typography variant="subtitle2" gutterBottom>
            Add Account
          </Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap">
            {availableToConnect.map((provider) => {
              const Icon = provider.icon;
              return (
                <Chip
                  key={provider.id}
                  icon={<Icon />}
                  label={provider.name}
                  onClick={() => onConnect(provider.id)}
                  variant="outlined"
                  sx={{
                    borderColor: provider.color,
                    color: provider.color,
                    '&:hover': {
                      backgroundColor: `${provider.color}10`,
                    },
                  }}
                />
              );
            })}
          </Stack>
        </Box>
      )}
      
      {/* Disconnect Confirmation Dialog */}
      <Dialog
        open={confirmDisconnect !== null}
        onClose={() => setConfirmDisconnect(null)}
      >
        <DialogTitle>Disconnect Account?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to disconnect your {confirmDisconnect} account?
            You can reconnect it at any time.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDisconnect(null)}>
            Cancel
          </Button>
          <Button
            onClick={() => confirmDisconnect && handleDisconnect(confirmDisconnect)}
            color="error"
            autoFocus
          >
            Disconnect
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default SocialLoginButton;