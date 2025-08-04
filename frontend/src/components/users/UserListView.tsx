import React from 'react';
import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
  Checkbox,
  Avatar,
  Typography,
  Stack,
  Tooltip,
  Paper,
} from '@mui/material';
import {
  MoreVert,
  Edit,
  Delete,
  Block,
  CheckCircle,
} from '@mui/icons-material';
import { VirtualList } from '@/components/common/VirtualList';
import { format } from 'date-fns';
import { UserRole } from '@/types/auth';

interface User {
  id: string;
  username: string;
  email: string;
  role: UserRole;
  status: string;
  created_at: string;
  last_login?: string;
  avatar?: string;
}

interface UserListViewProps {
  users: User[];
  selected: string[];
  onSelectAll: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onSelectOne: (id: string) => void;
  onEdit: (user: User) => void;
  onDelete: (userId: string) => void;
  onToggleStatus: (userId: string, status: string) => void;
  onMenuClick: (event: React.MouseEvent<HTMLElement>, userId: string) => void;
  viewMode?: 'table' | 'virtual';
}

export const UserListView: React.FC<UserListViewProps> = ({
  users,
  selected,
  onSelectAll,
  onSelectOne,
  onEdit,
  onDelete,
  onToggleStatus,
  onMenuClick,
  viewMode = 'virtual',
}) => {
  const getRoleColor = (role: UserRole) => {
    switch (role) {
      case UserRole.SUPER_ADMIN:
        return 'error';
      case UserRole.AGENCY_OWNER:
        return 'primary';
      case UserRole.AGENCY_ADMIN:
        return 'secondary';
      case UserRole.AGENCY_STAFF:
        return 'info';
      case UserRole.MODEL:
        return 'success';
      default:
        return 'default';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'active':
        return 'success';
      case 'inactive':
        return 'default';
      case 'suspended':
        return 'error';
      case 'pending':
        return 'warning';
      default:
        return 'default';
    }
  };

  const renderUserRow = (user: User, index: number) => {
    const isSelected = selected.includes(user.id);

    return (
      <TableRow
        hover
        role="checkbox"
        aria-checked={isSelected}
        tabIndex={-1}
        key={user.id}
        selected={isSelected}
        sx={{ height: 72 }}
      >
        <TableCell padding="checkbox">
          <Checkbox
            checked={isSelected}
            onChange={() => onSelectOne(user.id)}
          />
        </TableCell>
        <TableCell component="th" scope="row">
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Avatar src={user.avatar} alt={user.username}>
              {user.username[0]?.toUpperCase()}
            </Avatar>
            <Box>
              <Typography variant="subtitle2" fontWeight="medium">
                {user.username}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {user.email}
              </Typography>
            </Box>
          </Box>
        </TableCell>
        <TableCell>
          <Chip
            label={user.role.replace(/_/g, ' ')}
            color={getRoleColor(user.role)}
            size="small"
          />
        </TableCell>
        <TableCell>
          <Chip
            label={user.status}
            color={getStatusColor(user.status)}
            size="small"
          />
        </TableCell>
        <TableCell>
          <Typography variant="body2">
            {format(new Date(user.created_at), 'MMM d, yyyy')}
          </Typography>
        </TableCell>
        <TableCell>
          <Typography variant="body2">
            {user.last_login
              ? format(new Date(user.last_login), 'MMM d, yyyy h:mm a')
              : 'Never'}
          </Typography>
        </TableCell>
        <TableCell align="right">
          <Stack direction="row" spacing={0.5} justifyContent="flex-end">
            <Tooltip title="Edit">
              <IconButton size="small" onClick={() => onEdit(user)}>
                <Edit fontSize="small" />
              </IconButton>
            </Tooltip>
            {user.status === 'active' ? (
              <Tooltip title="Suspend">
                <IconButton
                  size="small"
                  onClick={() => onToggleStatus(user.id, 'suspended')}
                  color="warning"
                >
                  <Block fontSize="small" />
                </IconButton>
              </Tooltip>
            ) : (
              <Tooltip title="Activate">
                <IconButton
                  size="small"
                  onClick={() => onToggleStatus(user.id, 'active')}
                  color="success"
                >
                  <CheckCircle fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
            <Tooltip title="Delete">
              <IconButton
                size="small"
                onClick={() => onDelete(user.id)}
                color="error"
              >
                <Delete fontSize="small" />
              </IconButton>
            </Tooltip>
            <IconButton
              size="small"
              onClick={(e) => onMenuClick(e, user.id)}
            >
              <MoreVert fontSize="small" />
            </IconButton>
          </Stack>
        </TableCell>
      </TableRow>
    );
  };

  const tableHeader = (
    <TableHead>
      <TableRow>
        <TableCell padding="checkbox">
          <Checkbox
            indeterminate={selected.length > 0 && selected.length < users.length}
            checked={users.length > 0 && selected.length === users.length}
            onChange={onSelectAll}
          />
        </TableCell>
        <TableCell>User</TableCell>
        <TableCell>Role</TableCell>
        <TableCell>Status</TableCell>
        <TableCell>Created</TableCell>
        <TableCell>Last Login</TableCell>
        <TableCell align="right">Actions</TableCell>
      </TableRow>
    </TableHead>
  );

  if (viewMode === 'virtual' && users.length > 20) {
    // Use virtual scrolling for large lists
    return (
      <TableContainer component={Paper}>
        <Table stickyHeader>
          {tableHeader}
        </Table>
        <Box sx={{ height: 'calc(100vh - 450px)', minHeight: 400 }}>
          <VirtualList
            items={users}
            itemHeight={72}
            renderItem={renderUserRow}
            height="100%"
            overscan={5}
            getItemKey={(user) => user.id}
          />
        </Box>
      </TableContainer>
    );
  }

  // Use regular table for small lists
  return (
    <TableContainer component={Paper}>
      <Table>
        {tableHeader}
        <TableBody>
          {users.map((user, index) => renderUserRow(user, index))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};