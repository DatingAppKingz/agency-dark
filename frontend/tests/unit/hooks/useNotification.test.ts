import { renderHook, act } from '@testing-library/react';
import { vi } from 'vitest';
import { useNotification } from '@/hooks/useNotification';

describe('useNotification Hook', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(Date, 'now').mockReturnValue(1000);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  describe('Initial State', () => {
    it('starts with empty notifications array', () => {
      const { result } = renderHook(() => useNotification());
      
      expect(result.current.notifications).toEqual([]);
    });

    it('provides showNotification and hideNotification functions', () => {
      const { result } = renderHook(() => useNotification());
      
      expect(typeof result.current.showNotification).toBe('function');
      expect(typeof result.current.hideNotification).toBe('function');
    });
  });

  describe('showNotification', () => {
    it('adds a success notification', () => {
      const { result } = renderHook(() => useNotification());

      act(() => {
        result.current.showNotification({
          title: 'Success',
          message: 'Operation completed successfully',
          type: 'success'
        });
      });

      expect(result.current.notifications).toHaveLength(1);
      expect(result.current.notifications[0]).toEqual({
        id: '1000',
        title: 'Success',
        message: 'Operation completed successfully',
        type: 'success',
        duration: 5000
      });
    });

    it('adds error notification', () => {
      const { result } = renderHook(() => useNotification());

      act(() => {
        result.current.showNotification({
          title: 'Error',
          message: 'Something went wrong',
          type: 'error'
        });
      });

      expect(result.current.notifications[0].type).toBe('error');
    });

    it('adds warning notification', () => {
      const { result } = renderHook(() => useNotification());

      act(() => {
        result.current.showNotification({
          title: 'Warning',
          message: 'Please be careful',
          type: 'warning'
        });
      });

      expect(result.current.notifications[0].type).toBe('warning');
    });

    it('adds info notification', () => {
      const { result } = renderHook(() => useNotification());

      act(() => {
        result.current.showNotification({
          title: 'Info',
          message: 'Here is some information',
          type: 'info'
        });
      });

      expect(result.current.notifications[0].type).toBe('info');
    });

    it('adds multiple notifications', () => {
      const { result } = renderHook(() => useNotification());

      act(() => {
        // Mock different timestamps
        vi.spyOn(Date, 'now').mockReturnValueOnce(1000);
        result.current.showNotification({
          title: 'First',
          message: 'First notification',
          type: 'info'
        });

        vi.spyOn(Date, 'now').mockReturnValueOnce(2000);
        result.current.showNotification({
          title: 'Second',
          message: 'Second notification',
          type: 'success'
        });
      });

      expect(result.current.notifications).toHaveLength(2);
      expect(result.current.notifications[0].id).toBe('1000');
      expect(result.current.notifications[1].id).toBe('2000');
    });

    it('uses custom duration', () => {
      const { result } = renderHook(() => useNotification());

      act(() => {
        result.current.showNotification({
          title: 'Custom Duration',
          message: 'This will last 10 seconds',
          type: 'info',
          duration: 10000
        });
      });

      expect(result.current.notifications[0].duration).toBe(10000);
    });

    it('auto-hides notification after default duration', () => {
      const { result } = renderHook(() => useNotification());

      act(() => {
        result.current.showNotification({
          title: 'Auto Hide',
          message: 'This will disappear',
          type: 'info'
        });
      });

      expect(result.current.notifications).toHaveLength(1);

      // Advance time by default duration (5000ms)
      act(() => {
        vi.advanceTimersByTime(5000);
      });

      expect(result.current.notifications).toHaveLength(0);
    });

    it('auto-hides notification after custom duration', () => {
      const { result } = renderHook(() => useNotification());

      act(() => {
        result.current.showNotification({
          title: 'Custom Auto Hide',
          message: 'This will disappear in 3 seconds',
          type: 'info',
          duration: 3000
        });
      });

      expect(result.current.notifications).toHaveLength(1);

      act(() => {
        vi.advanceTimersByTime(2999);
      });
      expect(result.current.notifications).toHaveLength(1);

      act(() => {
        vi.advanceTimersByTime(1);
      });
      expect(result.current.notifications).toHaveLength(0);
    });

    it('does not auto-hide with duration 0', () => {
      const { result } = renderHook(() => useNotification());

      act(() => {
        result.current.showNotification({
          title: 'Persistent',
          message: 'This will not auto-hide',
          type: 'info',
          duration: 0
        });
      });

      expect(result.current.notifications).toHaveLength(1);

      act(() => {
        vi.advanceTimersByTime(10000);
      });

      // Should still be there
      expect(result.current.notifications).toHaveLength(1);
    });

    it('does not auto-hide with negative duration', () => {
      const { result } = renderHook(() => useNotification());

      act(() => {
        result.current.showNotification({
          title: 'Persistent',
          message: 'This will not auto-hide',
          type: 'info',
          duration: -1
        });
      });

      act(() => {
        vi.advanceTimersByTime(10000);
      });

      expect(result.current.notifications).toHaveLength(1);
    });
  });

  describe('hideNotification', () => {
    it('removes notification by id', () => {
      const { result } = renderHook(() => useNotification());

      act(() => {
        result.current.showNotification({
          title: 'Test',
          message: 'Test message',
          type: 'info'
        });
      });

      expect(result.current.notifications).toHaveLength(1);

      act(() => {
        result.current.hideNotification('1000');
      });

      expect(result.current.notifications).toHaveLength(0);
    });

    it('removes correct notification from multiple', () => {
      const { result } = renderHook(() => useNotification());

      act(() => {
        vi.spyOn(Date, 'now').mockReturnValueOnce(1000);
        result.current.showNotification({
          title: 'First',
          message: 'First message',
          type: 'info'
        });

        vi.spyOn(Date, 'now').mockReturnValueOnce(2000);
        result.current.showNotification({
          title: 'Second',
          message: 'Second message',
          type: 'success'
        });

        vi.spyOn(Date, 'now').mockReturnValueOnce(3000);
        result.current.showNotification({
          title: 'Third',
          message: 'Third message',
          type: 'error'
        });
      });

      expect(result.current.notifications).toHaveLength(3);

      act(() => {
        result.current.hideNotification('2000');
      });

      expect(result.current.notifications).toHaveLength(2);
      expect(result.current.notifications.find(n => n.id === '2000')).toBeUndefined();
      expect(result.current.notifications[0].id).toBe('1000');
      expect(result.current.notifications[1].id).toBe('3000');
    });

    it('does nothing if id does not exist', () => {
      const { result } = renderHook(() => useNotification());

      act(() => {
        result.current.showNotification({
          title: 'Test',
          message: 'Test message',
          type: 'info'
        });
      });

      expect(result.current.notifications).toHaveLength(1);

      act(() => {
        result.current.hideNotification('non-existent-id');
      });

      expect(result.current.notifications).toHaveLength(1);
    });

    it('can be called manually before auto-hide', () => {
      const { result } = renderHook(() => useNotification());

      act(() => {
        result.current.showNotification({
          title: 'Manual Hide',
          message: 'Hide me manually',
          type: 'info',
          duration: 5000
        });
      });

      expect(result.current.notifications).toHaveLength(1);

      // Hide manually after 1 second
      act(() => {
        vi.advanceTimersByTime(1000);
        result.current.hideNotification('1000');
      });

      expect(result.current.notifications).toHaveLength(0);

      // Advance to when auto-hide would have occurred
      act(() => {
        vi.advanceTimersByTime(4000);
      });

      // Should still be empty (no errors from trying to hide already hidden notification)
      expect(result.current.notifications).toHaveLength(0);
    });
  });

  describe('Real-world scenarios', () => {
    it('handles form submission notifications', () => {
      const { result } = renderHook(() => useNotification());

      // Show loading notification
      act(() => {
        vi.spyOn(Date, 'now').mockReturnValueOnce(1000);
        result.current.showNotification({
          title: 'Saving',
          message: 'Saving your changes...',
          type: 'info',
          duration: 0 // Don't auto-hide
        });
      });

      expect(result.current.notifications[0].message).toBe('Saving your changes...');

      // Hide loading and show success
      act(() => {
        result.current.hideNotification('1000');
        vi.spyOn(Date, 'now').mockReturnValueOnce(2000);
        result.current.showNotification({
          title: 'Success',
          message: 'Changes saved successfully!',
          type: 'success'
        });
      });

      expect(result.current.notifications).toHaveLength(1);
      expect(result.current.notifications[0].type).toBe('success');
    });

    it('handles error notification flow', () => {
      const { result } = renderHook(() => useNotification());

      // Simulate API error
      act(() => {
        result.current.showNotification({
          title: 'Error',
          message: 'Failed to load data. Please try again.',
          type: 'error',
          duration: 10000 // Longer duration for errors
        });
      });

      expect(result.current.notifications[0].type).toBe('error');
      expect(result.current.notifications[0].duration).toBe(10000);
    });

    it('handles notification queue', () => {
      const { result } = renderHook(() => useNotification());

      // Simulate multiple rapid notifications
      act(() => {
        vi.spyOn(Date, 'now').mockReturnValueOnce(1000);
        result.current.showNotification({
          title: 'Upload 1',
          message: 'File 1 uploaded',
          type: 'success',
          duration: 3000
        });

        vi.spyOn(Date, 'now').mockReturnValueOnce(1100);
        result.current.showNotification({
          title: 'Upload 2',
          message: 'File 2 uploaded',
          type: 'success',
          duration: 3000
        });

        vi.spyOn(Date, 'now').mockReturnValueOnce(1200);
        result.current.showNotification({
          title: 'Upload 3',
          message: 'File 3 uploaded',
          type: 'success',
          duration: 3000
        });
      });

      expect(result.current.notifications).toHaveLength(3);

      // First notification expires
      act(() => {
        vi.advanceTimersByTime(3000);
      });

      expect(result.current.notifications).toHaveLength(2);
      expect(result.current.notifications.find(n => n.id === '1000')).toBeUndefined();

      // Remaining notifications expire
      act(() => {
        vi.advanceTimersByTime(200);
      });

      expect(result.current.notifications).toHaveLength(0);
    });
  });

  describe('Edge cases', () => {
    it('maintains stable function references', () => {
      const { result, rerender } = renderHook(() => useNotification());

      const firstShowNotification = result.current.showNotification;
      const firstHideNotification = result.current.hideNotification;

      rerender();

      expect(result.current.showNotification).toBe(firstShowNotification);
      expect(result.current.hideNotification).toBe(firstHideNotification);
    });

    it('handles empty strings', () => {
      const { result } = renderHook(() => useNotification());

      act(() => {
        result.current.showNotification({
          title: '',
          message: '',
          type: 'info'
        });
      });

      expect(result.current.notifications[0]).toEqual({
        id: '1000',
        title: '',
        message: '',
        type: 'info',
        duration: 5000
      });
    });

    it('handles very long messages', () => {
      const { result } = renderHook(() => useNotification());
      const longMessage = 'A'.repeat(1000);

      act(() => {
        result.current.showNotification({
          title: 'Long Message',
          message: longMessage,
          type: 'info'
        });
      });

      expect(result.current.notifications[0].message).toBe(longMessage);
    });

    it('handles rapid show/hide cycles', () => {
      const { result } = renderHook(() => useNotification());

      act(() => {
        // Show
        result.current.showNotification({
          title: 'Rapid',
          message: 'Rapid notification',
          type: 'info'
        });
        
        // Immediately hide
        result.current.hideNotification('1000');
        
        // Show again with same timestamp
        result.current.showNotification({
          title: 'Rapid 2',
          message: 'Second rapid notification',
          type: 'success'
        });
      });

      expect(result.current.notifications).toHaveLength(1);
      expect(result.current.notifications[0].type).toBe('success');
    });
  });
});