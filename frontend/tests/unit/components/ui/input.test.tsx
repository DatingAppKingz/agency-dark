import React from 'react';
import { vi } from 'vitest';
import { render, screen } from '../../../utils/enhanced-test-utils';
import userEvent from '@testing-library/user-event';
import { Input } from '@/components/ui/input';

describe('Input Component', () => {
  it('renders correctly', () => {
    render(<Input placeholder="Enter text" />);
    expect(screen.getByPlaceholderText('Enter text')).toBeInTheDocument();
  });

  it('accepts and displays typed text', async () => {
    const user = userEvent.setup();
    render(<Input placeholder="Type here" />);
    
    const input = screen.getByPlaceholderText('Type here');
    await user.type(input, 'Hello World');
    
    expect(input).toHaveValue('Hello World');
  });

  it('handles onChange events', async () => {
    const handleChange = vi.fn();
    const user = userEvent.setup();
    
    render(<Input onChange={handleChange} placeholder="Type here" />);
    const input = screen.getByPlaceholderText('Type here');
    
    await user.type(input, 'Test');
    expect(handleChange).toHaveBeenCalledTimes(4); // One for each character
  });

  it('can be disabled', () => {
    render(<Input disabled placeholder="Disabled input" />);
    const input = screen.getByPlaceholderText('Disabled input');
    
    expect(input).toBeDisabled();
  });

  it('does not accept input when disabled', async () => {
    const user = userEvent.setup();
    render(<Input disabled placeholder="Disabled" value="" onChange={() => {}} />);
    
    const input = screen.getByPlaceholderText('Disabled');
    await user.type(input, 'Should not appear');
    
    expect(input).toHaveValue('');
  });

  it('supports different input types', () => {
    const { rerender } = render(<Input type="email" placeholder="Email" />);
    expect(screen.getByPlaceholderText('Email')).toHaveAttribute('type', 'email');
    
    rerender(<Input type="password" placeholder="Password" />);
    expect(screen.getByPlaceholderText('Password')).toHaveAttribute('type', 'password');
    
    rerender(<Input type="number" placeholder="Number" />);
    expect(screen.getByPlaceholderText('Number')).toHaveAttribute('type', 'number');
  });

  it('accepts value prop', () => {
    render(<Input value="Controlled value" onChange={() => {}} />);
    expect(screen.getByDisplayValue('Controlled value')).toBeInTheDocument();
  });

  it('supports defaultValue', () => {
    render(<Input defaultValue="Default text" />);
    expect(screen.getByDisplayValue('Default text')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    render(<Input className="custom-input" placeholder="Custom" />);
    const input = screen.getByPlaceholderText('Custom');
    expect(input).toHaveClass('custom-input');
  });

  it('forwards ref correctly', () => {
    const ref = React.createRef<HTMLInputElement>();
    render(<Input ref={ref} placeholder="Ref test" />);
    
    expect(ref.current).toBeInstanceOf(HTMLInputElement);
    expect(ref.current?.placeholder).toBe('Ref test');
  });

  it('handles focus and blur events', async () => {
    const handleFocus = vi.fn();
    const handleBlur = vi.fn();
    const user = userEvent.setup();
    
    render(
      <Input 
        onFocus={handleFocus} 
        onBlur={handleBlur} 
        placeholder="Focus test" 
      />
    );
    
    const input = screen.getByPlaceholderText('Focus test');
    
    await user.click(input);
    expect(handleFocus).toHaveBeenCalledTimes(1);
    
    await user.tab();
    expect(handleBlur).toHaveBeenCalledTimes(1);
  });

  it('supports maxLength attribute', async () => {
    const user = userEvent.setup();
    render(<Input maxLength={5} placeholder="Max 5 chars" />);
    
    const input = screen.getByPlaceholderText('Max 5 chars');
    await user.type(input, 'Hello World');
    
    expect(input).toHaveValue('Hello');
  });

  it('supports required attribute', () => {
    render(<Input required placeholder="Required field" />);
    const input = screen.getByPlaceholderText('Required field');
    
    expect(input).toBeRequired();
  });

  it('supports pattern attribute', () => {
    render(<Input pattern="[0-9]*" placeholder="Numbers only" />);
    const input = screen.getByPlaceholderText('Numbers only');
    
    expect(input).toHaveAttribute('pattern', '[0-9]*');
  });

  it('clears input with Ctrl+A and Delete', async () => {
    const user = userEvent.setup();
    render(<Input defaultValue="Clear me" />);
    
    const input = screen.getByDisplayValue('Clear me');
    await user.click(input);
    await user.keyboard('{Control>}a{/Control}{Delete}');
    
    expect(input).toHaveValue('');
  });

  describe('Accessibility', () => {
    it('supports aria-label', () => {
      render(<Input aria-label="Search input" />);
      expect(screen.getByLabelText('Search input')).toBeInTheDocument();
    });

    it('supports aria-describedby', () => {
      render(
        <>
          <Input aria-describedby="input-help" />
          <span id="input-help">Help text</span>
        </>
      );
      
      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('aria-describedby', 'input-help');
    });

    it('supports aria-invalid', () => {
      render(<Input aria-invalid="true" placeholder="Invalid input" />);
      const input = screen.getByPlaceholderText('Invalid input');
      
      expect(input).toHaveAttribute('aria-invalid', 'true');
    });

    it('maintains focus styles', () => {
      render(<Input placeholder="Focus styles" />);
      const input = screen.getByPlaceholderText('Focus styles');
      
      input.focus();
      expect(input).toHaveFocus();
      expect(input).toHaveClass('focus-visible:outline-none');
    });
  });

  describe('Input validation', () => {
    it('shows native validation for email type', async () => {
      const user = userEvent.setup();
      render(<Input type="email" placeholder="Email" required />);
      
      const input = screen.getByPlaceholderText('Email') as HTMLInputElement;
      await user.type(input, 'invalid-email');
      
      expect(input.validity.valid).toBe(false);
    });

    it('shows native validation for number type', async () => {
      const user = userEvent.setup();
      render(<Input type="number" min="0" max="10" placeholder="Number" />);
      
      const input = screen.getByPlaceholderText('Number') as HTMLInputElement;
      await user.type(input, '15');
      
      expect(input.validity.valid).toBe(false);
    });
  });
});