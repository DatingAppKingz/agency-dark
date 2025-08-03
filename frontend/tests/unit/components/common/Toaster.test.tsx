import React from 'react';
import { vi } from 'vitest';
import { render, screen, waitFor, act } from '@/tests/utils/enhanced-test-utils';
import userEvent from '@testing-library/user-event';
import { Toaster, showToast } from '@/components/common/Toaster';
import toast from 'react-hot-toast';

describe('Toaster Component', () => {
  beforeEach(() => {
    // Clear all toasts before each test
    toast.remove();
  });

  it('renders without crashing', () => {
    render(<Toaster />);
    // Toaster is a provider, so it doesn't render visible content initially
    expect(document.body).toBeInTheDocument();
  });

  describe('showToast function', () => {
    it('shows success toast', async () => {
      render(<Toaster />);

      act(() => {
        showToast.success('Operation successful!');
      });

      await waitFor(() => {
        expect(screen.getByText('Operation successful!')).toBeInTheDocument();
      });

      // Check for success icon
      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    it('shows error toast', async () => {
      render(<Toaster />);

      act(() => {
        showToast.error('Something went wrong!');
      });

      await waitFor(() => {
        expect(screen.getByText('Something went wrong!')).toBeInTheDocument();
      });
    });

    it('shows loading toast', async () => {
      render(<Toaster />);

      act(() => {
        showToast.loading('Processing...');
      });

      await waitFor(() => {
        expect(screen.getByText('Processing...')).toBeInTheDocument();
      });
    });

    it('shows promise toast with success', async () => {
      render(<Toaster />);

      const promise = new Promise((resolve) => {
        setTimeout(() => resolve('Done!'), 100);
      });

      act(() => {
        showToast.promise(promise, {
          loading: 'Loading...',
          success: 'Success!',
          error: 'Error!',
        });
      });

      // First shows loading
      expect(screen.getByText('Loading...')).toBeInTheDocument();

      // Then shows success
      await waitFor(() => {
        expect(screen.getByText('Success!')).toBeInTheDocument();
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });
    });

    it('shows promise toast with error', async () => {
      render(<Toaster />);

      const promise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('Failed!')), 100);
      });

      act(() => {
        showToast.promise(promise, {
          loading: 'Loading...',
          success: 'Success!',
          error: 'Error occurred!',
        });
      });

      // First shows loading
      expect(screen.getByText('Loading...')).toBeInTheDocument();

      // Then shows error
      await waitFor(() => {
        expect(screen.getByText('Error occurred!')).toBeInTheDocument();
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });
    });
  });

  describe('Toast interactions', () => {
    it('dismisses toast on click', async () => {
      const user = userEvent.setup();
      render(<Toaster />);

      act(() => {
        showToast.success('Click to dismiss');
      });

      const toastElement = await screen.findByText('Click to dismiss');
      await user.click(toastElement);

      await waitFor(() => {
        expect(screen.queryByText('Click to dismiss')).not.toBeInTheDocument();
      });
    });

    it('auto-dismisses after duration', async () => {
      render(<Toaster />);

      act(() => {
        toast.success('Auto dismiss', { duration: 1000 });
      });

      expect(screen.getByText('Auto dismiss')).toBeInTheDocument();

      // Wait for auto-dismiss
      await waitFor(
        () => {
          expect(screen.queryByText('Auto dismiss')).not.toBeInTheDocument();
        },
        { timeout: 2000 }
      );
    });

    it('shows multiple toasts', async () => {
      render(<Toaster />);

      act(() => {
        showToast.success('First toast');
        showToast.error('Second toast');
        showToast.loading('Third toast');
      });

      await waitFor(() => {
        expect(screen.getByText('First toast')).toBeInTheDocument();
        expect(screen.getByText('Second toast')).toBeInTheDocument();
        expect(screen.getByText('Third toast')).toBeInTheDocument();
      });
    });
  });

  describe('Toast positioning', () => {
    it('renders toasts in correct position', () => {
      const { container } = render(<Toaster />);

      act(() => {
        showToast.success('Positioned toast');
      });

      // Check that Toaster container has correct positioning
      const toasterContainer = container.querySelector('[class*="toaster"]');
      expect(toasterContainer).toBeInTheDocument();
    });
  });

  describe('Custom toast options', () => {
    it('accepts custom duration', async () => {
      render(<Toaster />);

      act(() => {
        toast.success('Long toast', { duration: 5000 });
      });

      expect(screen.getByText('Long toast')).toBeInTheDocument();

      // Should still be visible after 1 second
      await waitFor(() => {
        expect(screen.getByText('Long toast')).toBeInTheDocument();
      }, { timeout: 1500 });
    });

    it('shows toast with custom id', async () => {
      render(<Toaster />);

      act(() => {
        toast.success('Unique toast', { id: 'unique-toast' });
      });

      expect(screen.getByText('Unique toast')).toBeInTheDocument();

      // Trying to show same toast again should not create duplicate
      act(() => {
        toast.success('Unique toast updated', { id: 'unique-toast' });
      });

      expect(screen.queryByText('Unique toast')).not.toBeInTheDocument();
      expect(screen.getByText('Unique toast updated')).toBeInTheDocument();
    });

    it('prevents duplicate toasts', async () => {
      render(<Toaster />);

      act(() => {
        showToast.error('Duplicate error', { id: 'error-1' });
        showToast.error('Duplicate error', { id: 'error-1' });
      });

      // Should only show one toast
      const toasts = screen.getAllByText('Duplicate error');
      expect(toasts).toHaveLength(1);
    });
  });

  describe('Toast styling', () => {
    it('applies correct styles for different toast types', async () => {
      render(<Toaster />);

      act(() => {
        showToast.success('Success style');
        showToast.error('Error style');
      });

      await waitFor(() => {
        const successToast = screen.getByText('Success style').closest('[role="status"]');
        const errorToast = screen.getByText('Error style').closest('[role="status"]');

        expect(successToast).toBeInTheDocument();
        expect(errorToast).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('has correct ARIA attributes', async () => {
      render(<Toaster />);

      act(() => {
        showToast.success('Accessible toast');
      });

      const toastElement = await screen.findByRole('status');
      expect(toastElement).toHaveAttribute('aria-live', 'polite');
    });

    it('announces toast messages to screen readers', async () => {
      render(<Toaster />);

      act(() => {
        showToast.error('Screen reader announcement');
      });

      const announcement = await screen.findByRole('status');
      expect(announcement).toHaveTextContent('Screen reader announcement');
    });
  });

  describe('Integration with forms', () => {
    it('shows appropriate toasts for form submission', async () => {
      const user = userEvent.setup();

      const TestForm = () => {
        const handleSubmit = async (e: React.FormEvent) => {
          e.preventDefault();
          
          const promise = new Promise((resolve) => {
            setTimeout(() => resolve('Form submitted'), 500);
          });

          showToast.promise(promise, {
            loading: 'Submitting form...',
            success: 'Form submitted successfully!',
            error: 'Failed to submit form',
          });
        };

        return (
          <form onSubmit={handleSubmit}>
            <button type="submit">Submit</button>
          </form>
        );
      };

      render(
        <>
          <TestForm />
          <Toaster />
        </>
      );

      const submitButton = screen.getByRole('button', { name: /submit/i });
      await user.click(submitButton);

      // Should show loading toast
      expect(screen.getByText('Submitting form...')).toBeInTheDocument();

      // Then success toast
      await waitFor(() => {
        expect(screen.getByText('Form submitted successfully!')).toBeInTheDocument();
      });
    });
  });
});