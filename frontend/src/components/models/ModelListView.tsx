import React, { useMemo } from 'react';
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Avatar,
  Chip,
  IconButton,
  Checkbox,
  Typography,
  Switch,
  Tooltip,
  Stack,
} from '@mui/material';
import {
  Edit,
  Delete,
  Visibility,
  MoreVert,
} from '@mui/icons-material';
import { VirtualList } from '@/components/common/VirtualList';
import { OptimizedImage } from '@/components/common/OptimizedImage';
import { ModelProfile, ModelStatus } from '@/types/models';
import { format } from 'date-fns';
import { UserRole } from '@/types/auth';
import { useAuthStore } from '@/store/authStore';

interface ModelListViewProps {
  models: ModelProfile[];
  selectedIds: string[];
  onSelectIds: (ids: string[]) => void;
  onEdit: (model: ModelProfile) => void;
  onDelete: (modelId: string) => void;
  onToggleStatus: (modelId: string, isActive: boolean) => void;
  viewMode?: 'table' | 'virtual';
}

export const ModelListView: React.FC<ModelListViewProps> = ({
  models,
  selectedIds,
  onSelectIds,
  onEdit,
  onDelete,
  onToggleStatus,
  viewMode = 'virtual',
}) => {
  const { user } = useAuthStore();
  
  const canManageModels = user && [
    UserRole.SUPER_ADMIN,
    UserRole.AGENCY_OWNER,
    UserRole.AGENCY_ADMIN,
  ].includes(user.role);

  const handleSelectAll = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.checked) {
      onSelectIds(models.map(m => m.id));
    } else {
      onSelectIds([]);
    }
  };

  const handleSelectOne = (modelId: string) => {
    const selectedIndex = selectedIds.indexOf(modelId);
    let newSelected: string[] = [];

    if (selectedIndex === -1) {
      newSelected = newSelected.concat(selectedIds, modelId);
    } else if (selectedIndex === 0) {
      newSelected = newSelected.concat(selectedIds.slice(1));
    } else if (selectedIndex === selectedIds.length - 1) {
      newSelected = newSelected.concat(selectedIds.slice(0, -1));
    } else if (selectedIndex > 0) {
      newSelected = newSelected.concat(
        selectedIds.slice(0, selectedIndex),
        selectedIds.slice(selectedIndex + 1)
      );
    }

    onSelectIds(newSelected);
  };

  const getStatusColor = (status: ModelStatus) => {
    switch (status) {
      case ModelStatus.ACTIVE:
        return 'success';
      case ModelStatus.INACTIVE:
        return 'default';
      case ModelStatus.PENDING:
        return 'warning';
      case ModelStatus.SUSPENDED:
        return 'error';
      default:
        return 'default';
    }
  };

  const formatEarnings = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const renderModelRow = (model: ModelProfile, index: number) => {
    const isSelected = selectedIds.includes(model.id);

    return (
      <TableRow
        hover
        role="checkbox"
        aria-checked={isSelected}
        tabIndex={-1}
        key={model.id}
        selected={isSelected}
        sx={{ height: 72 }}
      >
        <TableCell padding="checkbox">
          <Checkbox
            checked={isSelected}
            onChange={() => handleSelectOne(model.id)}
          />
        </TableCell>
        <TableCell component="th" scope="row">
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Avatar
              sx={{ width: 48, height: 48 }}
              src={model.profile_image}
              alt={model.stage_name}
            >
              {model.stage_name[0]}
            </Avatar>
            <Box>
              <Typography variant="subtitle1" fontWeight="medium">
                {model.stage_name}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {model.email}
              </Typography>
            </Box>
          </Box>
        </TableCell>
        <TableCell>
          <Chip
            label={model.status}
            color={getStatusColor(model.status)}
            size="small"
          />
        </TableCell>
        <TableCell align="right">{formatEarnings(model.total_earnings || 0)}</TableCell>
        <TableCell align="right">{model.total_fans || 0}</TableCell>
        <TableCell align="right">{model.active_subscriptions || 0}</TableCell>
        <TableCell>
          <Typography variant="body2">
            {format(new Date(model.created_at), 'MMM d, yyyy')}
          </Typography>
        </TableCell>
        <TableCell>
          {canManageModels && (
            <Switch
              checked={model.status === ModelStatus.ACTIVE}
              onChange={(e) => onToggleStatus(model.id, e.target.checked)}
              size="small"
            />
          )}
        </TableCell>
        <TableCell align="right">
          <Stack direction="row" spacing={1} justifyContent="flex-end">
            <Tooltip title="View">
              <IconButton size="small">
                <Visibility fontSize="small" />
              </IconButton>
            </Tooltip>
            {canManageModels && (
              <>
                <Tooltip title="Edit">
                  <IconButton size="small" onClick={() => onEdit(model)}>
                    <Edit fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Delete">
                  <IconButton 
                    size="small" 
                    onClick={() => onDelete(model.id)}
                    color="error"
                  >
                    <Delete fontSize="small" />
                  </IconButton>
                </Tooltip>
              </>
            )}
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
            indeterminate={selectedIds.length > 0 && selectedIds.length < models.length}
            checked={models.length > 0 && selectedIds.length === models.length}
            onChange={handleSelectAll}
          />
        </TableCell>
        <TableCell>Model</TableCell>
        <TableCell>Status</TableCell>
        <TableCell align="right">Earnings</TableCell>
        <TableCell align="right">Fans</TableCell>
        <TableCell align="right">Subscriptions</TableCell>
        <TableCell>Joined</TableCell>
        <TableCell>Active</TableCell>
        <TableCell align="right">Actions</TableCell>
      </TableRow>
    </TableHead>
  );

  if (viewMode === 'virtual' && models.length > 20) {
    // Use virtual scrolling for large lists
    return (
      <TableContainer component={Paper}>
        <Table stickyHeader>
          {tableHeader}
        </Table>
        <Box sx={{ height: 'calc(100vh - 400px)', minHeight: 400 }}>
          <VirtualList
            items={models}
            itemHeight={72}
            renderItem={renderModelRow}
            height="100%"
            overscan={5}
            getItemKey={(model) => model.id}
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
          {models.map((model, index) => renderModelRow(model, index))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};