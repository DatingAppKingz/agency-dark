import React from 'react';
import {
  Box,
  Typography,
  Button,
  IconButton,
  TextField,
  FormControl,
  Select,
  MenuItem,
  Card,
  CardContent,
  Chip,
  Grid,
  InputLabel,
  Autocomplete } from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  FilterList as FilterIcon } from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { ReportFilter } from '@/types/reports';

interface FilterBuilderProps {
  filters: ReportFilter[];
  onChange: (filters: ReportFilter[]) => void;
  availableFields?: {
    field: string;
    label: string;
    type: 'text' | 'number' | 'date' | 'select';
    operators: string[];
    options?: { value: string; label: string }[];
  }[];
}

const FilterBuilder: React.FC<FilterBuilderProps> = ({
  filters,
  onChange,
  availableFields = [] }) => {
  // const [someState] = useState(false); // TODO: Remove or implement

  const defaultOperators = {
    text: ['equals', 'not_equals', 'contains', 'not_contains'],
    number: ['equals', 'not_equals', 'greater_than', 'less_than', 'between'],
    date: ['equals', 'not_equals', 'greater_than', 'less_than', 'between'],
    select: ['equals', 'not_equals', 'in', 'not_in'] };

  const addFilter = () => {
    const newFilter: ReportFilter = {
      id: `filter-${Date.now()}`,
      field: availableFields[0]?.field || '',
      operator: 'equals',
      value: '' };
    onChange([...filters, newFilter]);
  };

  const updateFilter = (filterId: string, updates: Partial<ReportFilter>) => {
    onChange(
      filters.map((f) => (f.id === filterId ? { ...f, ...updates } : f))
    );
  };

  const removeFilter = (filterId: string) => {
    onChange(filters.filter((f) => f.id !== filterId));
  };

  const getFieldConfig = (field: string) => {
    return availableFields.find((f) => f.field === field);
  };

  const renderValueInput = (filter: ReportFilter) => {
    const fieldConfig = getFieldConfig(filter.field);
    const fieldType = fieldConfig?.type || 'text';

    switch (fieldType) {
      case 'date':
        if (filter.operator === 'between') {
          return (
            <LocalizationProvider dateAdapter={AdapterDateFns}>
              <Grid container spacing={1}>
                <Grid item xs={6}>
                  <DatePicker
                    label="From"
                    value={filter.value?.[0] ? new Date(filter.value[0]) : null}
                    onChange={(date) =>
                      updateFilter(filter.id, {
                        value: [date?.toISOString(), filter.value?.[1] || ''] })
                    }
                    slotProps={{ textField: { size: 'small', fullWidth: true } }}
                  />
                </Grid>
                <Grid item xs={6}>
                  <DatePicker
                    label="To"
                    value={filter.value?.[1] ? new Date(filter.value[1]) : null}
                    onChange={(date) =>
                      updateFilter(filter.id, {
                        value: [filter.value?.[0] || '', date?.toISOString()] })
                    }
                    slotProps={{ textField: { size: 'small', fullWidth: true } }}
                  />
                </Grid>
              </Grid>
            </LocalizationProvider>
          );
        }
        return (
          <LocalizationProvider dateAdapter={AdapterDateFns}>
            <DatePicker
              label="Value"
              value={filter.value ? new Date(filter.value) : null}
              onChange={(date) =>
                updateFilter(filter.id, { value: date?.toISOString() })
              }
              slotProps={{ textField: { size: 'small', fullWidth: true } }}
            />
          </LocalizationProvider>
        );

      case 'number':
        if (filter.operator === 'between') {
          return (
            <Grid container spacing={1}>
              <Grid item xs={6}>
                <TextField
                  type="number"
                  label="Min"
                  size="small"
                  fullWidth
                  value={filter.value?.[0] || ''}
                  onChange={(e) =>
                    updateFilter(filter.id, {
                      value: [e.target.value, filter.value?.[1] || ''] })
                  }
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  type="number"
                  label="Max"
                  size="small"
                  fullWidth
                  value={filter.value?.[1] || ''}
                  onChange={(e) =>
                    updateFilter(filter.id, {
                      value: [filter.value?.[0] || '', e.target.value] })
                  }
                />
              </Grid>
            </Grid>
          );
        }
        return (
          <TextField
            type="number"
            label="Value"
            size="small"
            fullWidth
            value={filter.value || ''}
            onChange={(e) => updateFilter(filter.id, { value: e.target.value })}
          />
        );

      case 'select': {
        const options = fieldConfig?.options || [];
        if (filter.operator === 'in' || (filter.operator as any) === 'not_in') {
          return (
            <Autocomplete
              multiple
              options={options}
              getOptionLabel={(option) => option.label}
              value={
                options.filter((opt) =>
                  Array.isArray(filter.value) ? filter.value.includes(opt.value) : false
                ) || []
              }
              onChange={(_, newValue) =>
                updateFilter(filter.id, {
                  value: newValue.map((v) => v.value) })
              }
              renderInput={(params) => (
                <TextField {...params} label="Values" size="small" />
              )}
              renderTags={(value, getTagProps) =>
                value.map((option, index) => (
                  <Chip
                    label={option.label}
                    size="small"
                    {...getTagProps({ index })}
                  />
                ))
              }
            />
          );
        }
        return (
          <FormControl fullWidth size="small">
            <InputLabel>Value</InputLabel>
            <Select
              value={filter.value || ''}
              onChange={(e) => updateFilter(filter.id, { value: e.target.value })}
              label="Value"
            >
              {options.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        );
      }

      default:
        return (
          <TextField
            label="Value"
            size="small"
            fullWidth
            value={filter.value || ''}
            onChange={(e) => updateFilter(filter.id, { value: e.target.value })}
          />
        );
    }
  };

  return (
    <Box>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
        <Typography variant="h6">Filters</Typography>
        <Button
          startIcon={<AddIcon />}
          onClick={addFilter}
          disabled={availableFields.length === 0}
        >
          Add Filter
        </Button>
      </Box>

      {filters.length === 0 ? (
        <Box
          sx={{
            p: 3,
            textAlign: 'center',
            bgcolor: 'background.paper',
            borderRadius: 1,
            border: 1,
            borderColor: 'divider',
            borderStyle: 'dashed' }}
        >
          <FilterIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 1 }} />
          <Typography variant="body2" color="text.secondary">
            No filters applied
          </Typography>
        </Box>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {filters.map((filter, index) => {
            const fieldConfig = getFieldConfig(filter.field);
            const fieldType = fieldConfig?.type || 'text';
            const operators = fieldConfig?.operators || defaultOperators[fieldType] || [];

            return (
              <Card key={filter.id} variant="outlined">
                <CardContent>
                  <Grid container spacing={2} alignItems="center">
                    <Grid item xs={12} sm={4}>
                      <FormControl fullWidth size="small">
                        <InputLabel>Field</InputLabel>
                        <Select
                          value={filter.field}
                          onChange={(e) =>
                            updateFilter(filter.id, {
                              field: e.target.value,
                              operator: 'equals',
                              value: '' })
                          }
                          label="Field"
                        >
                          {availableFields.map((field) => (
                            <MenuItem key={field.field} value={field.field}>
                              {field.label}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    </Grid>
                    <Grid item xs={12} sm={3}>
                      <FormControl fullWidth size="small">
                        <InputLabel>Operator</InputLabel>
                        <Select
                          value={filter.operator}
                          onChange={(e) =>
                            updateFilter(filter.id, { operator: e.target.value as any })
                          }
                          label="Operator"
                        >
                          {operators.map((op) => (
                            <MenuItem key={op} value={op}>
                              {op.replace(/_/g, ' ')}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    </Grid>
                    <Grid item xs={12} sm={4}>
                      {renderValueInput(filter)}
                    </Grid>
                    <Grid item xs={12} sm={1}>
                      <IconButton
                        onClick={() => removeFilter(filter.id)}
                        color="error"
                      >
                        <DeleteIcon />
                      </IconButton>
                    </Grid>
                  </Grid>
                  {index < filters.length - 1 && (
                    <Typography
                      variant="caption"
                      sx={{
                        display: 'block',
                        textAlign: 'center',
                        mt: 1,
                        color: 'text.secondary' }}
                    >
                      AND
                    </Typography>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </Box>
      )}
    </Box>
  );
};

export default FilterBuilder;
