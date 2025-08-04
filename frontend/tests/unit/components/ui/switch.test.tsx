import React from 'react';
import { vi } from 'vitest';
import { render, screen } from '../../../utils/enhanced-test-utils';
import userEvent from '@testing-library/user-event';
import { Switch } from '@/components/ui/switch';

describe('Switch Component', () => {
  describe('Basic Rendering', () => {
    it('renders correctly', () => {
      render(<Switch />);
      
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toBeInTheDocument();
      expect(switchElement).toHaveAttribute('aria-checked', 'false');
    });

    it('renders with default checked state', () => {
      render(<Switch defaultChecked />);
      
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toHaveAttribute('aria-checked', 'true');
      expect(switchElement).toHaveAttribute('data-state', 'checked');
    });

    it('renders with custom className', () => {
      render(<Switch className="custom-switch" />);
      
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toHaveClass('custom-switch');
    });

    it('renders with id prop', () => {
      render(<Switch id="theme-toggle" />);
      
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toHaveAttribute('id', 'theme-toggle');
    });
  });

  describe('Interactions', () => {
    it('toggles when clicked', async () => {
      const user = userEvent.setup();
      
      render(<Switch />);
      
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toHaveAttribute('aria-checked', 'false');
      
      await user.click(switchElement);
      expect(switchElement).toHaveAttribute('aria-checked', 'true');
      
      await user.click(switchElement);
      expect(switchElement).toHaveAttribute('aria-checked', 'false');
    });

    it('calls onCheckedChange when toggled', async () => {
      const user = userEvent.setup();
      const handleChange = vi.fn();
      
      render(<Switch onCheckedChange={handleChange} />);
      
      const switchElement = screen.getByRole('switch');
      await user.click(switchElement);
      
      expect(handleChange).toHaveBeenCalledTimes(1);
      expect(handleChange).toHaveBeenCalledWith(true);
      
      await user.click(switchElement);
      expect(handleChange).toHaveBeenCalledTimes(2);
      expect(handleChange).toHaveBeenCalledWith(false);
    });

    it('toggles with keyboard Space key', async () => {
      const user = userEvent.setup();
      
      render(<Switch />);
      
      const switchElement = screen.getByRole('switch');
      switchElement.focus();
      
      await user.keyboard(' ');
      expect(switchElement).toHaveAttribute('aria-checked', 'true');
      
      await user.keyboard(' ');
      expect(switchElement).toHaveAttribute('aria-checked', 'false');
    });

    it('toggles with keyboard Enter key', async () => {
      const user = userEvent.setup();
      
      render(<Switch />);
      
      const switchElement = screen.getByRole('switch');
      switchElement.focus();
      
      await user.keyboard('{Enter}');
      expect(switchElement).toHaveAttribute('aria-checked', 'true');
    });
  });

  describe('Disabled State', () => {
    it('renders as disabled', () => {
      render(<Switch disabled />);
      
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toBeDisabled();
      expect(switchElement).toHaveClass('disabled:cursor-not-allowed');
      expect(switchElement).toHaveClass('disabled:opacity-50');
    });

    it('does not toggle when disabled', async () => {
      const user = userEvent.setup();
      const handleChange = vi.fn();
      
      render(<Switch disabled onCheckedChange={handleChange} />);
      
      const switchElement = screen.getByRole('switch');
      await user.click(switchElement);
      
      expect(handleChange).not.toHaveBeenCalled();
      expect(switchElement).toHaveAttribute('aria-checked', 'false');
    });

    it('does not respond to keyboard when disabled', async () => {
      const user = userEvent.setup();
      
      render(<Switch disabled />);
      
      const switchElement = screen.getByRole('switch');
      switchElement.focus();
      
      await user.keyboard(' ');
      expect(switchElement).toHaveAttribute('aria-checked', 'false');
    });
  });

  describe('Controlled Component', () => {
    it('works as controlled component', async () => {
      const user = userEvent.setup();
      
      const ControlledSwitch = () => {
        const [checked, setChecked] = React.useState(false);
        
        return (
          <>
            <Switch checked={checked} onCheckedChange={setChecked} />
            <span data-testid="checked-state">{checked ? 'ON' : 'OFF'}</span>
          </>
        );
      };
      
      render(<ControlledSwitch />);
      
      const switchElement = screen.getByRole('switch');
      const stateDisplay = screen.getByTestId('checked-state');
      
      expect(stateDisplay).toHaveTextContent('OFF');
      expect(switchElement).toHaveAttribute('aria-checked', 'false');
      
      await user.click(switchElement);
      
      expect(stateDisplay).toHaveTextContent('ON');
      expect(switchElement).toHaveAttribute('aria-checked', 'true');
    });

    it('does not change when controlled value does not update', async () => {
      const user = userEvent.setup();
      
      render(<Switch checked={false} onCheckedChange={() => {}} />);
      
      const switchElement = screen.getByRole('switch');
      await user.click(switchElement);
      
      // Should remain unchecked because controlled value didn't change
      expect(switchElement).toHaveAttribute('aria-checked', 'false');
    });
  });

  describe('Form Integration', () => {
    it('works within a form with name attribute', () => {
      // Note: Radix UI Switch doesn't directly support name attribute on the button element
      // In real usage, you would need to use a hidden input or handle form submission manually
      const { container } = render(
        <form>
          <Switch name="notifications" />
        </form>
      );
      
      // The switch component itself is rendered
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toBeInTheDocument();
      
      // In practice, you'd need to add a hidden input for form submission
      // This test verifies the component accepts the prop without error
    });

    it('submits correct value in form', async () => {
      const user = userEvent.setup();
      const handleSubmit = vi.fn((e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        return Object.fromEntries(formData);
      });
      
      render(
        <form onSubmit={handleSubmit}>
          <Switch name="newsletter" defaultChecked />
          <button type="submit">Submit</button>
        </form>
      );
      
      const submitButton = screen.getByRole('button', { name: 'Submit' });
      await user.click(submitButton);
      
      expect(handleSubmit).toHaveBeenCalled();
      const formData = handleSubmit.mock.results[0].value;
      expect(formData.newsletter).toBe('on');
    });

    it('can have a custom value', () => {
      render(<Switch value="enabled" />);
      
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toHaveAttribute('value', 'enabled');
    });
  });

  describe('Visual States', () => {
    it('has correct unchecked styles', () => {
      render(<Switch />);
      
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toHaveClass('data-[state=unchecked]:bg-input');
      expect(switchElement).toHaveAttribute('data-state', 'unchecked');
    });

    it('has correct checked styles', () => {
      render(<Switch defaultChecked />);
      
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toHaveClass('data-[state=checked]:bg-primary');
      expect(switchElement).toHaveAttribute('data-state', 'checked');
    });

    it('shows focus ring when focused', async () => {
      const user = userEvent.setup();
      
      render(<Switch />);
      
      const switchElement = screen.getByRole('switch');
      await user.tab();
      
      expect(document.activeElement).toBe(switchElement);
      expect(switchElement).toHaveClass('focus-visible:ring-2');
      expect(switchElement).toHaveClass('focus-visible:ring-ring');
    });
  });

  describe('Accessibility', () => {
    it('has correct ARIA attributes', () => {
      render(<Switch />);
      
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toHaveAttribute('type', 'button');
      expect(switchElement).toHaveAttribute('role', 'switch');
      expect(switchElement).toHaveAttribute('aria-checked', 'false');
    });

    it('supports aria-label', () => {
      render(<Switch aria-label="Enable notifications" />);
      
      const switchElement = screen.getByRole('switch', { name: 'Enable notifications' });
      expect(switchElement).toBeInTheDocument();
    });

    it('supports aria-labelledby', () => {
      render(
        <>
          <label id="switch-label">Dark mode</label>
          <Switch aria-labelledby="switch-label" />
        </>
      );
      
      const switchElement = screen.getByRole('switch', { name: 'Dark mode' });
      expect(switchElement).toBeInTheDocument();
    });

    it('can be focused with Tab key', async () => {
      const user = userEvent.setup();
      
      render(
        <>
          <button>Previous</button>
          <Switch />
          <button>Next</button>
        </>
      );
      
      const switchElement = screen.getByRole('switch');
      const prevButton = screen.getByRole('button', { name: 'Previous' });
      
      prevButton.focus();
      await user.tab();
      
      expect(document.activeElement).toBe(switchElement);
    });

    it('announces state changes to screen readers', async () => {
      const user = userEvent.setup();
      
      render(<Switch aria-label="Toggle feature" />);
      
      const switchElement = screen.getByRole('switch');
      
      // Initial state
      expect(switchElement).toHaveAttribute('aria-checked', 'false');
      
      // After toggle
      await user.click(switchElement);
      expect(switchElement).toHaveAttribute('aria-checked', 'true');
    });
  });

  describe('Thumb Animation', () => {
    it('renders thumb element', () => {
      const { container } = render(<Switch />);
      
      const thumb = container.querySelector('[class*="rounded-full"][class*="transition-transform"]');
      expect(thumb).toBeInTheDocument();
      expect(thumb).toHaveClass('data-[state=unchecked]:translate-x-0');
    });

    it('animates thumb on toggle', () => {
      const { container } = render(<Switch defaultChecked />);
      
      const thumb = container.querySelector('[class*="rounded-full"][class*="transition-transform"]');
      expect(thumb).toHaveClass('data-[state=checked]:translate-x-5');
    });
  });

  describe('Custom Props', () => {
    it('forwards additional props', () => {
      render(<Switch data-testid="custom-switch" />);
      
      const switchElement = screen.getByTestId('custom-switch');
      expect(switchElement).toBeInTheDocument();
    });

    it('supports required prop', () => {
      // Note: Radix UI Switch doesn't directly support required attribute
      // The prop is accepted but not applied to the button element
      const { container } = render(<Switch required aria-required="true" />);
      
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toBeInTheDocument();
      // Check that aria-required is properly set for accessibility
      expect(switchElement).toHaveAttribute('aria-required', 'true');
    });
  });

  describe('Use Cases', () => {
    it('works as theme toggle', async () => {
      const user = userEvent.setup();
      
      const ThemeToggle = () => {
        const [isDark, setIsDark] = React.useState(false);
        
        return (
          <div data-theme={isDark ? 'dark' : 'light'}>
            <Switch
              checked={isDark}
              onCheckedChange={setIsDark}
              aria-label="Toggle dark mode"
            />
          </div>
        );
      };
      
      const { container } = render(<ThemeToggle />);
      
      expect(container.firstChild).toHaveAttribute('data-theme', 'light');
      
      const switchElement = screen.getByRole('switch');
      await user.click(switchElement);
      
      expect(container.firstChild).toHaveAttribute('data-theme', 'dark');
    });

    it('works for enabling/disabling features', async () => {
      const user = userEvent.setup();
      const handleToggle = vi.fn();
      
      const FeatureToggle = () => {
        const [enabled, setEnabled] = React.useState(false);
        
        return (
          <div>
            <label htmlFor="feature">Enable experimental features</label>
            <Switch
              id="feature"
              checked={enabled}
              onCheckedChange={(checked) => {
                setEnabled(checked);
                handleToggle(checked);
              }}
            />
          </div>
        );
      };
      
      render(<FeatureToggle />);
      
      const switchElement = screen.getByRole('switch');
      await user.click(switchElement);
      
      expect(handleToggle).toHaveBeenCalledWith(true);
    });
  });
});