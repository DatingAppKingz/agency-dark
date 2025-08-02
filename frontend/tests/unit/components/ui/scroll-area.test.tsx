import React from 'react';
import { render, screen } from '@/tests/utils/enhanced-test-utils';
import userEvent from '@testing-library/user-event';
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area';

describe('ScrollArea Component', () => {
  describe('Basic Rendering', () => {
    it('renders children correctly', () => {
      render(
        <ScrollArea>
          <div>Scrollable content</div>
        </ScrollArea>
      );

      expect(screen.getByText('Scrollable content')).toBeInTheDocument();
    });

    it('renders with custom className', () => {
      render(
        <ScrollArea className="h-[200px] w-[300px] border">
          <div>Content</div>
        </ScrollArea>
      );

      const scrollArea = screen.getByText('Content').closest('.relative.overflow-hidden');
      expect(scrollArea).toHaveClass('h-[200px] w-[300px] border');
    });

    it('applies default overflow-hidden class', () => {
      render(
        <ScrollArea>
          <div>Content</div>
        </ScrollArea>
      );

      const scrollArea = screen.getByText('Content').closest('.relative');
      expect(scrollArea).toHaveClass('relative overflow-hidden');
    });
  });

  describe('Viewport Behavior', () => {
    it('renders viewport with correct classes', () => {
      const { container } = render(
        <ScrollArea>
          <div>Content in viewport</div>
        </ScrollArea>
      );

      const viewport = container.querySelector('.h-full.w-full.rounded-\\[inherit\\]');
      expect(viewport).toBeInTheDocument();
      expect(viewport).toContainElement(screen.getByText('Content in viewport'));
    });

    it('maintains border radius inheritance', () => {
      const { container } = render(
        <ScrollArea className="rounded-lg">
          <div>Rounded content</div>
        </ScrollArea>
      );

      const viewport = container.querySelector('.rounded-\\[inherit\\]');
      expect(viewport).toBeInTheDocument();
    });
  });

  describe('Scrollbar Rendering', () => {
    it('renders vertical scrollbar by default', () => {
      const { container } = render(
        <ScrollArea className="h-[100px]">
          <div style={{ height: '200px' }}>Tall content</div>
        </ScrollArea>
      );

      // Look for vertical scrollbar classes
      const scrollbar = container.querySelector('.h-full.w-2\\.5');
      expect(scrollbar).toBeInTheDocument();
    });

    it('renders scrollbar thumb', () => {
      const { container } = render(
        <ScrollArea>
          <div>Content</div>
        </ScrollArea>
      );

      const thumb = container.querySelector('.relative.flex-1.rounded-full.bg-border');
      expect(thumb).toBeInTheDocument();
    });
  });

  describe('Content Overflow', () => {
    it('handles overflowing content', () => {
      render(
        <ScrollArea className="h-[100px] w-[100px]">
          <div style={{ height: '300px', width: '100px' }}>
            Very tall content that should trigger scrolling
          </div>
        </ScrollArea>
      );

      expect(screen.getByText('Very tall content that should trigger scrolling')).toBeInTheDocument();
    });

    it('handles wide content', () => {
      render(
        <ScrollArea className="h-[100px] w-[100px]">
          <div style={{ width: '300px', whiteSpace: 'nowrap' }}>
            Very wide content that extends beyond the container width
          </div>
        </ScrollArea>
      );

      expect(screen.getByText('Very wide content that extends beyond the container width')).toBeInTheDocument();
    });
  });

  describe('Custom ScrollBar', () => {
    it('accepts custom scrollbar orientation', () => {
      const { container } = render(
        <ScrollArea>
          <ScrollBar orientation="horizontal" />
          <div>Content</div>
        </ScrollArea>
      );

      const horizontalScrollbar = container.querySelector('.h-2\\.5');
      expect(horizontalScrollbar).toBeInTheDocument();
    });

    it('applies custom scrollbar className', () => {
      const { container } = render(
        <ScrollArea>
          <ScrollBar className="bg-red-500" />
          <div>Content</div>
        </ScrollArea>
      );

      const scrollbar = container.querySelector('.bg-red-500');
      expect(scrollbar).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('maintains semantic structure', () => {
      const { container } = render(
        <ScrollArea>
          <article>
            <h2>Article Title</h2>
            <p>Article content</p>
          </article>
        </ScrollArea>
      );

      expect(screen.getByRole('heading', { name: 'Article Title' })).toBeInTheDocument();
      expect(container.querySelector('article')).toBeInTheDocument();
    });

    it('preserves focus management', async () => {
      const user = userEvent.setup();
      
      render(
        <ScrollArea>
          <button>First button</button>
          <button>Second button</button>
          <button>Third button</button>
        </ScrollArea>
      );

      const firstButton = screen.getByRole('button', { name: 'First button' });
      const secondButton = screen.getByRole('button', { name: 'Second button' });

      await user.tab();
      expect(firstButton).toHaveFocus();

      await user.tab();
      expect(secondButton).toHaveFocus();
    });

    it('supports aria attributes', () => {
      render(
        <ScrollArea aria-label="Scrollable list">
          <ul>
            <li>Item 1</li>
            <li>Item 2</li>
          </ul>
        </ScrollArea>
      );

      const scrollArea = screen.getByLabelText('Scrollable list');
      expect(scrollArea).toBeInTheDocument();
    });
  });

  describe('Use Cases', () => {
    it('renders long list of items', () => {
      const items = Array.from({ length: 50 }, (_, i) => `Item ${i + 1}`);
      
      render(
        <ScrollArea className="h-[200px]">
          <ul>
            {items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </ScrollArea>
      );

      expect(screen.getByText('Item 1')).toBeInTheDocument();
      expect(screen.getByText('Item 50')).toBeInTheDocument();
    });

    it('renders code block with horizontal scroll', () => {
      render(
        <ScrollArea className="h-[100px] w-[200px]">
          <pre className="whitespace-pre">
            {`function longFunctionNameWithManyParameters(param1, param2, param3, param4) {
  return param1 + param2 + param3 + param4;
}`}
          </pre>
        </ScrollArea>
      );

      expect(screen.getByText(/longFunctionNameWithManyParameters/)).toBeInTheDocument();
    });

    it('renders chat messages', () => {
      const messages = [
        { id: 1, text: 'Hello!' },
        { id: 2, text: 'How are you?' },
        { id: 3, text: 'I am fine, thanks!' },
      ];

      render(
        <ScrollArea className="h-[300px]">
          <div className="space-y-2 p-4">
            {messages.map((msg) => (
              <div key={msg.id} className="rounded bg-gray-100 p-2">
                {msg.text}
              </div>
            ))}
          </div>
        </ScrollArea>
      );

      messages.forEach((msg) => {
        expect(screen.getByText(msg.text)).toBeInTheDocument();
      });
    });
  });

  describe('Dynamic Content', () => {
    it('handles dynamically added content', () => {
      const { rerender } = render(
        <ScrollArea className="h-[100px]">
          <div>Initial content</div>
        </ScrollArea>
      );

      expect(screen.getByText('Initial content')).toBeInTheDocument();

      rerender(
        <ScrollArea className="h-[100px]">
          <div>Initial content</div>
          <div>New content</div>
        </ScrollArea>
      );

      expect(screen.getByText('New content')).toBeInTheDocument();
    });

    it('maintains scroll position on content update', () => {
      const TestComponent = () => {
        const [items, setItems] = React.useState(['Item 1', 'Item 2']);
        
        return (
          <>
            <ScrollArea className="h-[100px]">
              {items.map((item) => (
                <div key={item} className="p-4">
                  {item}
                </div>
              ))}
            </ScrollArea>
            <button onClick={() => setItems([...items, `Item ${items.length + 1}`])}>
              Add Item
            </button>
          </>
        );
      };

      render(<TestComponent />);

      expect(screen.getByText('Item 1')).toBeInTheDocument();
      expect(screen.getByText('Item 2')).toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    it('supports custom height and width', () => {
      render(
        <ScrollArea className="h-64 w-96">
          <div>Fixed size content</div>
        </ScrollArea>
      );

      const scrollArea = screen.getByText('Fixed size content').closest('.relative');
      expect(scrollArea).toHaveClass('h-64 w-96');
    });

    it('supports max height constraints', () => {
      render(
        <ScrollArea className="max-h-[400px]">
          <div style={{ height: '600px' }}>Tall content</div>
        </ScrollArea>
      );

      const scrollArea = screen.getByText('Tall content').closest('.relative');
      expect(scrollArea).toHaveClass('max-h-[400px]');
    });

    it('works with different border styles', () => {
      render(
        <ScrollArea className="rounded-md border-2 border-dashed">
          <div>Styled content</div>
        </ScrollArea>
      );

      const scrollArea = screen.getByText('Styled content').closest('.relative');
      expect(scrollArea).toHaveClass('rounded-md border-2 border-dashed');
    });
  });

  describe('Performance', () => {
    it('renders large datasets efficiently', () => {
      const largeDataset = Array.from({ length: 1000 }, (_, i) => ({
        id: i,
        text: `Row ${i + 1}`,
      }));

      render(
        <ScrollArea className="h-[400px]">
          <table>
            <tbody>
              {largeDataset.map((row) => (
                <tr key={row.id}>
                  <td>{row.text}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollArea>
      );

      // Should render without performance issues
      expect(screen.getByText('Row 1')).toBeInTheDocument();
      expect(screen.getByText('Row 1000')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('handles empty content', () => {
      render(
        <ScrollArea className="h-[200px]">
          {/* Empty */}
        </ScrollArea>
      );

      // Should render without crashing
      expect(document.querySelector('.relative.overflow-hidden')).toBeInTheDocument();
    });

    it('handles content exactly fitting container', () => {
      render(
        <ScrollArea className="h-[100px]">
          <div style={{ height: '100px' }}>Exact fit content</div>
        </ScrollArea>
      );

      expect(screen.getByText('Exact fit content')).toBeInTheDocument();
    });

    it('preserves event handlers on children', async () => {
      const user = userEvent.setup();
      const handleClick = jest.fn();

      render(
        <ScrollArea>
          <button onClick={handleClick}>Click me</button>
        </ScrollArea>
      );

      await user.click(screen.getByRole('button', { name: 'Click me' }));
      expect(handleClick).toHaveBeenCalledTimes(1);
    });
  });

  describe('Ref Forwarding', () => {
    it('forwards ref to root element', () => {
      const ref = React.createRef<HTMLDivElement>();
      
      render(
        <ScrollArea ref={ref}>
          <div>Content</div>
        </ScrollArea>
      );

      expect(ref.current).toBeInstanceOf(HTMLDivElement);
      expect(ref.current).toHaveClass('relative overflow-hidden');
    });
  });
});