import React, { useState } from 'react';
import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
  IconButton,
  TextField,
  InputAdornment,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  FormControl,
  Select,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
} from '@mui/material';
import {
  Add as AddIcon,
  Search as SearchIcon,
  ExpandMore as ExpandMoreIcon,
  CalendarToday as TimeIcon,
  Person as UserIcon,
  Description as ContentIcon,
  Language as PlatformIcon,
  Category as CategoryIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import { ReportDimension } from '@/types/reports';

interface DimensionSelectorProps {
  availableDimensions: {
    time: ReportDimension[];
    user: ReportDimension[];
    content: ReportDimension[];
    platform: ReportDimension[];
  };
  selectedDimensions: ReportDimension[];
  onChange: (dimensions: ReportDimension[]) => void;
}

const DimensionSelector: React.FC<DimensionSelectorProps> = ({
  availableDimensions,
  selectedDimensions,
  onChange,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [editingDimension, setEditingDimension] = useState<ReportDimension | null>(null);

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'time':
        return <TimeIcon />;
      case 'user':
        return <UserIcon />;
      case 'content':
        return <ContentIcon />;
      case 'platform':
        return <PlatformIcon />;
      default:
        return <CategoryIcon />;
    }
  };

  const addDimension = (dimension: ReportDimension) => {
    // Don't add if already selected
    if (selectedDimensions.some(d => d.field === dimension.field)) {
      return;
    }
    const newDimension = { ...dimension, id: `${dimension.field}-${Date.now()}` };
    onChange([...selectedDimensions, newDimension]);
  };

  const updateDimension = (dimensionId: string, updates: Partial<ReportDimension>) => {
    onChange(
      selectedDimensions.map((d) => (d.id === dimensionId ? { ...d, ...updates } : d))
    );
  };

  const removeDimension = (dimensionId: string) => {
    onChange(selectedDimensions.filter((d) => d.id !== dimensionId));
  };

  const filterDimensions = (dimensions: ReportDimension[]) => {
    if (!searchTerm) return dimensions;
    return dimensions.filter(
      (dimension) =>
        dimension.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        dimension.field.toLowerCase().includes(searchTerm.toLowerCase())
    );
  };

  const isSelected = (dimension: ReportDimension) => {
    return selectedDimensions.some(d => d.field === dimension.field);
  };

  return (
    <Box>
      <TextField
        size="small"
        fullWidth
        placeholder="Search dimensions..."
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              <SearchIcon />
            </InputAdornment>
          ),
        }}
        sx={{ mb: 2 }}
      />

      {/* Selected Dimensions */}
      {selectedDimensions.length > 0 && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="subtitle2" gutterBottom>
            Selected Dimensions ({selectedDimensions.length})
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {selectedDimensions.map((dimension) => (
              <Chip
                key={dimension.id}
                label={dimension.name}
                onDelete={() => removeDimension(dimension.id)}
                onClick={() => setEditingDimension(dimension)}
                size="small"
              />
            ))}
          </Box>
        </Box>
      )}

      {/* Available Dimensions */}
      <Typography variant="subtitle2" gutterBottom>
        Available Dimensions
      </Typography>
      {Object.entries(availableDimensions).map(([category, dimensions]) => (
        <Accordion key={category} defaultExpanded={category === 'time'}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {getCategoryIcon(category)}
              <Typography textTransform="capitalize">{category}</Typography>
              <Chip label={filterDimensions(dimensions).length} size="small" />
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            <List dense>
              {filterDimensions(dimensions).map((dimension) => (
                <ListItem 
                  key={dimension.field} 
                  button 
                  onClick={() => !isSelected(dimension) && addDimension(dimension)}
                  disabled={isSelected(dimension)}
                >
                  <ListItemIcon>
                    <CategoryIcon fontSize="small" />
                  </ListItemIcon>
                  <ListItemText
                    primary={dimension.name}
                    secondary={
                      <Box>
                        <Typography variant="caption">{dimension.field}</Typography>
                        {dimension.type === 'date' && dimension.groupBy && (
                          <Chip
                            label={`Group by ${dimension.groupBy}`}
                            size="small"
                            sx={{ ml: 1, height: 16 }}
                          />
                        )}
                      </Box>
                    }
                  />
                  <ListItemSecondaryAction>
                    <IconButton 
                      edge="end" 
                      size="small" 
                      onClick={() => !isSelected(dimension) && addDimension(dimension)}
                      disabled={isSelected(dimension)}
                    >
                      <AddIcon />
                    </IconButton>
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
            </List>
          </AccordionDetails>
        </Accordion>
      ))}

      {/* Edit Dimension Dialog */}
      <Dialog
        open={!!editingDimension}
        onClose={() => setEditingDimension(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Edit Dimension</DialogTitle>
        <DialogContent>
          {editingDimension && (
            <Box sx={{ mt: 2 }}>
              <TextField
                label="Display Name"
                fullWidth
                value={editingDimension.name}
                onChange={(e) =>
                  setEditingDimension({ ...editingDimension, name: e.target.value })
                }
                sx={{ mb: 2 }}
              />
              {editingDimension.type === 'date' && (
                <FormControl fullWidth>
                  <Typography variant="caption" gutterBottom>
                    Group By
                  </Typography>
                  <Select
                    value={editingDimension.groupBy || 'day'}
                    onChange={(e) =>
                      setEditingDimension({
                        ...editingDimension,
                        groupBy: e.target.value as any,
                      })
                    }
                  >
                    <MenuItem value="day">Day</MenuItem>
                    <MenuItem value="week">Week</MenuItem>
                    <MenuItem value="month">Month</MenuItem>
                    <MenuItem value="year">Year</MenuItem>
                  </Select>
                </FormControl>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditingDimension(null)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={() => {
              if (editingDimension) {
                updateDimension(editingDimension.id, editingDimension);
                setEditingDimension(null);
              }
            }}
          >
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default DimensionSelector;