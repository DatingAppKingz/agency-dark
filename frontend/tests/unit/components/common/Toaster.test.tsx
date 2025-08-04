import React from 'react';
import { vi } from 'vitest';
import { render, screen, waitFor, act } from '../../../utils/enhanced-test-utils';
import userEvent from '@testing-library/user-event';
import { Toaster, useToast, useToastStore } from '@/components/common/Toaster';

// Store original setTimeout
const originalSetTimeout = global.setTimeout;

describe('Toaster Component', () => {
  beforeEach(() => {
    // Clear all toasts before each test
    useToastStore.getState().toasts = [];
    vi.clearAllTimers();
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  it('renders without crashing', () => {
    render(<Toaster />);
    // Toaster is a provider, so it doesn't render visible content initially
    expect(document.body).toBeInTheDocument();
  });

  describe('useToast hook', () => {
    it('shows success toast', async () => {
      const TestComponent = () => {
        const toast = useToast();
        return (
          <button onClick={() => toast.success('Operation successful!')}>
            Show Toast
          </button>
        );
      };

      render(<TestComponent />);

      const button = screen.getByText('Show Toast');
      await userEvent.click(button);

      await waitFor(() => {
        expect(screen.getByText('Operation successful!')).toBeInTheDocument();
      });
    });

    it('shows error toast', async () => {
      const TestComponent = () => {
        const toast = useToast();
        return (
          <button onClick={() => toast.error('Something went wrong!')}>
            Show Error
          </button>
        );
      };

      render(<TestComponent />);

      const button = screen.getByText('Show Error');
      await userEvent.click(button);

      await waitFor(() => {
        expect(screen.getByText('Something went wrong!')).toBeInTheDocument();
      });
    });

    it('shows warning toast', async () => {
      const TestComponent = () => {
        const toast = useToast();
        return (
          <button onClick={() => toast.warning('Warning message!')}>
            Show Warning
          </button>
        );
      };

      render(<TestComponent />);

      const button = screen.getByText('Show Warning');
      await userEvent.click(button);

      await waitFor(() => {
        expect(screen.getByText('Warning message!')).toBeInTheDocument();
      });
    });

    it('shows info toast', async () => {
      const TestComponent = () => {
        const toast = useToast();
        return (
          <button onClick={() => toast.info('Info message!')}>
            Show Info
          </button>
        );
      };

      render(<TestComponent />);

      const button = screen.getByText('Show Info');
      await userEvent.click(button);

      await waitFor(() => {
        expect(screen.getByText('Info message!')).toBeInTheDocument();
      });
    });
  });

  describe('Toast interactions', () => {
    it.skip('auto-dismisses after 5 seconds', async () => {
      vi.useFakeTimers();
      
      const TestComponent = () => {
        const toast = useToast();
        return (
          <button onClick={() => toast.success('Auto dismiss')}>
            Show Toast
          </button>
        );
      };

      render(<TestComponent />);

      const button = screen.getByText('Show Toast');
      
      // Click and immediately check
      act(() => {
        userEvent.click(button);
      });

      // Wait for toast to appear
      await waitFor(() => {
        expect(screen.getByText('Auto dismiss')).toBeInTheDocument();
      });

      // Fast forward 5 seconds
      act(() => {
        vi.advanceTimersByTime(5000);
      });

      // Check toast is gone
      expect(screen.queryByText('Auto dismiss')).not.toBeInTheDocument();
      
      vi.useRealTimers();
    });

    it.skip('shows multiple toasts', async () => {
      vi.useFakeTimers();
      
      const TestComponent = () => {
        const toast = useToast();
        return (
          <>
            <button onClick={() => toast.success('First toast')}>
              First
            </button>
            <button onClick={() => toast.error('Second toast')}>
              Second
            </button>
          </>
        );
      };

      render(<TestComponent />);

      const firstButton = screen.getByText('First');
      const secondButton = screen.getByText('Second');
      
      act(() => {
        userEvent.click(firstButton);
        userEvent.click(secondButton);
      });

      await waitFor(() => {
        expect(screen.getByText('First toast')).toBeInTheDocument();
        expect(screen.getByText('Second toast')).toBeInTheDocument();
      });
      
      vi.useRealTimers();
    });

    it.skip('can dismiss toasts manually', async () => {
      vi.useFakeTimers();
      
      const TestComponent = () => {
        const toast = useToast();
        return (
          <button onClick={() => toast.success('Dismissible toast')}>
            Show Toast
          </button>
        );
      };

      render(<TestComponent />);

      const button = screen.getByText('Show Toast');
      
      act(() => {
        userEvent.click(button);
      });
      
      await waitFor(() => {
        expect(screen.getByText('Dismissible toast')).toBeInTheDocument();
      });

      // Find and click the close button
      const closeButton = screen.getByRole('button', { name: /close/i });
      
      act(() => {
        userEvent.click(closeButton);
      });

      await waitFor(() => {
        expect(screen.queryByText('Dismissible toast')).not.toBeInTheDocument();
      });
      
      vi.useRealTimers();
    });
  });

  describe('Toast positioning', () => {
    it.skip('stacks multiple toasts vertically', async () => {
      // Use direct store manipulation for this test to avoid timing issues
      const { addToast } = useToastStore.getState();
      
      act(() => {
        addToast('Toast 1', 'success');
        addToast('Toast 2', 'success');
        addToast('Toast 3', 'success');
      });

      // Force a re-render
      const { rerender } = render(<Toaster />);
      rerender(<Toaster />);

      await waitFor(() => {
        // Check that all toasts are visible
        expect(screen.getByText('Toast 1')).toBeInTheDocument();
        expect(screen.getByText('Toast 2')).toBeInTheDocument();
        expect(screen.getByText('Toast 3')).toBeInTheDocument();
      });

      // Check positioning (each toast should have different top value)
      const toasts = screen.getAllByRole('alert');
      expect(toasts).toHaveLength(3);
      
      // Clear toasts
      useToastStore.getState().toasts = [];
    });
  });

  describe('useToastStore', () => {
    it('can add and remove toasts directly', () => {
      const { addToast, removeToast } = useToastStore.getState();
      
      // Add a toast
      addToast('Test message', 'success');
      expect(useToastStore.getState().toasts).toHaveLength(1);
      expect(useToastStore.getState().toasts[0].message).toBe('Test message');
      expect(useToastStore.getState().toasts[0].severity).toBe('success');
      
      // Remove the toast
      const toastId = useToastStore.getState().toasts[0].id;
      removeToast(toastId);
      expect(useToastStore.getState().toasts).toHaveLength(0);
    });

    it('generates unique IDs for toasts', () => {
      vi.useFakeTimers();
      const { addToast } = useToastStore.getState();
      
      addToast('Toast 1');
      vi.advanceTimersByTime(1);
      addToast('Toast 2');
      
      const toasts = useToastStore.getState().toasts;
      expect(toasts[0].id).not.toBe(toasts[1].id);
      
      vi.useRealTimers();
    });
  });
});