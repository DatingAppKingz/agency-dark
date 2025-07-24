import { useState } from 'react';
import {
  Box,
  Grid,
  Typography,
  Paper,
  Button,
  Switch,
  FormControlLabel,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import { TimePicker } from '@mui/x-date-pickers/TimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { Add, Edit, Delete } from '@mui/icons-material';
import { format } from 'date-fns';

interface ModelAvailabilityProps {
  modelId: string;
}

interface AvailabilitySlot {
  id: string;
  dayOfWeek: number;
  startTime: Date;
  endTime: Date;
  isActive: boolean;
}

const DAYS_OF_WEEK = [
  'Sunday',
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
];

export const ModelAvailability = ({ modelId }: ModelAvailabilityProps) => {
  const [autoReplyEnabled, setAutoReplyEnabled] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingSlot, setEditingSlot] = useState<AvailabilitySlot | null>(null);
  
  // Mock availability data - replace with real API data
  const [availability, setAvailability] = useState<AvailabilitySlot[]>([
    {
      id: '1',
      dayOfWeek: 1,
      startTime: new Date('2025-01-01T09:00:00'),
      endTime: new Date('2025-01-01T17:00:00'),
      isActive: true,
    },
    {
      id: '2',
      dayOfWeek: 2,
      startTime: new Date('2025-01-01T09:00:00'),
      endTime: new Date('2025-01-01T17:00:00'),
      isActive: true,
    },
    {
      id: '3',
      dayOfWeek: 3,
      startTime: new Date('2025-01-01T10:00:00'),
      endTime: new Date('2025-01-01T18:00:00'),
      isActive: true,
    },
  ]);

  const [formData, setFormData] = useState({
    dayOfWeek: 0,
    startTime: new Date('2025-01-01T09:00:00'),
    endTime: new Date('2025-01-01T17:00:00'),
  });

  const handleAddSlot = () => {
    setEditingSlot(null);
    setFormData({
      dayOfWeek: 0,
      startTime: new Date('2025-01-01T09:00:00'),
      endTime: new Date('2025-01-01T17:00:00'),
    });
    setDialogOpen(true);
  };

  const handleEditSlot = (slot: AvailabilitySlot) => {
    setEditingSlot(slot);
    setFormData({
      dayOfWeek: slot.dayOfWeek,
      startTime: slot.startTime,
      endTime: slot.endTime,
    });
    setDialogOpen(true);
  };

  const handleDeleteSlot = (slotId: string) => {
    setAvailability(availability.filter(slot => slot.id !== slotId));
  };

  const handleToggleSlot = (slotId: string) => {
    setAvailability(availability.map(slot =>
      slot.id === slotId ? { ...slot, isActive: !slot.isActive } : slot
    ));
  };

  const handleSaveSlot = () => {
    if (editingSlot) {
      // Update existing slot
      setAvailability(availability.map(slot =>
        slot.id === editingSlot.id
          ? { ...slot, ...formData }
          : slot
      ));
    } else {
      // Add new slot
      const newSlot: AvailabilitySlot = {
        id: Date.now().toString(),
        ...formData,
        isActive: true,
      };
      setAvailability([...availability, newSlot]);
    }
    setDialogOpen(false);
  };

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box sx={{ p: 3 }}>
        <Grid container spacing={3}>
          {/* Auto-Reply Settings */}
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Auto-Reply Settings
              </Typography>
              <FormControlLabel
                control={
                  <Switch
                    checked={autoReplyEnabled}
                    onChange={(e) => setAutoReplyEnabled(e.target.checked)}
                  />
                }
                label="Enable auto-reply outside of availability hours"
              />
              {autoReplyEnabled && (
                <TextField
                  fullWidth
                  multiline
                  rows={3}
                  label="Auto-reply message"
                  defaultValue="Hi! I'm currently offline. I'll respond to your message as soon as I'm back online. My usual hours are Monday-Friday 9AM-5PM EST."
                  sx={{ mt: 2 }}
                />
              )}
            </Paper>
          </Grid>

          {/* Availability Schedule */}
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6">
                  Availability Schedule
                </Typography>
                <Button
                  variant="contained"
                  startIcon={<Add />}
                  onClick={handleAddSlot}
                >
                  Add Time Slot
                </Button>
              </Box>

              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Day</TableCell>
                      <TableCell>Start Time</TableCell>
                      <TableCell>End Time</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell align="right">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {availability.map((slot) => (
                      <TableRow key={slot.id}>
                        <TableCell>{DAYS_OF_WEEK[slot.dayOfWeek]}</TableCell>
                        <TableCell>{format(slot.startTime, 'h:mm a')}</TableCell>
                        <TableCell>{format(slot.endTime, 'h:mm a')}</TableCell>
                        <TableCell>
                          <Switch
                            checked={slot.isActive}
                            onChange={() => handleToggleSlot(slot.id)}
                            size="small"
                          />
                        </TableCell>
                        <TableCell align="right">
                          <IconButton size="small" onClick={() => handleEditSlot(slot)}>
                            <Edit />
                          </IconButton>
                          <IconButton size="small" onClick={() => handleDeleteSlot(slot.id)}>
                            <Delete />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    ))}
                    {availability.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={5} align="center">
                          No availability schedule set. Add time slots to define when you're available.
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>

          {/* Timezone Settings */}
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Timezone Settings
              </Typography>
              <FormControl fullWidth>
                <InputLabel>Timezone</InputLabel>
                <Select defaultValue="America/New_York" label="Timezone">
                  <MenuItem value="America/New_York">Eastern Time (EST/EDT)</MenuItem>
                  <MenuItem value="America/Chicago">Central Time (CST/CDT)</MenuItem>
                  <MenuItem value="America/Denver">Mountain Time (MST/MDT)</MenuItem>
                  <MenuItem value="America/Los_Angeles">Pacific Time (PST/PDT)</MenuItem>
                  <MenuItem value="Europe/London">London (GMT/BST)</MenuItem>
                  <MenuItem value="Europe/Paris">Paris (CET/CEST)</MenuItem>
                </Select>
              </FormControl>
            </Paper>
          </Grid>
        </Grid>

        {/* Add/Edit Dialog */}
        <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>
            {editingSlot ? 'Edit Time Slot' : 'Add Time Slot'}
          </DialogTitle>
          <DialogContent>
            <Grid container spacing={2} sx={{ mt: 1 }}>
              <Grid item xs={12}>
                <FormControl fullWidth>
                  <InputLabel>Day of Week</InputLabel>
                  <Select
                    value={formData.dayOfWeek}
                    label="Day of Week"
                    onChange={(e) => setFormData({ ...formData, dayOfWeek: Number(e.target.value) })}
                  >
                    {DAYS_OF_WEEK.map((day, index) => (
                      <MenuItem key={index} value={index}>
                        {day}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={6}>
                <TimePicker
                  label="Start Time"
                  value={formData.startTime}
                  onChange={(newValue) => newValue && setFormData({ ...formData, startTime: newValue })}
                  slotProps={{ textField: { fullWidth: true } }}
                />
              </Grid>
              <Grid item xs={6}>
                <TimePicker
                  label="End Time"
                  value={formData.endTime}
                  onChange={(newValue) => newValue && setFormData({ ...formData, endTime: newValue })}
                  slotProps={{ textField: { fullWidth: true } }}
                />
              </Grid>
            </Grid>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSaveSlot} variant="contained">
              {editingSlot ? 'Update' : 'Add'}
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </LocalizationProvider>
  );
};