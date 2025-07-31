import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Tabs,
  Tab,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Switch,
  IconButton,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  Grid,
  Card,
  CardContent,
  LinearProgress,
  Alert,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  FormControlLabel } from '@mui/material';
import {
  Add,
  Settings,
  Delete,
  ExpandMore,
  Extension,
  Security,
  Analytics,
  Chat,
  AttachMoney,
  People,
  Autorenew,
  CloudSync } from '@mui/icons-material';
import { useAgencyFeatures } from '@/hooks/useAgencyFeatures';
import { FeatureCategory, IntegrationType } from '@/types/agencyFeatures';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel = ({ children, value, index }: TabPanelProps) => (
  <div hidden={value !== index}>
    {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
  </div>
);

const categoryIcons: Record<FeatureCategory, React.ReactElement> = {
  chat: <Chat />,
  analytics: <Analytics />,
  financial: <AttachMoney />,
  models: <People />,
  automation: <Autorenew />,
  integrations: <CloudSync />,
  security: <Security />,
  customization: <Extension /> };

export const AgencyFeaturesManager: React.FC = () => {
  const {
    config,
    isPending,
    toggleFeature,
    addCustomModule,
    updateCustomModule,
    deleteCustomModule,
    addIntegration,
    updateIntegration,
    deleteIntegration,
    getLimitUsage } = useAgencyFeatures();

  const [tabValue, setTabValue] = useState(0);
  const [moduleDialog, setModuleDialog] = useState(false);
  const [integrationDialog, setIntegrationDialog] = useState(false);
  const [, setSettingsDialog] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  // Module form state
  const [moduleForm, setModuleForm] = useState({
    name: '',
    description: '',
    route: '',
    component: '',
    permissions: [] as string[] });

  // Integration form state
  const [integrationForm, setIntegrationForm] = useState({
    type: 'webhook' as IntegrationType,
    name: '',
    config: {} });

  const handleCreateModule = async () => {
    if (!moduleForm.name || !moduleForm.route) return;

    await addCustomModule({
      ...moduleForm,
      enabled: true,
      order: config?.customModules.length || 0 });

    setModuleDialog(false);
    setModuleForm({
      name: '',
      description: '',
      route: '',
      component: '',
      permissions: [] });
  };

  const handleCreateIntegration = async () => {
    if (!integrationForm.name) return;

    await addIntegration(
      integrationForm.type,
      integrationForm.name,
      integrationForm.config
    );

    setIntegrationDialog(false);
    setIntegrationForm({
      type: 'webhook',
      name: '',
      config: {} });
  };

  if (isPending || !config) {
    return <Box>Loading features...</Box>;
  }

  // Group features by category
  const featuresByCategory = config.features.reduce((acc, feature) => {
    if (!acc[feature.category]) {
      acc[feature.category] = [];
    }
    acc[feature.category].push(feature);
    return acc;
  }, {} as Record<FeatureCategory, typeof config.features>);

  return (
    <Box>
      <Paper sx={{ mb: 3 }}>
        <Tabs value={tabValue} onChange={(_, v) => setTabValue(v)}>
          <Tab label="Features" />
          <Tab label="Custom Modules" />
          <Tab label="Integrations" />
          <Tab label="Usage & Limits" />
        </Tabs>

        <TabPanel value={tabValue} index={0}>
          {/* Features Tab */}
          {Object.entries(featuresByCategory).map(([category, features]) => (
            <Accordion key={category} defaultExpanded>
              <AccordionSummary expandIcon={<ExpandMore />}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  {categoryIcons[category as FeatureCategory]}
                  <Typography variant="h6" sx={{ textTransform: 'capitalize' }}>
                    {category}
                  </Typography>
                  <Chip
                    label={`${features.filter(f => f.enabled).length}/${features.length}`}
                    size="small"
                    color="primary"
                  />
                </Box>
              </AccordionSummary>
              <AccordionDetails>
                <List>
                  {features.map((feature) => (
                    <ListItem
                      key={feature.id}
                      sx={{
                        border: 1,
                        borderColor: 'divider',
                        borderRadius: 1,
                        mb: 1 }}
                    >
                      <ListItemText
                        primary={feature.name}
                        secondary={feature.description}
                      />
                      <ListItemSecondaryAction>
                        {feature.settings && (
                          <IconButton
                            edge="end"
                            onClick={() => setSettingsDialog(feature.id)}
                          >
                            <Settings />
                          </IconButton>
                        )}
                        <Switch
                          edge="end"
                          checked={feature.enabled}
                          onChange={() => toggleFeature(feature.id)}
                        />
                      </ListItemSecondaryAction>
                    </ListItem>
                  ))}
                </List>
              </AccordionDetails>
            </Accordion>
          ))}
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          {/* Custom Modules Tab */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
            <Typography variant="h6">Custom Modules</Typography>
            <Button
              startIcon={<Add />}
              variant="contained"
              onClick={() => setModuleDialog(true)}
            >
              Add Module
            </Button>
          </Box>

          <Grid container spacing={2}>
            {config.customModules.map((module) => (
              <Grid item xs={12} sm={6} md={4} key={module.id}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      {module.name}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" paragraph>
                      {module.description}
                    </Typography>
                    <Typography variant="caption" display="block" gutterBottom>
                      Route: {module.route}
                    </Typography>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={module.enabled}
                            onChange={(e) => updateCustomModule(module.id, { enabled: e.target.checked })}
                          />
                        }
                        label="Enabled"
                      />
                      <IconButton
                        size="small"
                        onClick={() => setDeleteConfirm(module.id)}
                        color="error"
                      >
                        <Delete />
                      </IconButton>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>

          {config.customModules.length === 0 && (
            <Alert severity="info">
              No custom modules yet. Create custom modules to extend your agency's functionality.
            </Alert>
          )}
        </TabPanel>

        <TabPanel value={tabValue} index={2}>
          {/* Integrations Tab */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
            <Typography variant="h6">Integrations</Typography>
            <Button
              startIcon={<Add />}
              variant="contained"
              onClick={() => setIntegrationDialog(true)}
            >
              Add Integration
            </Button>
          </Box>

          <List>
            {config.integrations.map((integration) => (
              <ListItem
                key={integration.id}
                sx={{
                  border: 1,
                  borderColor: 'divider',
                  borderRadius: 1,
                  mb: 1 }}
              >
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography>{integration.name}</Typography>
                      <Chip
                        label={integration.status}
                        size="small"
                        color={
                          integration.status === 'connected' ? 'success' :
                          integration.status === 'error' ? 'error' : 'default'
                        }
                      />
                    </Box>
                  }
                  secondary={`Type: ${integration.type}`}
                />
                <ListItemSecondaryAction>
                  <Switch
                    edge="end"
                    checked={integration.enabled}
                    onChange={(e) => updateIntegration(integration.id, { enabled: e.target.checked })}
                  />
                  <IconButton
                    edge="end"
                    onClick={() => setDeleteConfirm(integration.id)}
                    color="error"
                  >
                    <Delete />
                  </IconButton>
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>

          {config.integrations.length === 0 && (
            <Alert severity="info">
              No integrations configured. Add integrations to connect with external services.
            </Alert>
          )}
        </TabPanel>

        <TabPanel value={tabValue} index={3}>
          {/* Usage & Limits Tab */}
          <Typography variant="h6" gutterBottom>
            Resource Usage
          </Typography>

          <Grid container spacing={3}>
            {Object.entries(config.limits).map(([key, limit]) => {
              if (key === 'customLimits' || typeof limit !== 'object') return null;
              
              const usage = getLimitUsage(key as any);
              const isNearLimit = usage > 80;
              
              return (
                <Grid item xs={12} md={6} key={key}>
                  <Paper sx={{ p: 2 }}>
                    <Typography variant="subtitle1" gutterBottom>
                      {key.charAt(0).toUpperCase() + key.slice(1)}
                    </Typography>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="body2">
                        {limit.current} / {limit.max} {limit.unit || ''}
                      </Typography>
                      <Typography variant="body2" color={isNearLimit ? 'error' : 'text.secondary'}>
                        {usage.toFixed(0)}%
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={usage}
                      color={isNearLimit ? 'error' : 'primary'}
                    />
                  </Paper>
                </Grid>
              );
            })}
          </Grid>

          <Alert severity="info" sx={{ mt: 3 }}>
            Contact support to increase your limits or upgrade your plan.
          </Alert>
        </TabPanel>
      </Paper>

      {/* Module Dialog */}
      <Dialog
        open={moduleDialog}
        onClose={() => setModuleDialog(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Create Custom Module</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              label="Module Name"
              value={moduleForm.name}
              onChange={(e) => setModuleForm(prev => ({ ...prev, name: e.target.value }))}
              fullWidth
              required
            />
            <TextField
              label="Description"
              value={moduleForm.description}
              onChange={(e) => setModuleForm(prev => ({ ...prev, description: e.target.value }))}
              fullWidth
              multiline
              rows={2}
            />
            <TextField
              label="Route Path"
              value={moduleForm.route}
              onChange={(e) => setModuleForm(prev => ({ ...prev, route: e.target.value }))}
              fullWidth
              required
              placeholder="/custom/module-name"
            />
            <TextField
              label="Component Name"
              value={moduleForm.component}
              onChange={(e) => setModuleForm(prev => ({ ...prev, component: e.target.value }))}
              fullWidth
              placeholder="CustomModuleComponent"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setModuleDialog(false)}>Cancel</Button>
          <Button onClick={handleCreateModule} variant="contained">
            Create
          </Button>
        </DialogActions>
      </Dialog>

      {/* Integration Dialog */}
      <Dialog
        open={integrationDialog}
        onClose={() => setIntegrationDialog(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Add Integration</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <FormControl fullWidth>
              <InputLabel>Integration Type</InputLabel>
              <Select
                value={integrationForm.type}
                onChange={(e) => setIntegrationForm(prev => ({ ...prev, type: e.target.value as IntegrationType }))}
                label="Integration Type"
              >
                <MenuItem value="webhook">Webhook</MenuItem>
                <MenuItem value="payment_processor">Payment Processor</MenuItem>
                <MenuItem value="email">Email Service</MenuItem>
                <MenuItem value="sms">SMS Service</MenuItem>
                <MenuItem value="analytics">Analytics</MenuItem>
                <MenuItem value="storage">Cloud Storage</MenuItem>
                <MenuItem value="crm">CRM</MenuItem>
                <MenuItem value="accounting">Accounting</MenuItem>
              </Select>
            </FormControl>
            <TextField
              label="Integration Name"
              value={integrationForm.name}
              onChange={(e) => setIntegrationForm(prev => ({ ...prev, name: e.target.value }))}
              fullWidth
              required
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setIntegrationDialog(false)}>Cancel</Button>
          <Button onClick={handleCreateIntegration} variant="contained">
            Add
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation */}
      <Dialog
        open={Boolean(deleteConfirm)}
        onClose={() => setDeleteConfirm(null)}
      >
        <DialogTitle>Delete Item?</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete this item? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirm(null)}>Cancel</Button>
          <Button
            onClick={() => {
              if (deleteConfirm) {
                // Determine if it's a module or integration
                const isModule = config.customModules.some(m => m.id === deleteConfirm);
                if (isModule) {
                  deleteCustomModule(deleteConfirm);
                } else {
                  deleteIntegration(deleteConfirm);
                }
                setDeleteConfirm(null);
              }
            }}
            color="error"
            variant="contained"
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
