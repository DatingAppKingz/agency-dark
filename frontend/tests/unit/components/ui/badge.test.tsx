import React from 'react';
import { vi } from 'vitest';
import { render, screen } from '../../../utils/enhanced-test-utils';
import { Badge } from '@/components/ui/badge';

describe('Badge Component', () => {
  it('renders with text content', () => {
    render(<Badge>New</Badge>);
    expect(screen.getByText('New')).toBeInTheDocument();
  });

  it('renders with default variant styling', () => {
    render(<Badge>Default</Badge>);
    const badge = screen.getByText('Default');
    expect(badge).toHaveClass('bg-primary', 'text-primary-foreground');
  });

  describe('Badge Variants', () => {
    it('renders secondary variant', () => {
      render(<Badge variant="secondary">Secondary</Badge>);
      const badge = screen.getByText('Secondary');
      expect(badge).toHaveClass('bg-secondary', 'text-secondary-foreground');
    });

    it('renders destructive variant', () => {
      render(<Badge variant="destructive">Error</Badge>);
      const badge = screen.getByText('Error');
      expect(badge).toHaveClass('bg-destructive', 'text-destructive-foreground');
    });

    it('renders outline variant', () => {
      render(<Badge variant="outline">Outline</Badge>);
      const badge = screen.getByText('Outline');
      expect(badge).toHaveClass('border');
    });
  });

  it('accepts and applies custom className', () => {
    render(<Badge className="custom-badge">Custom</Badge>);
    const badge = screen.getByText('Custom');
    expect(badge).toHaveClass('custom-badge');
  });

  it('maintains base styling with custom classes', () => {
    render(<Badge className="ml-2">Spaced</Badge>);
    const badge = screen.getByText('Spaced');
    expect(badge).toHaveClass('inline-flex', 'items-center', 'ml-2');
  });

  it('can render with HTML elements inside', () => {
    render(
      <Badge>
        <span>Count: </span>
        <strong>5</strong>
      </Badge>
    );
    expect(screen.getByText('Count:')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('renders with proper spacing and sizing', () => {
    render(<Badge>Sized</Badge>);
    const badge = screen.getByText('Sized');
    expect(badge).toHaveClass('px-2.5', 'py-0.5', 'text-xs');
  });

  it('renders with proper border radius', () => {
    render(<Badge>Rounded</Badge>);
    const badge = screen.getByText('Rounded');
    expect(badge).toHaveClass('rounded-full');
  });

  it('can be used as status indicator', () => {
    const { rerender } = render(<Badge variant="default">Active</Badge>);
    expect(screen.getByText('Active')).toHaveClass('bg-primary');
    
    rerender(<Badge variant="secondary">Inactive</Badge>);
    expect(screen.getByText('Inactive')).toHaveClass('bg-secondary');
    
    rerender(<Badge variant="destructive">Error</Badge>);
    expect(screen.getByText('Error')).toHaveClass('bg-destructive');
  });

  it('works with numbers', () => {
    render(<Badge>42</Badge>);
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('works with long text and maintains layout', () => {
    render(<Badge>This is a very long badge text</Badge>);
    const badge = screen.getByText('This is a very long badge text');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass('inline-flex'); // Should not wrap
  });

  describe('Accessibility', () => {
    it('can have role attribute', () => {
      render(<Badge role="status">Status Badge</Badge>);
      expect(screen.getByRole('status')).toHaveTextContent('Status Badge');
    });

    it('can have aria-label', () => {
      render(<Badge aria-label="3 new notifications">3</Badge>);
      const badge = screen.getByText('3');
      expect(badge).toHaveAttribute('aria-label', '3 new notifications');
    });

    it('maintains semantic HTML', () => {
      const { container } = render(<Badge>Semantic</Badge>);
      const badge = container.firstChild;
      expect(badge?.nodeName).toBe('DIV');
    });
  });

  describe('Common use cases', () => {
    it('renders as notification count', () => {
      render(
        <div>
          <span>Notifications</span>
          <Badge variant="destructive" className="ml-2">
            5
          </Badge>
        </div>
      );
      
      const badge = screen.getByText('5');
      expect(badge).toHaveClass('bg-destructive', 'ml-2');
    });

    it('renders as status indicator in a list', () => {
      render(
        <div>
          <span>Server Status: </span>
          <Badge variant="outline">Online</Badge>
        </div>
      );
      
      expect(screen.getByText('Online')).toHaveClass('border');
    });

    it('renders as a tag', () => {
      render(
        <div>
          <Badge variant="secondary">JavaScript</Badge>
          <Badge variant="secondary">React</Badge>
          <Badge variant="secondary">TypeScript</Badge>
        </div>
      );
      
      expect(screen.getByText('JavaScript')).toBeInTheDocument();
      expect(screen.getByText('React')).toBeInTheDocument();
      expect(screen.getByText('TypeScript')).toBeInTheDocument();
    });
  });
});