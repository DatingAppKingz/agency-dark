import { useState } from 'react';
import {
  Box,
  Typography,
  Button,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Chip,
  IconButton,
  Menu,
  MenuItem,
  TextField,
  InputAdornment,
  Checkbox,
  Toolbar,
  alpha,
} from '@mui/material';
import {
  Add,
  Search,
  MoreVert,
  Edit,
  Delete,
  Block,
  CheckCircle,
  Download,
} from '@mui/icons-material';
import { useAuthStore } from '@/store/authStore';
import { useUIStore } from '@/store/uiStore';
import { UserRole } from '@/types/auth';
import { UserDialog } from '@/components/users/UserDialog';
import { UserListView } from '@/components/users/UserListView';
import {
  useUsers,
  useCreateUser,
  useUpdateUser,
  useDeleteUser,
  useDeleteUsers,
  useToggleUserStatus,
} from '@/hooks/useUsers';

const UsersPage = () => {
  const { user: currentUser } = useAuthStore();
  const { userFilters, setUserFilters } = useUIStore();
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [selected, setSelected] = useState<string[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<any>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);

  // API hooks
  const { data, isPending } = useUsers({
    page: page + 1,
    size: rowsPerPage,
    search: userFilters.search,
  });
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const deleteUser = useDeleteUser();
  const deleteUsers = useDeleteUsers();
  const toggleStatus = useToggleUserStatus();
  const [bulkActionAnchor, setBulkActionAnchor] = useState<null | HTMLElement>(null);

  const users = data?.data || [];
  const totalCount = data?.total || 0;

  const handleChangePage = (_: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleSelectAllClick = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.checked) {
      const newSelected = users.map((user: any) => user.id);
      setSelected(newSelected);
    } else {
      setSelected([]);
    }
  };

  const handleSelectClick = (id: string) => {
    const selectedIndex = selected.indexOf(id);
    let newSelected: string[] = [];

    if (selectedIndex === -1) {
      newSelected = newSelected.concat(selected, id);
    } else if (selectedIndex === 0) {
      newSelected = newSelected.concat(selected.slice(1));
    } else if (selectedIndex === selected.length - 1) {
      newSelected = newSelected.concat(selected.slice(0, -1));
    } else if (selectedIndex > 0) {
      newSelected = newSelected.concat(
        selected.slice(0, selectedIndex),
        selected.slice(selectedIndex + 1)
      );
    }

    setSelected(newSelected);
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, userId: string) => {
    setAnchorEl(event.currentTarget);
    setSelectedUserId(userId);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedUserId(null);
  };

  const handleEdit = () => {
    const user = users.find((u: any) => u.id === selectedUserId);
    if (user) {
      setEditingUser(user);
      setDialogOpen(true);
    }
    handleMenuClose();
  };

  const handleDelete = async () => {
    if (selectedUserId) {
      await deleteUser.mutateAsync(selectedUserId);
    }
    handleMenuClose();
  };

  const handleToggleStatus = async () => {
    const user = users.find((u: any) => u.id === selectedUserId);
    if (user) {
      await toggleStatus.mutateAsync({
        userId: user.id,
        isActive: !user.is_active,
      });
    }
    handleMenuClose();
  };

  const handleBulkDelete = async () => {
    if (selected.length > 0 && window.confirm(`Delete ${selected.length} users?`)) {
      await deleteUsers.mutateAsync(selected);
      setSelected([]);
    }
  };

  const handleBulkStatusToggle = async (activate: boolean) => {
    if (selected.length > 0) {
      await Promise.all(
        selected.map((userId) => 
          toggleStatus.mutateAsync({ userId, isActive: activate })
        )
      );
      setSelected([]);
    }
    setBulkActionAnchor(null);
  };

  const handleExportUsers = () => {
    // Create CSV data
    const csvData = users
      .filter(user => selected.includes(user.id))
      .map(user => ({
        Name: user.full_name,
        Email: user.email,
        Role: user.role,
        Status: user.is_active ? 'Active' : 'Inactive',
        Created: new Date(user.created_at).toLocaleDateString(),
      }));
    
    // Convert to CSV string
    const headers = Object.keys(csvData[0] || {});
    const csvString = [
      headers.join(','),
      ...csvData.map(row => headers.map(header => (row as any)[header]).join(','))
    ].join('\n');
    
    // Download file
    const blob = new Blob([csvString], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `users-export-${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
    setBulkActionAnchor(null);
  };

  const handleSubmit = async (data: any) => {
    if (editingUser) {
      await updateUser.mutateAsync({
        userId: editingUser.id,
        data,
      });
    } else {
      await createUser.mutateAsync(data);
    }
    setDialogOpen(false);
    setEditingUser(null);
  };

  const getRoleColor = (role: UserRole) => {
    switch (role) {
      case UserRole.SUPER_ADMIN:
        return 'error';
      case UserRole.AGENCY_OWNER:
        return 'warning';
      case UserRole.AGENCY_ADMIN:
        return 'info';
      case UserRole.MODEL:
        return 'success';
      case UserRole.CHATTER:
        return 'secondary';
      default:
        return 'default';
    }
  };

  const isSelected = (id: string) => selected.indexOf(id) !== -1;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Users</Typography>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={() => {
            setEditingUser(null);
            setDialogOpen(true);
          }}
        >
          Add User
        </Button>
      </Box>

      <Paper>
        {selected.length > 0 && (
          <Toolbar
            sx={{
              pl: { sm: 2 },
              pr: { xs: 1, sm: 1 },
              ...(selected.length > 0 && {
                bgcolor: (theme) =>
                  alpha(theme.palette.primary.main, theme.palette.action.activatedOpacity),
              }),
            }}
          >
            <Typography sx={{ flex: '1 1 100%' }} color="inherit" variant="subtitle1">
              {selected.length} selected
            </Typography>
            <Box display="flex" gap={1}>
              <Button 
                color="inherit" 
                onClick={(event) => setBulkActionAnchor(event.currentTarget)}
                endIcon={<MoreVert />}
              >
                Bulk Actions
              </Button>
              <Menu
                anchorEl={bulkActionAnchor}
                open={Boolean(bulkActionAnchor)}
                onClose={() => setBulkActionAnchor(null)}
              >
                <MenuItem onClick={() => handleBulkStatusToggle(true)}>
                  <CheckCircle fontSize="small" sx={{ mr: 1 }} /> Activate Selected
                </MenuItem>
                <MenuItem onClick={() => handleBulkStatusToggle(false)}>
                  <Block fontSize="small" sx={{ mr: 1 }} /> Deactivate Selected
                </MenuItem>
                <MenuItem onClick={handleExportUsers}>
                  <Download fontSize="small" sx={{ mr: 1 }} /> Export Selected
                </MenuItem>
                <MenuItem onClick={handleBulkDelete} sx={{ color: 'error.main' }}>
                  <Delete fontSize="small" sx={{ mr: 1 }} /> Delete Selected
                </MenuItem>
              </Menu>
              <Button color="inherit" onClick={() => setSelected([])}>
                Clear Selection
              </Button>
            </Box>
          </Toolbar>
        )}

        <Box sx={{ p: 2 }}>
          <TextField
            fullWidth
            placeholder="Search users..."
            value={userFilters.search}
            onChange={(e) => setUserFilters({ search: e.target.value })}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Search />
                </InputAdornment>
              ),
            }}
          />
        </Box>

        {isPending ? (
          <Box sx={{ p: 3, textAlign: 'center' }}>
            <Typography>Loading...</Typography>
          </Box>
        ) : users.length === 0 ? (
          <Box sx={{ p: 3, textAlign: 'center' }}>
            <Typography>No users found</Typography>
          </Box>
        ) : (
          <UserListView
            users={users.map((user: any) => ({
              ...user,
              username: user.full_name || user.username,
              status: user.is_active ? 'active' : 'inactive',
            }))}
            selected={selected}
            onSelectAll={handleSelectAllClick}
            onSelectOne={handleSelectClick}
            onEdit={(user) => {
              setEditingUser(user);
              setDialogOpen(true);
            }}
            onDelete={handleDeleteUser}
            onToggleStatus={async (userId, status) => {
              await toggleStatus.mutateAsync({
                userId,
                isActive: status === 'active',
              });
            }}
            onMenuClick={handleMenuOpen}
            viewMode={users.length > 20 ? 'virtual' : 'table'}
          />
        )}

        <TablePagination
          rowsPerPageOptions={[5, 10, 25]}
          component="div"
          count={totalCount}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={handleChangePage}
          onRowsPerPageChange={handleChangeRowsPerPage}
        />
      </Paper>

      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={handleEdit}>
          <Edit fontSize="small" sx={{ mr: 1 }} /> Edit
        </MenuItem>
        <MenuItem onClick={handleToggleStatus}>
          <Block fontSize="small" sx={{ mr: 1 }} /> Toggle Status
        </MenuItem>
        <MenuItem onClick={handleDelete} sx={{ color: 'error.main' }}>
          <Delete fontSize="small" sx={{ mr: 1 }} /> Delete
        </MenuItem>
      </Menu>

      <UserDialog
        open={dialogOpen}
        onClose={() => {
          setDialogOpen(false);
          setEditingUser(null);
        }}
        onSubmit={handleSubmit}
        user={editingUser}
        loading={createUser.isPending || updateUser.isPending}
      />
    </Box>
  );
};

export default UsersPage;
