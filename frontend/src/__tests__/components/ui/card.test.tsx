import React from 'react';
import { render, screen } from '@/test-utils/enhanced-test-utils';
import {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardDescription,
  CardContent,
} from '@/components/ui/card';

describe('Card Components', () => {
  describe('Card', () => {
    it('renders with children', () => {
      render(
        <Card>
          <div>Card content</div>
        </Card>
      );
      expect(screen.getByText('Card content')).toBeInTheDocument();
    });

    it('applies default styling', () => {
      const { container } = render(<Card>Content</Card>);
      const card = container.firstChild;
      expect(card).toHaveClass('rounded-lg', 'border', 'bg-card', 'text-card-foreground');
    });

    it('accepts custom className', () => {
      const { container } = render(<Card className="custom-card">Content</Card>);
      const card = container.firstChild;
      expect(card).toHaveClass('custom-card');
    });

    it('forwards ref correctly', () => {
      const ref = React.createRef<HTMLDivElement>();
      render(<Card ref={ref}>Content</Card>);
      expect(ref.current).toBeInstanceOf(HTMLDivElement);
    });
  });

  describe('CardHeader', () => {
    it('renders with children', () => {
      render(
        <CardHeader>
          <div>Header content</div>
        </CardHeader>
      );
      expect(screen.getByText('Header content')).toBeInTheDocument();
    });

    it('applies correct spacing', () => {
      const { container } = render(<CardHeader>Header</CardHeader>);
      const header = container.firstChild;
      expect(header).toHaveClass('space-y-1.5', 'p-6');
    });

    it('accepts custom className', () => {
      const { container } = render(
        <CardHeader className="custom-header">Header</CardHeader>
      );
      const header = container.firstChild;
      expect(header).toHaveClass('custom-header');
    });
  });

  describe('CardTitle', () => {
    it('renders as h3 by default', () => {
      render(<CardTitle>Card Title</CardTitle>);
      const title = screen.getByText('Card Title');
      expect(title.tagName).toBe('H3');
    });

    it('applies correct typography styles', () => {
      render(<CardTitle>Title</CardTitle>);
      const title = screen.getByText('Title');
      expect(title).toHaveClass('text-2xl', 'font-semibold', 'leading-none');
    });

    it('accepts custom className', () => {
      render(<CardTitle className="custom-title">Title</CardTitle>);
      const title = screen.getByText('Title');
      expect(title).toHaveClass('custom-title');
    });
  });

  describe('CardDescription', () => {
    it('renders as p element', () => {
      render(<CardDescription>Description text</CardDescription>);
      const description = screen.getByText('Description text');
      expect(description.tagName).toBe('P');
    });

    it('applies muted text styling', () => {
      render(<CardDescription>Description</CardDescription>);
      const description = screen.getByText('Description');
      expect(description).toHaveClass('text-sm', 'text-muted-foreground');
    });

    it('accepts custom className', () => {
      render(
        <CardDescription className="custom-desc">Description</CardDescription>
      );
      const description = screen.getByText('Description');
      expect(description).toHaveClass('custom-desc');
    });
  });

  describe('CardContent', () => {
    it('renders with children', () => {
      render(
        <CardContent>
          <p>Content paragraph</p>
        </CardContent>
      );
      expect(screen.getByText('Content paragraph')).toBeInTheDocument();
    });

    it('applies correct padding', () => {
      const { container } = render(<CardContent>Content</CardContent>);
      const content = container.firstChild;
      expect(content).toHaveClass('p-6', 'pt-0');
    });

    it('accepts custom className', () => {
      const { container } = render(
        <CardContent className="custom-content">Content</CardContent>
      );
      const content = container.firstChild;
      expect(content).toHaveClass('custom-content');
    });
  });

  describe('CardFooter', () => {
    it('renders with children', () => {
      render(
        <CardFooter>
          <button>Action</button>
        </CardFooter>
      );
      expect(screen.getByRole('button', { name: 'Action' })).toBeInTheDocument();
    });

    it('applies flex layout by default', () => {
      const { container } = render(<CardFooter>Footer</CardFooter>);
      const footer = container.firstChild;
      expect(footer).toHaveClass('flex', 'items-center', 'p-6', 'pt-0');
    });

    it('accepts custom className', () => {
      const { container } = render(
        <CardFooter className="custom-footer">Footer</CardFooter>
      );
      const footer = container.firstChild;
      expect(footer).toHaveClass('custom-footer');
    });
  });

  describe('Complete Card composition', () => {
    it('renders a complete card with all subcomponents', () => {
      render(
        <Card>
          <CardHeader>
            <CardTitle>Card Title</CardTitle>
            <CardDescription>Card description text</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Card content goes here</p>
          </CardContent>
          <CardFooter>
            <button>Save</button>
            <button>Cancel</button>
          </CardFooter>
        </Card>
      );

      expect(screen.getByText('Card Title')).toBeInTheDocument();
      expect(screen.getByText('Card description text')).toBeInTheDocument();
      expect(screen.getByText('Card content goes here')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
    });

    it('maintains proper structure and spacing', () => {
      const { container } = render(
        <Card>
          <CardHeader>
            <CardTitle>Title</CardTitle>
          </CardHeader>
          <CardContent>Content</CardContent>
        </Card>
      );

      const card = container.firstChild;
      expect(card).toHaveClass('rounded-lg', 'border');
      
      const header = card?.firstChild;
      expect(header).toHaveClass('p-6');
      
      const content = header?.nextSibling;
      expect(content).toHaveClass('p-6', 'pt-0');
    });
  });

  describe('Accessibility', () => {
    it('card can have role attribute', () => {
      const { container } = render(<Card role="article">Content</Card>);
      const card = container.firstChild;
      expect(card).toHaveAttribute('role', 'article');
    });

    it('supports aria attributes', () => {
      const { container } = render(
        <Card aria-label="User profile card">Content</Card>
      );
      const card = container.firstChild;
      expect(card).toHaveAttribute('aria-label', 'User profile card');
    });

    it('maintains semantic heading hierarchy', () => {
      render(
        <Card>
          <CardHeader>
            <CardTitle>Main Title</CardTitle>
            <CardDescription>Supporting text</CardDescription>
          </CardHeader>
        </Card>
      );

      const title = screen.getByText('Main Title');
      expect(title.tagName).toBe('H3');
      
      const description = screen.getByText('Supporting text');
      expect(description.tagName).toBe('P');
    });
  });

  describe('Common use cases', () => {
    it('renders as a user profile card', () => {
      render(
        <Card>
          <CardHeader>
            <CardTitle>John Doe</CardTitle>
            <CardDescription>Software Developer</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Building awesome applications</p>
          </CardContent>
        </Card>
      );

      expect(screen.getByText('John Doe')).toBeInTheDocument();
      expect(screen.getByText('Software Developer')).toBeInTheDocument();
    });

    it('renders as a stats card', () => {
      render(
        <Card>
          <CardHeader>
            <CardTitle>Total Revenue</CardTitle>
            <CardDescription>+20.1% from last month</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">$45,231.89</div>
          </CardContent>
        </Card>
      );

      expect(screen.getByText('Total Revenue')).toBeInTheDocument();
      expect(screen.getByText('$45,231.89')).toBeInTheDocument();
    });
  });
});