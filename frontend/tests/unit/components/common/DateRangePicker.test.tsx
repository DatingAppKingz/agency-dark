import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { DateRangePicker } from '@/components/common/DateRangePicker';
import { format, subDays, startOfWeek, endOfWeek, startOfMonth, endOfMonth, subMonths } from 'date-fns';

// Mock MUI icons
vi.mock('@mui/icons-material', () => ({
  DateRange: () => <div data-testid="date-range-icon" />
}));

describe('DateRangePicker Component', () => {
  const mockOnStartDateChange = vi.fn();
  const mockOnEndDateChange = vi.fn();

  const defaultProps = {
    startDate: new Date('2024-01-15'),
    endDate: new Date('2024-01-31'),
    onStartDateChange: mockOnStartDateChange,
    onEndDateChange: mockOnEndDateChange
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Set consistent date for tests
    vi.setSystemTime(new Date('2024-01-31'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('Initial Rendering', () => {
    it('should render the date range button with formatted dates', () => {
      render(<DateRangePicker {...defaultProps} />);

      const button = screen.getByRole('button');
      expect(button).toHaveTextContent('Jan 15, 2024 - Jan 31, 2024');
    });

    it('should render with date range icon', () => {
      render(<DateRangePicker {...defaultProps} />);

      const icon = screen.getByTestId('date-range-icon');
      expect(icon).toBeInTheDocument();
    });

    it('should be disabled when disabled prop is true', () => {
      render(<DateRangePicker {...defaultProps} disabled />);

      const button = screen.getByRole('button');
      expect(button).toBeDisabled();
    });
  });

  describe('Popover Behavior', () => {
    it('should open popover when button is clicked', () => {
      render(<DateRangePicker {...defaultProps} />);

      const button = screen.getByRole('button');
      fireEvent.click(button);

      expect(screen.getByText('Select Date Range')).toBeInTheDocument();
    });

    it('should close popover when Cancel button is clicked', async () => {
      const { container } = render(<DateRangePicker {...defaultProps} />);

      const button = screen.getByRole('button');
      fireEvent.click(button);

      // Verify popover is open
      expect(screen.getByText('Select Date Range')).toBeInTheDocument();

      const cancelButton = screen.getByText('Cancel');
      fireEvent.click(cancelButton);

      // Wait for popover to close
      await waitFor(() => {
        const popover = container.querySelector('[role="presentation"]');
        expect(popover).toBeNull();
      });
    });

    it('should close popover when Apply button is clicked', async () => {
      const { container } = render(<DateRangePicker {...defaultProps} />);

      const button = screen.getByRole('button');
      fireEvent.click(button);

      // Verify popover is open
      expect(screen.getByText('Select Date Range')).toBeInTheDocument();

      const applyButton = screen.getByText('Apply');
      fireEvent.click(applyButton);

      // Wait for popover to close
      await waitFor(() => {
        const popover = container.querySelector('[role="presentation"]');
        expect(popover).toBeNull();
      });
    });

    it('should not open popover when button is disabled', () => {
      render(<DateRangePicker {...defaultProps} disabled />);

      const button = screen.getByRole('button');
      fireEvent.click(button);

      expect(screen.queryByText('Select Date Range')).not.toBeInTheDocument();
    });
  });

  describe('Date Input Fields', () => {
    it('should display start and end date input fields', () => {
      render(<DateRangePicker {...defaultProps} />);

      fireEvent.click(screen.getByRole('button'));

      const startDateInput = screen.getByLabelText('Start Date');
      const endDateInput = screen.getByLabelText('End Date');

      expect(startDateInput).toHaveValue('2024-01-15');
      expect(endDateInput).toHaveValue('2024-01-31');
    });

    it('should call onStartDateChange when start date is changed', () => {
      render(<DateRangePicker {...defaultProps} />);

      fireEvent.click(screen.getByRole('button'));

      const startDateInput = screen.getByLabelText('Start Date');
      fireEvent.change(startDateInput, { target: { value: '2024-01-10' } });

      expect(mockOnStartDateChange).toHaveBeenCalledWith(new Date('2024-01-10'));
    });

    it('should call onEndDateChange when end date is changed', () => {
      render(<DateRangePicker {...defaultProps} />);

      fireEvent.click(screen.getByRole('button'));

      const endDateInput = screen.getByLabelText('End Date');
      fireEvent.change(endDateInput, { target: { value: '2024-02-10' } });

      expect(mockOnEndDateChange).toHaveBeenCalledWith(new Date('2024-02-10'));
    });
  });

  describe('Preset Ranges', () => {
    it('should display all preset range options', () => {
      render(<DateRangePicker {...defaultProps} />);

      fireEvent.click(screen.getByRole('button'));

      expect(screen.getByText('Yesterday')).toBeInTheDocument();
      expect(screen.getByText('Last 7 Days')).toBeInTheDocument();
      expect(screen.getByText('Last 30 Days')).toBeInTheDocument();
      expect(screen.getByText('This Week')).toBeInTheDocument();
      expect(screen.getByText('Last Week')).toBeInTheDocument();
      expect(screen.getByText('This Month')).toBeInTheDocument();
      expect(screen.getByText('Last Month')).toBeInTheDocument();
    });

    it('should set correct dates for Yesterday preset', () => {
      render(<DateRangePicker {...defaultProps} />);

      fireEvent.click(screen.getByRole('button'));
      fireEvent.click(screen.getByText('Yesterday'));

      const yesterday = subDays(new Date('2024-01-31'), 1);
      expect(mockOnStartDateChange).toHaveBeenCalledWith(yesterday);
      expect(mockOnEndDateChange).toHaveBeenCalledWith(yesterday);
    });

    it('should set correct dates for Last 7 Days preset', () => {
      render(<DateRangePicker {...defaultProps} />);

      fireEvent.click(screen.getByRole('button'));
      fireEvent.click(screen.getByText('Last 7 Days'));

      const sevenDaysAgo = subDays(new Date('2024-01-31'), 7);
      const today = new Date('2024-01-31');
      
      expect(mockOnStartDateChange).toHaveBeenCalledWith(sevenDaysAgo);
      expect(mockOnEndDateChange).toHaveBeenCalledWith(today);
    });

    it('should set correct dates for Last 30 Days preset', () => {
      render(<DateRangePicker {...defaultProps} />);

      fireEvent.click(screen.getByRole('button'));
      fireEvent.click(screen.getByText('Last 30 Days'));

      const thirtyDaysAgo = subDays(new Date('2024-01-31'), 30);
      const today = new Date('2024-01-31');
      
      expect(mockOnStartDateChange).toHaveBeenCalledWith(thirtyDaysAgo);
      expect(mockOnEndDateChange).toHaveBeenCalledWith(today);
    });

    it('should set correct dates for This Week preset', () => {
      render(<DateRangePicker {...defaultProps} />);

      fireEvent.click(screen.getByRole('button'));
      fireEvent.click(screen.getByText('This Week'));

      const weekStart = startOfWeek(new Date('2024-01-31'));
      const weekEnd = endOfWeek(new Date('2024-01-31'));
      
      expect(mockOnStartDateChange).toHaveBeenCalledWith(weekStart);
      expect(mockOnEndDateChange).toHaveBeenCalledWith(weekEnd);
    });

    it('should set correct dates for Last Week preset', () => {
      render(<DateRangePicker {...defaultProps} />);

      fireEvent.click(screen.getByRole('button'));
      fireEvent.click(screen.getByText('Last Week'));

      const lastWeek = subDays(new Date('2024-01-31'), 7);
      const lastWeekStart = startOfWeek(lastWeek);
      const lastWeekEnd = endOfWeek(lastWeek);
      
      expect(mockOnStartDateChange).toHaveBeenCalledWith(lastWeekStart);
      expect(mockOnEndDateChange).toHaveBeenCalledWith(lastWeekEnd);
    });

    it('should set correct dates for This Month preset', () => {
      render(<DateRangePicker {...defaultProps} />);

      fireEvent.click(screen.getByRole('button'));
      fireEvent.click(screen.getByText('This Month'));

      const monthStart = startOfMonth(new Date('2024-01-31'));
      const monthEnd = endOfMonth(new Date('2024-01-31'));
      
      expect(mockOnStartDateChange).toHaveBeenCalledWith(monthStart);
      expect(mockOnEndDateChange).toHaveBeenCalledWith(monthEnd);
    });

    it('should set correct dates for Last Month preset', () => {
      render(<DateRangePicker {...defaultProps} />);

      fireEvent.click(screen.getByRole('button'));
      fireEvent.click(screen.getByText('Last Month'));

      const lastMonth = subMonths(new Date('2024-01-31'), 1);
      const lastMonthStart = startOfMonth(lastMonth);
      const lastMonthEnd = endOfMonth(lastMonth);
      
      expect(mockOnStartDateChange).toHaveBeenCalledWith(lastMonthStart);
      expect(mockOnEndDateChange).toHaveBeenCalledWith(lastMonthEnd);
    });

    it('should close popover after selecting a preset', async () => {
      const { container } = render(<DateRangePicker {...defaultProps} />);

      fireEvent.click(screen.getByRole('button'));
      fireEvent.click(screen.getByText('Yesterday'));

      // Wait for popover to close
      await waitFor(() => {
        const popover = container.querySelector('[role="presentation"]');
        expect(popover).toBeNull();
      });
    });
  });

  describe('Date Formatting', () => {
    it('should format dates correctly in the button', () => {
      const testProps = {
        ...defaultProps,
        startDate: new Date('2024-02-01'),
        endDate: new Date('2024-12-25')
      };

      render(<DateRangePicker {...testProps} />);

      const button = screen.getByRole('button');
      expect(button).toHaveTextContent('Feb 1, 2024 - Dec 25, 2024');
    });

    it('should handle single day ranges', () => {
      const sameDay = new Date('2024-03-15');
      const testProps = {
        ...defaultProps,
        startDate: sameDay,
        endDate: sameDay
      };

      render(<DateRangePicker {...testProps} />);

      const button = screen.getByRole('button');
      expect(button).toHaveTextContent('Mar 15, 2024 - Mar 15, 2024');
    });
  });

  describe('Edge Cases', () => {
    it('should handle invalid date input gracefully', () => {
      render(<DateRangePicker {...defaultProps} />);

      fireEvent.click(screen.getByRole('button'));

      const startDateInput = screen.getByLabelText('Start Date');
      fireEvent.change(startDateInput, { target: { value: 'invalid-date' } });

      // Should create Invalid Date object
      expect(mockOnStartDateChange).toHaveBeenCalled();
      const callArg = mockOnStartDateChange.mock.calls[0][0];
      expect(callArg.toString()).toBe('Invalid Date');
    });

    it('should handle future dates', () => {
      render(<DateRangePicker {...defaultProps} />);

      fireEvent.click(screen.getByRole('button'));

      const futureDate = '2025-12-31';
      const endDateInput = screen.getByLabelText('End Date');
      fireEvent.change(endDateInput, { target: { value: futureDate } });

      expect(mockOnEndDateChange).toHaveBeenCalledWith(new Date(futureDate));
    });

    it('should handle date range where end is before start', () => {
      const testProps = {
        ...defaultProps,
        startDate: new Date('2024-12-31'),
        endDate: new Date('2024-01-01')
      };

      render(<DateRangePicker {...testProps} />);

      const button = screen.getByRole('button');
      // Component should still render the dates as provided
      expect(button).toHaveTextContent('Dec 31, 2024 - Jan 1, 2024');
    });
  });

  describe('Accessibility', () => {
    it('should have accessible labels for all interactive elements', () => {
      render(<DateRangePicker {...defaultProps} />);

      fireEvent.click(screen.getByRole('button'));

      expect(screen.getByLabelText('Start Date')).toBeInTheDocument();
      expect(screen.getByLabelText('End Date')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Apply/i })).toBeInTheDocument();
    });

    it('should maintain focus management', () => {
      render(<DateRangePicker {...defaultProps} />);

      const button = screen.getByRole('button');
      button.focus();
      expect(document.activeElement).toBe(button);

      fireEvent.click(button);

      // Popover should be open and focusable elements should be accessible
      const startDateInput = screen.getByLabelText('Start Date');
      expect(startDateInput).toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    it('should apply minimum width to button', () => {
      render(<DateRangePicker {...defaultProps} />);

      const button = screen.getByRole('button');
      expect(button).toHaveStyle({ minWidth: '250px' });
    });

    it('should render popover with correct width', () => {
      render(<DateRangePicker {...defaultProps} />);

      fireEvent.click(screen.getByRole('button'));

      const paper = screen.getByText('Select Date Range').closest('[class*="MuiPaper"]');
      expect(paper).toHaveStyle({ width: '400px' });
    });
  });
});