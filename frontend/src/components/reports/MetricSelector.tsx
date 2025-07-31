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
  Button } from '@mui/material';
import {
  Add as AddIcon,
  Search as SearchIcon,
  ExpandMore as ExpandMoreIcon,
  Functions as FunctionIcon,
  AttachMoney as MoneyIcon,
  Person as PersonIcon,
  Message as MessageIcon,
  Image as ContentIcon,
  CreditCard as SubscriptionIcon } from '@mui/icons-material';
import { ReportMetric, AggregationType } from '@/types/reports';

interface MetricSelectorProps {
  availableMetrics: {
    revenue: ReportMetric[];
    users: ReportMetric[];
    messages: ReportMetric[];
    content: ReportMetric[];
    subscriptions: ReportMetric[];
  };
  selectedMetrics: ReportMetric[];
  onChange: (metrics: ReportMetric[]) => void;
}

const MetricSelector: React.FC<MetricSelectorProps> = ({
  availableMetrics,
  selectedMetrics,
  onChange }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [editingMetric, setEditingMetric] = useState<ReportMetric | null>(null);
  const [, setCustomMetricDialog] = useState(false);

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'revenue':
        return <MoneyIcon />;
      case 'users':
        return <PersonIcon />;
      case 'messages':
        return <MessageIcon />;
      case 'content':
        return <ContentIcon />;
      case 'subscriptions':
        return <SubscriptionIcon />;
      default:
        return <FunctionIcon />;
    }
  };

  const addMetric = (metric: ReportMetric) => {
    const newMetric = { ...metric, id: `${metric.field}-${Date.now()}` };
    onChange([...selectedMetrics, newMetric]);
  };

  const updateMetric = (metricId: string, updates: Partial<ReportMetric>) => {
    onChange(
      selectedMetrics.map((m) => (m.id === metricId ? { ...m, ...updates } : m))
    );
  };

  const removeMetric = (metricId: string) => {
    onChange(selectedMetrics.filter((m) => m.id !== metricId));
  };

  const filterMetrics = (metrics: ReportMetric[]) => {
    if (!searchTerm) return metrics;
    return metrics.filter(
      (metric) =>
        metric.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        metric.field.toLowerCase().includes(searchTerm.toLowerCase())
    );
  };

  return (
    <Box>
      <TextField
        size="small"
        fullWidth
        placeholder="Search metrics..."
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              <SearchIcon />
            </InputAdornment>
          ) }}
        sx={{ mb: 2 }}
      />

      {/* Selected Metrics */}
      {selectedMetrics.length > 0 && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="subtitle2" gutterBottom>
            Selected Metrics ({selectedMetrics.length})
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {selectedMetrics.map((metric) => (
              <Chip
                key={metric.id}
                label={metric.name}
                onDelete={() => removeMetric(metric.id)}
                onClick={() => setEditingMetric(metric)}
                size="small"
              />
            ))}
          </Box>
        </Box>
      )}

      {/* Available Metrics */}
      <Typography variant="subtitle2" gutterBottom>
        Available Metrics
      </Typography>
      {Object.entries(availableMetrics).map(([category, metrics]) => (
        <Accordion key={category} defaultExpanded={category === 'revenue'}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {getCategoryIcon(category)}
              <Typography textTransform="capitalize">{category}</Typography>
              <Chip label={filterMetrics(metrics).length} size="small" />
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            <List dense>
              {filterMetrics(metrics).map((metric) => (
                <ListItem key={metric.field} button onClick={() => addMetric(metric)}>
                  <ListItemIcon>
                    <FunctionIcon fontSize="small" />
                  </ListItemIcon>
                  <ListItemText
                    primary={metric.name}
                    secondary={metric.field}
                  />
                  <ListItemSecondaryAction>
                    <IconButton edge="end" size="small" onClick={() => addMetric(metric)}>
                      <AddIcon />
                    </IconButton>
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
            </List>
          </AccordionDetails>
        </Accordion>
      ))}

      {/* Custom Metric Button */}
      <Button
        fullWidth
        startIcon={<AddIcon />}
        onClick={() => setCustomMetricDialog(true)}
        sx={{ mt: 2 }}
      >
        Add Custom Metric
      </Button>

      {/* Edit Metric Dialog */}
      <Dialog
        open={!!editingMetric}
        onClose={() => setEditingMetric(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Edit Metric</DialogTitle>
        <DialogContent>
          {editingMetric && (
            <Box sx={{ mt: 2 }}>
              <TextField
                label="Display Name"
                fullWidth
                value={editingMetric.name}
                onChange={(e) =>
                  setEditingMetric({ ...editingMetric, name: e.target.value })
                }
                sx={{ mb: 2 }}
              />
              <FormControl fullWidth sx={{ mb: 2 }}>
                <Select
                  value={editingMetric.aggregation}
                  onChange={(e) =>
                    setEditingMetric({
                      ...editingMetric,
                      aggregation: e.target.value as AggregationType })
                  }
                >
                  <MenuItem value={AggregationType.SUM}>Sum</MenuItem>
                  <MenuItem value={AggregationType.AVERAGE}>Average</MenuItem>
                  <MenuItem value={AggregationType.COUNT}>Count</MenuItem>
                  <MenuItem value={AggregationType.MIN}>Minimum</MenuItem>
                  <MenuItem value={AggregationType.MAX}>Maximum</MenuItem>
                  <MenuItem value={AggregationType.DISTINCT}>Distinct Count</MenuItem>
                </Select>
              </FormControl>
              <FormControl fullWidth sx={{ mb: 2 }}>
                <Select
                  value={editingMetric.format || 'number'}
                  onChange={(e) =>
                    setEditingMetric({
                      ...editingMetric,
                      format: e.target.value as any })
                  }
                >
                  <MenuItem value="number">Number</MenuItem>
                  <MenuItem value="currency">Currency</MenuItem>
                  <MenuItem value="percentage">Percentage</MenuItem>
                  <MenuItem value="duration">Duration</MenuItem>
                </Select>
              </FormControl>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditingMetric(null)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={() => {
              if (editingMetric) {
                updateMetric(editingMetric.id, editingMetric);
                setEditingMetric(null);
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

export default MetricSelector;
