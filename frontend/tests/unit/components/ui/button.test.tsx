import React from 'react';
import { vi } from 'vitest';
import { render, screen } from '../../../utils/enhanced-test-utils';
import userEvent from '@testing-library/user-event';
import { Button } from '@/components/ui/button';

describe('Button Component', () => {
  it('renders with text content', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument();
  });

  it('handles click events', async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();
    
    render(<Button onClick={handleClick}>Click me</Button>);
    const button = screen.getByRole('button', { name: /click me/i });
    
    await user.click(button);
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('can be disabled', () => {
    render(<Button disabled>Disabled Button</Button>);
    const button = screen.getByRole('button', { name: /disabled button/i });
    
    expect(button).toBeDisabled();
  });

  it('does not trigger click when disabled', async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();
    
    render(<Button disabled onClick={handleClick}>Disabled</Button>);
    const button = screen.getByRole('button', { name: /disabled/i });
    
    await user.click(button);
    expect(handleClick).not.toHaveBeenCalled();
  });

  describe('Button Variants', () => {
    it('renders default variant', () => {
      render(<Button variant="default">Default</Button>);
      const button = screen.getByRole('button', { name: /default/i });
      expect(button).toHaveClass('bg-primary');
    });

    it('renders destructive variant', () => {
      render(<Button variant="destructive">Delete</Button>);
      const button = screen.getByRole('button', { name: /delete/i });
      expect(button).toHaveClass('bg-destructive');
    });

    it('renders outline variant', () => {
      render(<Button variant="outline">Outline</Button>);
      const button = screen.getByRole('button', { name: /outline/i });
      expect(button).toHaveClass('border-input');
    });

    it('renders secondary variant', () => {
      render(<Button variant="secondary">Secondary</Button>);
      const button = screen.getByRole('button', { name: /secondary/i });
      expect(button).toHaveClass('bg-secondary');
    });

    it('renders ghost variant', () => {
      render(<Button variant="ghost">Ghost</Button>);
      const button = screen.getByRole('button', { name: /ghost/i });
      expect(button).toHaveClass('hover:bg-accent');
    });

    it('renders link variant', () => {
      render(<Button variant="link">Link</Button>);
      const button = screen.getByRole('button', { name: /link/i });
      expect(button).toHaveClass('underline-offset-4');
    });
  });

  describe('Button Sizes', () => {
    it('renders default size', () => {
      render(<Button size="default">Default Size</Button>);
      const button = screen.getByRole('button', { name: /default size/i });
      expect(button).toHaveClass('h-10', 'px-4', 'py-2');
    });

    it('renders small size', () => {
      render(<Button size="sm">Small</Button>);
      const button = screen.getByRole('button', { name: /small/i });
      expect(button).toHaveClass('h-9', 'px-3');
    });

    it('renders large size', () => {
      render(<Button size="lg">Large</Button>);
      const button = screen.getByRole('button', { name: /large/i });
      expect(button).toHaveClass('h-11', 'px-8');
    });

    it('renders icon size', () => {
      render(<Button size="icon">🔥</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('h-10', 'w-10');
    });
  });

  it('renders as a child component when asChild is true', () => {
    render(
      <Button asChild>
        <a href="/test">Link Button</a>
      </Button>
    );
    
    const link = screen.getByRole('link', { name: /link button/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/test');
  });

  it('accepts and applies custom className', () => {
    render(<Button className="custom-class">Custom</Button>);
    const button = screen.getByRole('button', { name: /custom/i });
    expect(button).toHaveClass('custom-class');
  });

  it('forwards ref correctly', () => {
    const ref = React.createRef<HTMLButtonElement>();
    render(<Button ref={ref}>Ref Button</Button>);
    
    expect(ref.current).toBeInstanceOf(HTMLButtonElement);
    expect(ref.current?.textContent).toBe('Ref Button');
  });

  it('supports type attribute', () => {
    render(<Button type="submit">Submit</Button>);
    const button = screen.getByRole('button', { name: /submit/i });
    expect(button).toHaveAttribute('type', 'submit');
  });

  it('handles keyboard navigation', async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();
    
    render(<Button onClick={handleClick}>Keyboard Test</Button>);
    const button = screen.getByRole('button', { name: /keyboard test/i });
    
    button.focus();
    await user.keyboard('{Enter}');
    expect(handleClick).toHaveBeenCalledTimes(1);
    
    await user.keyboard(' '); // Space key
    expect(handleClick).toHaveBeenCalledTimes(2);
  });

  describe('Accessibility', () => {
    it('has correct ARIA attributes', () => {
      render(
        <Button aria-label="Save document" aria-pressed="true">
          Save
        </Button>
      );
      
      const button = screen.getByRole('button', { name: /save document/i });
      expect(button).toHaveAttribute('aria-pressed', 'true');
    });

    it('supports aria-disabled', () => {
      render(<Button aria-disabled="true">Aria Disabled</Button>);
      const button = screen.getByRole('button', { name: /aria disabled/i });
      expect(button).toHaveAttribute('aria-disabled', 'true');
    });

    it('maintains focus styles', () => {
      render(<Button>Focus Test</Button>);
      const button = screen.getByRole('button', { name: /focus test/i });
      
      button.focus();
      expect(button).toHaveFocus();
      expect(button).toHaveClass('focus-visible:outline-none');
    });
  });
});