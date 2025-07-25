import { useState } from 'react';
import {
  Box,
  Typography,
  Tabs,
  Tab,
  Paper,
} from '@mui/material';
import {
  Person,
  Notifications,
  Security,
  Palette,
  Language,
} from '@mui/icons-material';
import { NotificationSettings } from '@/components/settings/NotificationSettings';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel = (props: TabPanelProps) => {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`settings-tabpanel-${index}`}
      aria-labelledby={`settings-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
};

const SettingsPage = () => {
  const [selectedTab, setSelectedTab] = useState(0);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setSelectedTab(newValue);
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Settings
      </Typography>

      <Paper sx={{ mt: 3 }}>
        <Tabs
          value={selectedTab}
          onChange={handleTabChange}
          variant="scrollable"
          scrollButtons="auto"
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab icon={<Person />} label="Profile" />
          <Tab icon={<Notifications />} label="Notifications" />
          <Tab icon={<Security />} label="Security" />
          <Tab icon={<Palette />} label="Appearance" />
          <Tab icon={<Language />} label="Language" />
        </Tabs>

        <Box sx={{ p: 3 }}>
          <TabPanel value={selectedTab} index={0}>
            <Typography variant="h6">Profile Settings</Typography>
            <Typography color="text.secondary" sx={{ mt: 2 }}>
              Profile settings coming soon...
            </Typography>
          </TabPanel>

          <TabPanel value={selectedTab} index={1}>
            <NotificationSettings />
          </TabPanel>

          <TabPanel value={selectedTab} index={2}>
            <Typography variant="h6">Security Settings</Typography>
            <Typography color="text.secondary" sx={{ mt: 2 }}>
              Security settings coming soon...
            </Typography>
          </TabPanel>

          <TabPanel value={selectedTab} index={3}>
            <Typography variant="h6">Appearance Settings</Typography>
            <Typography color="text.secondary" sx={{ mt: 2 }}>
              Appearance settings coming soon...
            </Typography>
          </TabPanel>

          <TabPanel value={selectedTab} index={4}>
            <Typography variant="h6">Language Settings</Typography>
            <Typography color="text.secondary" sx={{ mt: 2 }}>
              Language settings coming soon...
            </Typography>
          </TabPanel>
        </Box>
      </Paper>
    </Box>
  );
};

export default SettingsPage;