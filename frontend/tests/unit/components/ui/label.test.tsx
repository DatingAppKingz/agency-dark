import React from 'react';
import { vi } from 'vitest';
import { render, screen } from '@/tests/utils/enhanced-test-utils';
import userEvent from '@testing-library/user-event';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';

describe('Label Component', () => {
  describe('Basic Rendering', () => {
    it('renders label text correctly', () => {
      render(<Label>Email Address</Label>);
      
      expect(screen.getByText('Email Address')).toBeInTheDocument();
    });

    it('renders with default styles', () => {
      render(<Label>Test Label</Label>);
      
      const label = screen.getByText('Test Label');
      expect(label).toHaveClass('text-sm font-medium leading-none');
    });

    it('renders with custom className', () => {
      render(<Label className="text-red-500 text-lg">Custom Label</Label>);
      
      const label = screen.getByText('Custom Label');
      expect(label).toHaveClass('text-red-500 text-lg');
      // Should also retain default classes
      expect(label).toHaveClass('text-sm font-medium leading-none');
    });

    it('renders as label element', () => {
      render(<Label>Form Label</Label>);
      
      const label = screen.getByText('Form Label');
      expect(label.tagName).toBe('LABEL');
    });
  });

  describe('Form Association', () => {
    it('associates with form control using htmlFor', () => {
      render(
        <>
          <Label htmlFor="email-input">Email</Label>
          <Input id="email-input" type="email" />
        </>
      );
      
      const label = screen.getByText('Email');
      const input = screen.getByRole('textbox');
      
      expect(label).toHaveAttribute('for', 'email-input');
      expect(input).toHaveAttribute('id', 'email-input');
    });

    it('clicking label focuses associated input', async () => {
      const user = userEvent.setup();
      
      render(
        <>
          <Label htmlFor="username">Username</Label>
          <Input id="username" />
        </>
      );
      
      const label = screen.getByText('Username');
      const input = screen.getByRole('textbox');
      
      await user.click(label);
      expect(input).toHaveFocus();
    });

    it('works with nested input', async () => {
      const user = userEvent.setup();
      
      render(
        <Label>
          Email
          <Input type="email" />
        </Label>
      );
      
      const label = screen.getByText('Email');
      const input = screen.getByRole('textbox');
      
      await user.click(label);
      expect(input).toHaveFocus();
    });

    it('works with checkbox input', async () => {
      const user = userEvent.setup();
      const handleChange = vi.fn();
      
      render(
        <>
          <input 
            type="checkbox" 
            id="terms" 
            onChange={(e) => handleChange(e.target.checked)} 
          />
          <Label htmlFor="terms">Accept terms and conditions</Label>
        </>
      );
      
      const label = screen.getByText('Accept terms and conditions');
      await user.click(label);
      
      expect(handleChange).toHaveBeenCalledWith(true);
    });
  });

  describe('Disabled State Handling', () => {
    it('applies disabled styles when peer is disabled', () => {
      render(
        <div className="space-y-2">
          <Label htmlFor="disabled-input" className="peer-disabled:opacity-70">
            Disabled Field
          </Label>
          <Input id="disabled-input" disabled className="peer" />
        </div>
      );
      
      const label = screen.getByText('Disabled Field');
      expect(label).toHaveClass('peer-disabled:cursor-not-allowed');
      expect(label).toHaveClass('peer-disabled:opacity-70');
    });

    it('shows not-allowed cursor for disabled peer', () => {
      render(
        <div>
          <Input disabled className="peer" />
          <Label>This label is for a disabled input</Label>
        </div>
      );
      
      const label = screen.getByText('This label is for a disabled input');
      expect(label).toHaveClass('peer-disabled:cursor-not-allowed');
    });
  });

  describe('Required Field Indication', () => {
    it('renders with required asterisk', () => {
      render(
        <Label>
          Email
          <span className="text-red-500 ml-1">*</span>
        </Label>
      );
      
      expect(screen.getByText('Email')).toBeInTheDocument();
      expect(screen.getByText('*')).toBeInTheDocument();
      expect(screen.getByText('*')).toHaveClass('text-red-500');
    });

    it('can use aria-required', () => {
      render(
        <>
          <Label htmlFor="required-field">Required Field</Label>
          <Input id="required-field" aria-required="true" />
        </>
      );
      
      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('aria-required', 'true');
    });
  });

  describe('Accessibility', () => {
    it('provides accessible name to form controls', () => {
      render(
        <>
          <Label htmlFor="name-input">Full Name</Label>
          <Input id="name-input" />
        </>
      );
      
      const input = screen.getByLabelText('Full Name');
      expect(input).toBeInTheDocument();
    });

    it('supports aria-label override', () => {
      render(
        <Label aria-label="Enter your email address">
          Email
        </Label>
      );
      
      const label = screen.getByLabelText('Enter your email address');
      expect(label).toHaveTextContent('Email');
    });

    it('supports aria-describedby for additional context', () => {
      render(
        <>
          <Label htmlFor="password">Password</Label>
          <Input id="password" type="password" aria-describedby="password-help" />
          <p id="password-help" className="text-sm text-muted-foreground">
            Must be at least 8 characters
          </p>
        </>
      );
      
      const input = screen.getByLabelText('Password');
      expect(input).toHaveAttribute('aria-describedby', 'password-help');
    });

    it('maintains semantic HTML structure', () => {
      const { container } = render(
        <Label htmlFor="test-input">Test Label</Label>
      );
      
      const label = container.querySelector('label');
      expect(label).toBeInTheDocument();
      expect(label).toHaveAttribute('for', 'test-input');
    });
  });

  describe('Complex Form Layouts', () => {
    it('works in form groups', () => {
      render(
        <div className="space-y-2">
          <Label htmlFor="email">Email Address</Label>
          <Input id="email" type="email" placeholder="you@example.com" />
          <p className="text-sm text-muted-foreground">
            We'll never share your email
          </p>
        </div>
      );
      
      expect(screen.getByLabelText('Email Address')).toBeInTheDocument();
      expect(screen.getByText("We'll never share your email")).toBeInTheDocument();
    });

    it('works with inline form layouts', () => {
      render(
        <div className="flex items-center space-x-2">
          <input type="checkbox" id="remember" />
          <Label htmlFor="remember" className="cursor-pointer">
            Remember me
          </Label>
        </div>
      );
      
      const label = screen.getByText('Remember me');
      expect(label).toHaveClass('cursor-pointer');
    });

    it('works with radio button groups', () => {
      render(
        <div className="space-y-2">
          <Label>Select an option</Label>
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <input type="radio" id="option1" name="options" />
              <Label htmlFor="option1">Option 1</Label>
            </div>
            <div className="flex items-center space-x-2">
              <input type="radio" id="option2" name="options" />
              <Label htmlFor="option2">Option 2</Label>
            </div>
          </div>
        </div>
      );
      
      expect(screen.getByText('Select an option')).toBeInTheDocument();
      expect(screen.getByText('Option 1')).toBeInTheDocument();
      expect(screen.getByText('Option 2')).toBeInTheDocument();
    });
  });

  describe('Styling Flexibility', () => {
    it('supports different text sizes', () => {
      const { rerender } = render(
        <Label className="text-xs">Extra Small</Label>
      );
      
      expect(screen.getByText('Extra Small')).toHaveClass('text-xs');
      
      rerender(<Label className="text-lg">Large</Label>);
      expect(screen.getByText('Large')).toHaveClass('text-lg');
    });

    it('supports different font weights', () => {
      render(
        <>
          <Label className="font-normal">Normal Weight</Label>
          <Label className="font-bold">Bold Weight</Label>
        </>
      );
      
      expect(screen.getByText('Normal Weight')).toHaveClass('font-normal');
      expect(screen.getByText('Bold Weight')).toHaveClass('font-bold');
    });

    it('supports color variations', () => {
      render(
        <>
          <Label className="text-primary">Primary Label</Label>
          <Label className="text-destructive">Error Label</Label>
          <Label className="text-muted-foreground">Muted Label</Label>
        </>
      );
      
      expect(screen.getByText('Primary Label')).toHaveClass('text-primary');
      expect(screen.getByText('Error Label')).toHaveClass('text-destructive');
      expect(screen.getByText('Muted Label')).toHaveClass('text-muted-foreground');
    });
  });

  describe('Event Handling', () => {
    it('supports onClick handler', async () => {
      const user = userEvent.setup();
      const handleClick = vi.fn();
      
      render(
        <Label onClick={handleClick}>Clickable Label</Label>
      );
      
      await user.click(screen.getByText('Clickable Label'));
      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('supports onMouseEnter and onMouseLeave', async () => {
      const user = userEvent.setup();
      const handleMouseEnter = vi.fn();
      const handleMouseLeave = vi.fn();
      
      render(
        <Label 
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        >
          Hover Label
        </Label>
      );
      
      const label = screen.getByText('Hover Label');
      
      await user.hover(label);
      expect(handleMouseEnter).toHaveBeenCalled();
      
      await user.unhover(label);
      expect(handleMouseLeave).toHaveBeenCalled();
    });
  });

  describe('Edge Cases', () => {
    it('renders without children', () => {
      render(<Label />);
      
      // Should render without crashing
      expect(document.querySelector('label')).toBeInTheDocument();
    });

    it('renders with complex children', () => {
      render(
        <Label>
          <span className="font-bold">Name:</span>
          <span className="ml-1 text-red-500">*</span>
        </Label>
      );
      
      expect(screen.getByText('Name:')).toBeInTheDocument();
      expect(screen.getByText('*')).toBeInTheDocument();
    });

    it('preserves ref forwarding', () => {
      const ref = React.createRef<HTMLLabelElement>();
      
      render(<Label ref={ref}>Label with ref</Label>);
      
      expect(ref.current).toBeInstanceOf(HTMLLabelElement);
      expect(ref.current).toHaveTextContent('Label with ref');
    });
  });

  describe('Integration Examples', () => {
    it('works in a complete form field', async () => {
      const user = userEvent.setup();
      const handleSubmit = vi.fn((e) => e.preventDefault());
      
      render(
        <form onSubmit={handleSubmit}>
          <div className="space-y-2">
            <Label htmlFor="username">Username</Label>
            <Input 
              id="username" 
              name="username"
              required 
              placeholder="Enter username"
            />
          </div>
          <button type="submit">Submit</button>
        </form>
      );
      
      const input = screen.getByLabelText('Username');
      await user.type(input, 'johndoe');
      await user.click(screen.getByRole('button', { name: 'Submit' }));
      
      expect(handleSubmit).toHaveBeenCalled();
      expect(input).toHaveValue('johndoe');
    });

    it('works with error states', () => {
      render(
        <div className="space-y-2">
          <Label htmlFor="email" className="text-destructive">
            Email Address
          </Label>
          <Input 
            id="email" 
            type="email" 
            className="border-destructive"
            aria-invalid="true"
            aria-describedby="email-error"
          />
          <p id="email-error" className="text-sm text-destructive">
            Please enter a valid email address
          </p>
        </div>
      );
      
      const label = screen.getByText('Email Address');
      expect(label).toHaveClass('text-destructive');
      
      const input = screen.getByLabelText('Email Address');
      expect(input).toHaveAttribute('aria-invalid', 'true');
    });
  });
});