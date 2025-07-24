import { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  ToggleButton,
  ToggleButtonGroup,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  IconButton,
  Badge,
  Popover,
  Divider,
  Button,
} from '@mui/material';
import {
  FilterList,
  Clear,
  Inbox,
  Star,
  Archive,
  Person,
  Group,
} from '@mui/icons-material';
import { ChatFilters as ChatFiltersType } from '@/types/chat';
import { useAuthStore } from '@/store/authStore';
import { User } from '@/types';

interface ChatFiltersProps {
  filters: ChatFiltersType;
  onFiltersChange: (filters: Partial<ChatFiltersType>) => void;
  unreadCount: number;
  models?: User[];
}

export const ChatFilters = ({ 
  filters, 
  onFiltersChange, 
  unreadCount,
  models = []
}: ChatFiltersProps) => {
  const { user } = useAuthStore();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const handleFilterClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleStatusChange = (
    event: React.MouseEvent<HTMLElement>,
    newStatus: string | null,
  ) => {
    if (newStatus !== null) {
      onFiltersChange({ status: newStatus as ChatFiltersType['status'] });
    }
  };

  const handleAssignedToChange = (
    event: React.MouseEvent<HTMLElement>,
    newAssignedTo: string | null,
  ) => {
    if (newAssignedTo !== null) {
      onFiltersChange({ assigned_to: newAssignedTo as ChatFiltersType['assigned_to'] });
    }
  };

  const handleModelSelect = (modelId: string) => {
    onFiltersChange({ model_id: modelId });
  };

  const handleClearFilters = () => {
    onFiltersChange({
      search: '',
      status: 'all',
      assigned_to: 'me',
      model_id: undefined,
      tags: [],
    });
    handleClose();
  };

  const activeFiltersCount = [
    filters.status !== 'all',
    filters.assigned_to !== 'me',
    filters.model_id,
    filters.tags && filters.tags.length > 0,
  ].filter(Boolean).length;

  const open = Boolean(anchorEl);

  return (
    <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <Typography variant="h6" sx={{ flexGrow: 1 }}>
          Conversations
        </Typography>
        
        <IconButton onClick={handleFilterClick}>
          <Badge badgeContent={activeFiltersCount} color="primary">
            <FilterList />
          </Badge>
        </IconButton>
      </Box>

      {/* Quick Filters */}
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        <ToggleButtonGroup
          value={filters.status}
          exclusive
          onChange={handleStatusChange}
          size="small"
        >
          <ToggleButton value="all">
            <Inbox sx={{ mr: 0.5 }} />
            All
          </ToggleButton>
          <ToggleButton value="unread">
            <Badge badgeContent={unreadCount} color="error">
              <Inbox sx={{ mr: 0.5 }} />
            </Badge>
            Unread
          </ToggleButton>
          <ToggleButton value="pinned">
            <Star sx={{ mr: 0.5 }} />
            Pinned
          </ToggleButton>
          <ToggleButton value="archived">
            <Archive sx={{ mr: 0.5 }} />
            Archived
          </ToggleButton>
        </ToggleButtonGroup>

        {user?.role === 'agency_owner' && (
          <ToggleButtonGroup
            value={filters.assigned_to}
            exclusive
            onChange={handleAssignedToChange}
            size="small"
          >
            <ToggleButton value="me">
              <Person sx={{ mr: 0.5 }} />
              Me
            </ToggleButton>
            <ToggleButton value="team">
              <Group sx={{ mr: 0.5 }} />
              Team
            </ToggleButton>
            <ToggleButton value="unassigned">
              <Person sx={{ mr: 0.5 }} />
              Unassigned
            </ToggleButton>
          </ToggleButtonGroup>
        )}
      </Box>

      {/* Advanced Filters Popover */}
      <Popover
        open={open}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
      >
        <Paper sx={{ p: 3, width: 320 }}>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Advanced Filters
          </Typography>

          {models.length > 0 && (
            <FormControl fullWidth sx={{ mb: 2 }}>
              <InputLabel>Assigned Model</InputLabel>
              <Select
                value={filters.model_id || ''}
                onChange={(e) => handleModelSelect(e.target.value)}
                label="Assigned Model"
              >
                <MenuItem value="">All Models</MenuItem>
                {models.map((model) => (
                  <MenuItem key={model.id} value={model.id}>
                    {model.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}


          {filters.tags && filters.tags.length > 0 && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                Tags
              </Typography>
              <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                {filters.tags.map((tag) => (
                  <Chip
                    key={tag}
                    label={tag}
                    size="small"
                    onDelete={() => {
                      onFiltersChange({
                        tags: filters.tags?.filter(t => t !== tag)
                      });
                    }}
                  />
                ))}
              </Box>
            </Box>
          )}

          <Divider sx={{ my: 2 }} />

          <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
            <Button onClick={handleClearFilters}>
              Clear All
            </Button>
            <Button variant="contained" onClick={handleClose}>
              Apply
            </Button>
          </Box>
        </Paper>
      </Popover>
    </Box>
  );
};