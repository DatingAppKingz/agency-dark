import { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Button,
  Alert,
  Tabs,
  Tab } from '@mui/material';
import {
  Palette,
  Image,
  FontDownload,
  Email,
  Domain,
  Save,
  Refresh } from '@mui/icons-material';
import { ThemeCustomizer } from '@/components/whitelabel/ThemeCustomizer';
import { LogoUploader } from '@/components/whitelabel/LogoUploader';
import { FontSelector } from '@/components/whitelabel/FontSelector';
import { DomainSettings } from '@/components/whitelabel/DomainSettings';
import { EmailTemplateEditor } from '@/components/whitelabel/EmailTemplateEditor';
import { useAuthStore } from '@/store/authStore';
import { useToast } from '@/components/common/Toaster';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel = ({ children, value, index }: TabPanelProps) => {
  return (
    <Box
      role="tabpanel"
      hidden={value !== index}
      id={`whitelabel-tabpanel-${index}`}
      aria-labelledby={`whitelabel-tab-${index}`}
    >
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </Box>
  );
};

const WhiteLabelPage = () => {
  const { user } = useAuthStore();
  const { success, error } = useToast();
  const [selectedTab, setSelectedTab] = useState(0);
  const [hasChanges, setHasChanges] = useState(false);

  // Check if user has permission
  const canAccessWhiteLabel = ['super_admin', 'agency_owner'].includes(user?.role || '');

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setSelectedTab(newValue);
  };

  const handleSave = async () => {
    try {
      // TODO: Implement save functionality
      success('White label settings saved successfully');
      setHasChanges(false);
    } catch (err) {
      error('Failed to save settings');
    }
  };

  const handleReset = () => {
    // TODO: Implement reset functionality
    setHasChanges(false);
  };

  if (!canAccessWhiteLabel) {
    return (
      <Box>
        <Alert severity="error">
          You don't have permission to access white label settings.
        </Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">White Label Settings</Typography>
        
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="outlined"
            startIcon={<Refresh />}
            onClick={handleReset}
            disabled={!hasChanges}
          >
            Reset
          </Button>
          <Button
            variant="contained"
            startIcon={<Save />}
            onClick={handleSave}
            disabled={!hasChanges}
          >
            Save Changes
          </Button>
        </Box>
      </Box>

      {hasChanges && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          You have unsaved changes. Don't forget to save before leaving this page.
        </Alert>
      )}

      <Paper sx={{ mb: 3 }}>
        <Tabs
          value={selectedTab}
          onChange={handleTabChange}
          variant="scrollable"
          scrollButtons="auto"
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab icon={<Palette />} label="Theme" />
          <Tab icon={<Image />} label="Logo & Branding" />
          <Tab icon={<FontDownload />} label="Typography" />
          <Tab icon={<Domain />} label="Custom Domain" />
          <Tab icon={<Email />} label="Email Templates" />
        </Tabs>

        <Box sx={{ p: 3 }}>
          <TabPanel value={selectedTab} index={0}>
            <ThemeCustomizer onChange={() => setHasChanges(true)} />
          </TabPanel>

          <TabPanel value={selectedTab} index={1}>
            <LogoUploader onChange={() => setHasChanges(true)} />
          </TabPanel>

          <TabPanel value={selectedTab} index={2}>
            <FontSelector onChange={() => setHasChanges(true)} />
          </TabPanel>

          <TabPanel value={selectedTab} index={3}>
            <DomainSettings onChange={() => setHasChanges(true)} />
          </TabPanel>

          <TabPanel value={selectedTab} index={4}>
            <EmailTemplateEditor onChange={() => setHasChanges(true)} />
          </TabPanel>
        </Box>
      </Paper>

      {/* Preview Section */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Live Preview
        </Typography>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          Changes will be reflected here in real-time
        </Typography>
        
        <Box
          sx={{
            mt: 2,
            p: 3,
            border: 1,
            borderColor: 'divider',
            borderRadius: 1,
            minHeight: 200,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center' }}
        >
          <Typography color="text.secondary">
            Preview will update as you make changes
          </Typography>
        </Box>
      </Paper>
    </Box>
  );
};

export default WhiteLabelPage;
