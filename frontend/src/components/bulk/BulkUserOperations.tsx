import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Checkbox,
  Chip,
  IconButton,
  Avatar,
  Menu,
  MenuItem,
  TextField,
  InputAdornment,
  FormControl,
  InputLabel,
  Select,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormGroup,
  FormControlLabel,
  Switch,
  Grid,
  Divider,
  Tooltip,
  LinearProgress } from '@mui/material';
import {
  Search as SearchIcon,
  FilterList as MoreIcon,
  PersonOff as DeactivateIcon,
  PersonAdd as ActivateIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  Group as ExportIcon,
  Upload as AssignIcon,
  CheckCircle as SuccessIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { bulkOperationsService } from '@/services/api/bulkOperations';
import { userService } from '@/services/api/users';
import { BulkOperationType, BulkOperationCreate } from '@/types/bulkOperations';
import { UserRole } from '@/types/auth';
import BulkOperationProgress from './BulkOperationProgress';

interface BulkUserOperationsProps {
  role?: UserRole;
}

interface BulkUpdateData {
  role?: UserRole;
  agency_id?: string;
  is_active?: boolean;
  is_verified?: boolean;
  tags?: string[];
  custom_fields?: Record<string, any>;
  format?: string;
}

const BulkUserOperations: React.FC<BulkUserOperationsProps> = ({ role }) => {
  const [selectedUsers, setSelectedUsers] = useState<string[]>([]);
  const [selectAll, setSelectAll] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterRole, setFilterRole] = useState<UserRole | ''>('');
  const [showBulkDialog, setShowBulkDialog] = useState(false);
  const [bulkOperation, setBulkOperation] = useState<BulkOperationType | null>(null);
  const [bulkUpdateData, setBulkUpdateData] = useState<BulkUpdateData>({});
  const [activeOperation, setActiveOperation] = useState<string | null>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const queryClient = useQueryClient();

  // Fetch users
  const { data: users, isPending } = useQuery({
    queryKey: ['users', role, filterRole, searchTerm],
    queryFn: () => userService.getUsers({
      role: role || filterRole || undefined,
      search: searchTerm || undefined,
      limit: 100 }) });

  // Create bulk operation
  const createBulkOperation = useMutation({
    mutationFn: (data: BulkOperationCreate) => bulkOperationsService.createBulkOperation(data),
    onSuccess: (response) => {
      toast.success('Bulk operation started');
      setActiveOperation(response.id);
      queryClient.invalidateQueries({ queryKey: ['bulk-operations'] });
      queryClient.invalidateQueries({ queryKey: ['users'] });
      resetSelection();
      setShowBulkDialog(false);
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      toast.error(error.response?.data?.detail || 'Failed to start bulk operation');
    } });

  const handleSelectAll = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.checked) {
      const allUserIds = users?.data.map(user => user.id) || [];
      setSelectedUsers(allUserIds);
      setSelectAll(true);
    } else {
      setSelectedUsers([]);
      setSelectAll(false);
    }
  };

  const handleSelectUser = (userId: string) => {
    setSelectedUsers(prev => {
      if (prev.includes(userId)) {
        return prev.filter(id => id !== userId);
      } else {
        return [...prev, userId];
      }
    });
  };

  const resetSelection = () => {
    setSelectedUsers([]);
    setSelectAll(false);
    setBulkUpdateData({});
  };

  const handleBulkOperation = (operation: BulkOperationType) => {
    if (selectedUsers.length === 0) {
      toast.error('Please select at least one user');
      return;
    }
    setBulkOperation(operation);
    setShowBulkDialog(true);
  };

  const executeBulkOperation = () => {
    if (!bulkOperation) return;

    const operationData = {
      operation_type: bulkOperation,
      entity_type: 'users',
      entity_ids: selectedUsers,
      operation_params: bulkUpdateData,
      notes: `Bulk ${bulkOperation} for ${selectedUsers.length} users` };

    createBulkOperation.mutate(operationData);
  };

  const getRoleColor = (role: UserRole) => {
    const colors: Record<UserRole, any> = {
      [UserRole.SUPER_ADMIN]: 'error',
      [UserRole.AGENCY_OWNER]: 'warning',
      [UserRole.AGENCY_ADMIN]: 'info',
      [UserRole.MODEL]: 'success',
      [UserRole.CHATTER]: 'primary',
      [UserRole.AGENCY_MEMBER]: 'default' };
    return colors[role] || 'default';
  };

  const renderBulkActions = () => (
    <Box display="flex" gap={1} flexWrap="wrap">
      <Button
        size="small"
        startIcon={<ActivateIcon />}
        onClick={() => handleBulkOperation(BulkOperationType.USER_ACTIVATE)}
        disabled={selectedUsers.length === 0}
      >
        Activate
      </Button>
      <Button
        size="small"
        startIcon={<DeactivateIcon />}
        onClick={() => handleBulkOperation(BulkOperationType.USER_DEACTIVATE)}
        disabled={selectedUsers.length === 0}
      >
        Deactivate
      </Button>
      <Button
        size="small"
        startIcon={<EditIcon />}
        onClick={() => handleBulkOperation(BulkOperationType.USER_UPDATE)}
        disabled={selectedUsers.length === 0}
      >
        Update
      </Button>
      {role === UserRole.MODEL && (
        <Button
          size="small"
          startIcon={<AssignIcon />}
          onClick={() => handleBulkOperation(BulkOperationType.MODEL_ASSIGN)}
          disabled={selectedUsers.length === 0}
        >
          Assign
        </Button>
      )}
      <Button
        size="small"
        startIcon={<DeleteIcon />}
        color="error"
        onClick={() => handleBulkOperation(BulkOperationType.USER_DELETE)}
        disabled={selectedUsers.length === 0}
      >
        Delete
      </Button>
      <Button
        size="small"
        startIcon={<ExportIcon />}
        onClick={() => handleBulkOperation(BulkOperationType.DATA_EXPORT)}
      >
        Export
      </Button>
    </Box>
  );

  const renderBulkDialog = () => {
    if (!bulkOperation) return null;

    const dialogTitles: Partial<Record<BulkOperationType, string>> = {
      [BulkOperationType.USER_ACTIVATE]: 'Activate Users',
      [BulkOperationType.USER_DEACTIVATE]: 'Deactivate Users',
      [BulkOperationType.USER_UPDATE]: 'Update Users',
      [BulkOperationType.USER_DELETE]: 'Delete Users',
      [BulkOperationType.MODEL_ASSIGN]: 'Assign Models',
      [BulkOperationType.DATA_EXPORT]: 'Export Users' };

    return (
      <Dialog open={showBulkDialog} onClose={() => setShowBulkDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{dialogTitles[bulkOperation] || 'Bulk Operation'}</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            {(bulkOperation === BulkOperationType.USER_ACTIVATE || 
              bulkOperation === BulkOperationType.USER_DEACTIVATE) && (
              <Alert severity="info">
                This will {bulkOperation === BulkOperationType.USER_ACTIVATE ? 'activate' : 'deactivate'} {selectedUsers.length} selected users.
              </Alert>
            )}

            {bulkOperation === BulkOperationType.USER_UPDATE && (
              <Grid container spacing={2}>
                <Grid item xs={12}>
                  <FormControl fullWidth>
                    <InputLabel>Update Role</InputLabel>
                    <Select
                      value={bulkUpdateData.role || ''}
                      onChange={(e) => setBulkUpdateData({ ...bulkUpdateData, role: e.target.value as UserRole })}
                      label="Update Role"
                    >
                      <MenuItem value="">No Change</MenuItem>
                      {Object.values(UserRole).map(role => (
                        <MenuItem key={role} value={role}>{role.replace('_', ' ')}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12}>
                  <FormGroup>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={bulkUpdateData.is_verified || false}
                          onChange={(e) => setBulkUpdateData({ ...bulkUpdateData, is_verified: e.target.checked })}
                        />
                      }
                      label="Mark as Verified"
                    />
                  </FormGroup>
                </Grid>
                <Grid item xs={12}>
                  <TextField
                    label="Add Tags (comma separated)"
                    fullWidth
                    value={bulkUpdateData.tags?.join(', ') || ''}
                    onChange={(e) => setBulkUpdateData({ 
                      ...bulkUpdateData, 
                      tags: e.target.value.split(',').map(t => t.trim()).filter(t => t) 
                    })}
                  />
                </Grid>
              </Grid>
            )}

            {bulkOperation === BulkOperationType.USER_DELETE && (
              <Alert severity="error">
                <Typography variant="body2">
                  <strong>Warning:</strong> This action cannot be undone. {selectedUsers.length} users will be permanently deleted.
                </Typography>
              </Alert>
            )}

            {bulkOperation === BulkOperationType.DATA_EXPORT && (
              <Grid container spacing={2}>
                <Grid item xs={12}>
                  <FormControl fullWidth>
                    <InputLabel>Export Format</InputLabel>
                    <Select
                      value={bulkUpdateData.format || 'csv'}
                      onChange={(e) => setBulkUpdateData({ ...bulkUpdateData, format: e.target.value })}
                      label="Export Format"
                    >
                      <MenuItem value="csv">CSV</MenuItem>
                      <MenuItem value="xlsx">Excel</MenuItem>
                      <MenuItem value="json">JSON</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12}>
                  <FormGroup>
                    <FormControlLabel
                      control={<Checkbox defaultChecked />}
                      label="Include personal information"
                    />
                    <FormControlLabel
                      control={<Checkbox defaultChecked />}
                      label="Include activity data"
                    />
                    <FormControlLabel
                      control={<Checkbox />}
                      label="Include financial data"
                    />
                  </FormGroup>
                </Grid>
              </Grid>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowBulkDialog(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={executeBulkOperation}
            disabled={createBulkOperation.isPending}
            color={bulkOperation === BulkOperationType.USER_DELETE ? 'error' : 'primary'}
          >
            {bulkOperation === BulkOperationType.USER_DELETE ? 'Delete' : 'Confirm'}
          </Button>
        </DialogActions>
      </Dialog>
    );
  };

  return (
    <Box>
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6">
              {role ? `${role.replace('_', ' ')} Management` : 'User Management'}
            </Typography>
            {selectedUsers.length > 0 && (
              <Chip
                label={`${selectedUsers.length} selected`}
                onDelete={resetSelection}
                color="primary"
              />
            )}
          </Box>

          {/* Search and Filter */}
          <Grid container spacing={2} sx={{ mb: 2 }}>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                size="small"
                placeholder="Search users..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon />
                    </InputAdornment>
                  ) }}
              />
            </Grid>
            {!role && (
              <Grid item xs={12} md={3}>
                <FormControl fullWidth size="small">
                  <InputLabel>Filter by Role</InputLabel>
                  <Select
                    value={filterRole}
                    onChange={ (e) => setFilterRole(e.target.value as UserRole | '')       }
                    label="Filter by Role"
                  >
                    <MenuItem value="">All Roles</MenuItem>
                    {Object.values(UserRole).map(r => (
                      <MenuItem key={r} value={r}>{r.replace('_', ' ')}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
            )}
          </Grid>

          {/* Bulk Actions */}
          {selectedUsers.length > 0 && (
            <Box sx={{ mb: 2 }}>
              {renderBulkActions()}
            </Box>
          )}

          {/* Users Table */}
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell padding="checkbox">
                    <Checkbox
                      checked={selectAll}
                      indeterminate={selectedUsers.length > 0 && selectedUsers.length < (users?.data.length || 0)}
                      onChange={handleSelectAll}
                    />
                  </TableCell>
                  <TableCell>User</TableCell>
                  <TableCell>Email</TableCell>
                  <TableCell>Role</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Joined</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {isPending ? (
                  <TableRow>
                    <TableCell colSpan={7} align="center">
                      <LinearProgress />
                    </TableCell>
                  </TableRow>
                ) : users?.data.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} align="center">
                      <Typography variant="body2" color="text.secondary">
                        No users found
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  users?.data.map((user) => (
                    <TableRow key={user.id} selected={selectedUsers.includes(user.id)}>
                      <TableCell padding="checkbox">
                        <Checkbox
                          checked={selectedUsers.includes(user.id)}
                          onChange={() => handleSelectUser(user.id)}
                        />
                      </TableCell>
                      <TableCell>
                        <Box display="flex" alignItems="center" gap={1}>
                          <Avatar src={user.avatar_url} sx={{ width: 32, height: 32 }}>
                            {user.full_name?.charAt(0) || user.email.charAt(0)}
                          </Avatar>
                          <Box>
                            <Typography variant="body2">
                              {user.full_name || user.username || 'Unknown'}
                            </Typography>
                            {user.stage_name && (
                              <Typography variant="caption" color="text.secondary">
                                {user.stage_name}
                              </Typography>
                            )}
                          </Box>
                        </Box>
                      </TableCell>
                      <TableCell>{user.email}</TableCell>
                      <TableCell>
                        <Chip
                          label={user.role.replace('_', ' ')}
                          size="small"
                          color={getRoleColor(user.role)}
                        />
                      </TableCell>
                      <TableCell>
                        <Box display="flex" gap={0.5}>
                          {user.is_active ? (
                            <Chip label="Active" size="small" color="success" />
                          ) : (
                            <Chip label="Inactive" size="small" color="default" />
                          )}
                          {user.is_verified && (
                            <Tooltip title="Verified">
                              <SuccessIcon fontSize="small" color="success" />
                            </Tooltip>
                          )}
                        </Box>
                      </TableCell>
                      <TableCell>
                        {new Date(user.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell align="right">
                        <IconButton
                          size="small"
                          onClick={(event) => setAnchorEl(event.currentTarget)}
                        >
                          <MoreIcon />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      {/* Bulk Operation Dialog */}
      {renderBulkDialog()}

      {/* Operation Progress */}
      {activeOperation && (
        <Box sx={{ mt: 2 }}>
          <BulkOperationProgress
            operationId={activeOperation}
            onComplete={() => {
              setActiveOperation(null);
              queryClient.invalidateQueries({ queryKey: ['users'] });
            }}
          />
        </Box>
      )}

      {/* Individual User Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={() => setAnchorEl(null)}
      >
        <MenuItem onClick={() => {
          // Handle individual user edit
          setAnchorEl(null);
        }}>
          <EditIcon fontSize="small" sx={{ mr: 1 }} /> Edit
        </MenuItem>
        <MenuItem onClick={() => {
          // Handle individual user deactivate
          setAnchorEl(null);
        }}>
          <DeactivateIcon fontSize="small" sx={{ mr: 1 }} /> Deactivate
        </MenuItem>
        <Divider />
        <MenuItem onClick={() => {
          // Handle individual user delete
          setAnchorEl(null);
        }} sx={{ color: 'error.main' }}>
          <DeleteIcon fontSize="small" sx={{ mr: 1 }} /> Delete
        </MenuItem>
      </Menu>
    </Box>
  );
};

export default BulkUserOperations;
