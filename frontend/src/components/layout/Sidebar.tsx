import { Drawer, List, ListItem, ListItemButton, ListItemIcon, ListItemText, Typography, Box, Divider, useTheme, useMediaQuery, IconButton, Tooltip } from '@mui/material';
import { Dashboard, People, Person, Chat, Analytics, AttachMoney, Settings, Business, AdminPanelSettings, CloudSync, Group, Assessment, ChevronLeft, ChevronRight, Psychology } from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { UserRole } from '@/types/auth';

interface SidebarProps {
  open: boolean;
  onClose: () => void;
  width: number;
  collapsed?: boolean;
  onCollapse?: () => void;
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
    text: 'ML Insights',
    icon: <Psychology />,
    path: '/dashboard/ml-insights',
    roles: [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
  },
  {
    text: 'Bulk Operations',
    icon: <Group />,
    path: '/dashboard/bulk-operations',
    roles: [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
  },
  {
    text: 'Reports',
    icon: <Assessment />,
    path: '/dashboard/reports',
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

export const Sidebar = ({ open, onClose, width, collapsed = false, onCollapse }: SidebarProps) => {
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

  const effectiveWidth = collapsed ? 64 : width;

  const drawer = (
    <>
      <Box sx={{ 
        p: 2, 
        display: 'flex', 
        alignItems: 'center', 
        gap: 1,
        justifyContent: collapsed ? 'center' : 'flex-start',
        minHeight: 64,
      }}>
        {!collapsed && (
          <>
            <AdminPanelSettings sx={{ fontSize: 32, color: 'primary.main' }} />
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              AgencyDark
            </Typography>
          </>
        )}
        {collapsed && (
          <AdminPanelSettings sx={{ fontSize: 28, color: 'primary.main' }} />
        )}
      </Box>
      <Divider />
      {!isMobile && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 1 }}>
          <IconButton onClick={onCollapse} size="small">
            {collapsed ? <ChevronRight /> : <ChevronLeft />}
          </IconButton>
        </Box>
      )}
      <Divider />
      <List>
        {filteredMenuItems.map((item) => (
          <ListItem key={item.text} disablePadding>
            <Tooltip title={collapsed ? item.text : ''} placement="right">
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
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  px: collapsed ? 2 : 3,
                }}
              >
                <ListItemIcon sx={{ 
                  minWidth: collapsed ? 0 : 56,
                  justifyContent: 'center' 
                }}>
                  {item.icon}
                </ListItemIcon>
                {!collapsed && <ListItemText primary={item.text} />}
              </ListItemButton>
            </Tooltip>
          </ListItem>
        ))}
      </List>
      {user && !collapsed && (
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
        width: effectiveWidth,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width: effectiveWidth,
          boxSizing: 'border-box',
          display: 'flex',
          flexDirection: 'column',
          transition: theme.transitions.create('width', {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.enteringScreen,
          }),
          overflowX: 'hidden',
        },
      }}
    >
      {drawer}
    </Drawer>
  );
};
