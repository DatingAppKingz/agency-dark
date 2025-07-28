import { Drawer, List, ListItem, ListItemButton, ListItemIcon, ListItemText, Typography, Box, Divider, useTheme, useMediaQuery } from '@mui/material';
import { Dashboard, People, Person, Chat, Analytics, AttachMoney, Settings, Business, AdminPanelSettings, CloudSync, Group } from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { UserRole } from '@/types/auth';

interface SidebarProps {
  open: boolean;
  onClose: () => void;
  width: number;
}

interface MenuItem {
  text: string;
  icon: React.ReactNode;
  path: string;
  roles?: UserRole[];
}

const menuItems: MenuItem[] = [
  {
    text: 'Dashboard',
    icon: <Dashboard />,
    path: '/dashboard',
  },
  {
    text: 'Agencies',
    icon: <Business />,
    path: '/dashboard/agencies',
    roles: [UserRole.SUPER_ADMIN],
  },
  {
    text: 'Users',
    icon: <People />,
    path: '/dashboard/users',
    roles: [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
  },
  {
    text: 'Models',
    icon: <Person />,
    path: '/dashboard/models',
    roles: [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.MODEL],
  },
  {
    text: 'Chat',
    icon: <Chat />,
    path: '/dashboard/chat',
    roles: [UserRole.MODEL, UserRole.CHATTER],
  },
  {
    text: 'Analytics',
    icon: <Analytics />,
    path: '/dashboard/analytics',
  },
  {
    text: 'Bulk Operations',
    icon: <Group />,
    path: '/dashboard/bulk-operations',
    roles: [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
  },
  {
    text: 'Data Sync',
    icon: <CloudSync />,
    path: '/dashboard/sync',
    roles: [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.MODEL],
  },
  {
    text: 'Financial',
    icon: <AttachMoney />,
    path: '/dashboard/financial',
    roles: [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
  },
  {
    text: 'Settings',
    icon: <Settings />,
    path: '/dashboard/settings',
  },
];

export const Sidebar = ({ open, onClose, width }: SidebarProps) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuthStore();

  const filteredMenuItems = menuItems.filter((item) => {
    if (!item.roles) return true;
    return user && item.roles.includes(user.role);
  });

  const handleNavigation = (path: string) => {
    navigate(path);
    if (isMobile) {
      onClose();
    }
  };

  const drawer = (
    <>
      <Box sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
        <AdminPanelSettings sx={{ fontSize: 32, color: 'primary.main' }} />
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          AgencyDark
        </Typography>
      </Box>
      <Divider />
      <List>
        {filteredMenuItems.map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton
              selected={location.pathname === item.path}
              onClick={() => handleNavigation(item.path)}
              sx={{
                '&.Mui-selected': {
                  backgroundColor: 'action.selected',
                  '&:hover': {
                    backgroundColor: 'action.selected',
                  },
                },
              }}
            >
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
      {user && (
        <>
          <Box sx={{ flexGrow: 1 }} />
          <Box sx={{ p: 2 }}>
            <Typography variant="caption" color="text.secondary">
              Logged in as
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              {user.full_name}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {user.role.replace('_', ' ')}
            </Typography>
          </Box>
        </>
      )}
    </>
  );

  return (
    <Drawer
      variant={isMobile ? 'temporary' : 'permanent'}
      open={open}
      onClose={onClose}
      sx={{
        width: width,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width: width,
          boxSizing: 'border-box',
          display: 'flex',
          flexDirection: 'column',
        },
      }}
    >
      {drawer}
    </Drawer>
  );
};