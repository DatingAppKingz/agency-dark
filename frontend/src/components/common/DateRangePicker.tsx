import { useState } from 'react';
import {
  Box,
  TextField,
  IconButton,
  Popover,
  Paper,
  Typography,
  Button,
  Stack,
} from '@mui/material';
import {
  DateRange as DateRangeIcon,
  ChevronLeft,
  ChevronRight,
  Today,
} from '@mui/icons-material';
import { format, startOfWeek, endOfWeek, startOfMonth, endOfMonth, subDays, subMonths } from 'date-fns';

interface DateRangePickerProps {
  startDate: Date;
  endDate: Date;
  onStartDateChange: (date: Date) => void;
  onEndDateChange: (date: Date) => void;
  disabled?: boolean;
}

export const DateRangePicker = ({
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
  disabled = false,
}: DateRangePickerProps) => {
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const open = Boolean(anchorEl);

  const presetRanges = [
    { label: 'Today', start: new Date(), end: new Date() },
    { label: 'Yesterday', start: subDays(new Date(), 1), end: subDays(new Date(), 1) },
    { label: 'Last 7 Days', start: subDays(new Date(), 7), end: new Date() },
    { label: 'Last 30 Days', start: subDays(new Date(), 30), end: new Date() },
    { label: 'This Week', start: startOfWeek(new Date()), end: endOfWeek(new Date()) },
    { label: 'Last Week', start: startOfWeek(subDays(new Date(), 7)), end: endOfWeek(subDays(new Date(), 7)) },
    { label: 'This Month', start: startOfMonth(new Date()), end: endOfMonth(new Date()) },
    { label: 'Last Month', start: startOfMonth(subMonths(new Date(), 1)), end: endOfMonth(subMonths(new Date(), 1)) },
  ];

  const handlePresetClick = (start: Date, end: Date) => {
    onStartDateChange(start);
    onEndDateChange(end);
    handleClose();
  };

  return (
    <>
      <Button
        variant="outlined"
        startIcon={<DateRangeIcon />}
        onClick={handleClick}
        disabled={disabled}
        sx={{ minWidth: 250 }}
      >
        {format(startDate, 'MMM d, yyyy')} - {format(endDate, 'MMM d, yyyy')}
      </Button>
      
      <Popover
        open={open}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}
      >
        <Paper sx={{ p: 3, width: 400 }}>
          <Typography variant="h6" gutterBottom>
            Select Date Range
          </Typography>
          
          <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
            <TextField
              label="Start Date"
              type="date"
              value={format(startDate, 'yyyy-MM-dd')}
              onChange={(e) => onStartDateChange(new Date(e.target.value))}
              InputLabelProps={{ shrink: true }}
              fullWidth
            />
            <TextField
              label="End Date"
              type="date"
              value={format(endDate, 'yyyy-MM-dd')}
              onChange={(e) => onEndDateChange(new Date(e.target.value))}
              InputLabelProps={{ shrink: true }}
              fullWidth
            />
          </Box>
          
          <Typography variant="subtitle2" gutterBottom>
            Quick Selection
          </Typography>
          
          <Stack spacing={1}>
            {presetRanges.map((preset) => (
              <Button
                key={preset.label}
                variant="text"
                size="small"
                onClick={() => handlePresetClick(preset.start, preset.end)}
                sx={{ justifyContent: 'flex-start' }}
              >
                {preset.label}
              </Button>
            ))}
          </Stack>
          
          <Box sx={{ mt: 2, display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
            <Button onClick={handleClose}>Cancel</Button>
            <Button variant="contained" onClick={handleClose}>
              Apply
            </Button>
          </Box>
        </Paper>
      </Popover>
    </>
  );
};