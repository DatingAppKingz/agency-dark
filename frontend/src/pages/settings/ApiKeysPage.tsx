import React, { useState } from 'react';
import {
  Box,
  Container,
  Typography,
  Tabs,
  Tab,
  Paper,
  Alert,
  Button,
  Grid,
  Card,
  CardContent,
  Chip } from '@mui/material';
import {
  Key as SecurityIcon,
  Info as InfoIcon,
  Book as DocsIcon,
  Warning as WarningIcon } from '@mui/icons-material';
import { ApiKeyProvider } from '@/types/apiKeys';
import ApiKeyManager from '@/components/settings/ApiKeyManager';
import { useAuth } from '@/hooks/useAuth';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index, ...other }) => {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`api-keys-tabpanel-${index}`}
      aria-labelledby={`api-keys-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
};

const ApiKeysPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);
  const { user } = useAuth();

  // Check if user has permission to manage API keys
  const canManageApiKeys = ['super_admin', 'agency_owner', 'agency_admin'].includes(user?.role || '');

  if (!canManageApiKeys) {
    return (
      <Container maxWidth="lg">
        <Box py={4}>
          <Alert severity="error">
            You don't have permission to manage API keys. Please contact your administrator.
          </Alert>
        </Box>
      </Container>
    );
  }

  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  return (
    <Container maxWidth="lg">
      <Box py={4}>
        {/* Header */}
        <Box mb={4}>
          <Typography variant="h4" gutterBottom>
            API Key Management
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Manage your external API integrations securely. All API keys are encrypted and stored safely.
          </Typography>
        </Box>

        {/* Security Notice */}
        <Alert severity="info" icon={<SecurityIcon />} sx={{ mb: 3 }}>
          <Typography variant="body2">
            <strong>Security Best Practices:</strong>
            <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
              <li>Rotate your API keys regularly</li>
              <li>Use different keys for development and production</li>
              <li>Never share API keys in code repositories</li>
              <li>Monitor usage for suspicious activity</li>
            </ul>
          </Typography>
        </Alert>

        {/* Provider Tabs */}
        <Paper sx={{ mb: 3 }}>
          <Tabs
            value={activeTab}
            onChange={handleTabChange}
            variant="scrollable"
            scrollButtons="auto"
            aria-label="API provider tabs"
          >
            <Tab label="All Keys" />
            <Tab label="Inflow" />
            <Tab label="OnlyFans" />
            <Tab label="Payment Providers" />
            <Tab label="Custom" />
          </Tabs>
        </Paper>

        {/* Tab Content */}
        <TabPanel value={activeTab} index={0}>
          <ApiKeyManager />
        </TabPanel>
        
        <TabPanel value={activeTab} index={1}>
          <Box mb={3}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" gap={2} mb={2}>
                  <Chip label="Inflow" color="primary" />
                  <Typography variant="h6">Inflow API Integration</Typography>
                </Box>
                <Typography variant="body2" color="text.secondary" paragraph>
                  Inflow provides comprehensive analytics and management tools for content creators. 
                  Connect your Inflow account to sync subscriber data, messages, and analytics.
                </Typography>
                <Button
                  size="small"
                  startIcon={<DocsIcon />}
                  href="https://docs.inflow.com/api-keys"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  View Documentation
                </Button>
              </CardContent>
            </Card>
          </Box>
          <ApiKeyManager provider={ApiKeyProvider.INFLOW} />
        </TabPanel>
        
        <TabPanel value={activeTab} index={2}>
          <Box mb={3}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" gap={2} mb={2}>
                  <Chip label="OnlyFans" color="secondary" />
                  <Typography variant="h6">OnlyFans API Integration</Typography>
                </Box>
                <Typography variant="body2" color="text.secondary" paragraph>
                  Direct integration with OnlyFans for content management, fan interactions, and revenue tracking. 
                  Ensure you have the necessary permissions before adding your API key.
                </Typography>
                <Box display="flex" gap={2}>
                  <Button
                    size="small"
                    startIcon={<DocsIcon />}
                    href="https://docs.onlyfansapi.com"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    View Documentation
                  </Button>
                  <Button
                    size="small"
                    startIcon={<WarningIcon />}
                    color="warning"
                    href="https://onlyfans.com/settings/developer"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Get API Access
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Box>
          <ApiKeyManager provider={ApiKeyProvider.ONLYFANS} />
        </TabPanel>
        
        <TabPanel value={activeTab} index={3}>
          <Grid container spacing={3} mb={3}>
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Box display="flex" alignItems="center" gap={2} mb={2}>
                    <Chip label="Stripe" color="success" />
                    <Typography variant="h6">Stripe</Typography>
                  </Box>
                  <Typography variant="body2" color="text.secondary" paragraph>
                    Process payments and manage subscriptions with Stripe's powerful payment infrastructure.
                  </Typography>
                  <Button
                    size="small"
                    startIcon={<DocsIcon />}
                    href="https://stripe.com/docs/keys"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Get Stripe Keys
                  </Button>
                </CardContent>
              </Card>
            </Grid>
            
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Box display="flex" alignItems="center" gap={2} mb={2}>
                    <Chip label="PayPal" color="warning" />
                    <Typography variant="h6">PayPal</Typography>
                  </Box>
                  <Typography variant="body2" color="text.secondary" paragraph>
                    Accept PayPal payments and enable quick checkouts for your customers.
                  </Typography>
                  <Button
                    size="small"
                    startIcon={<DocsIcon />}
                    href="https://developer.paypal.com/api/rest/"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Get PayPal Keys
                  </Button>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
          <ApiKeyManager provider={ApiKeyProvider.STRIPE} />
        </TabPanel>
        
        <TabPanel value={activeTab} index={4}>
          <Box mb={3}>
            <Alert severity="warning">
              <Typography variant="body2">
                Custom API keys are for advanced integrations. Make sure you understand the security implications 
                before adding custom keys.
              </Typography>
            </Alert>
          </Box>
          <ApiKeyManager provider={ApiKeyProvider.CUSTOM} />
        </TabPanel>

        {/* Help Section */}
        <Box mt={4}>
          <Card variant="outlined">
            <CardContent>
              <Box display="flex" alignItems="center" gap={1} mb={2}>
                <InfoIcon color="primary" />
                <Typography variant="h6">Need Help?</Typography>
              </Box>
              <Typography variant="body2" color="text.secondary" paragraph>
                If you're having trouble setting up your API keys or need assistance with integrations:
              </Typography>
              <Box display="flex" gap={2} flexWrap="wrap">
                <Button
                  variant="outlined"
                  size="small"
                  href="/docs/api-keys"
                >
                  API Key Guide
                </Button>
                <Button
                  variant="outlined"
                  size="small"
                  href="/support"
                >
                  Contact Support
                </Button>
                <Button
                  variant="outlined"
                  size="small"
                  href="/docs/security"
                >
                  Security Documentation
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Box>
      </Box>
    </Container>
  );
};

export default ApiKeysPage;
