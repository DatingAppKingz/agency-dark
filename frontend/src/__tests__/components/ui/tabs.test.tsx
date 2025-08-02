import React from 'react';
import { render, screen } from '@/test-utils/enhanced-test-utils';
import userEvent from '@testing-library/user-event';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

describe('Tabs Component', () => {
  describe('Basic Rendering', () => {
    it('renders tabs correctly', () => {
      render(
        <Tabs defaultValue="tab1">
          <TabsList>
            <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            <TabsTrigger value="tab2">Tab 2</TabsTrigger>
          </TabsList>
          <TabsContent value="tab1">Content 1</TabsContent>
          <TabsContent value="tab2">Content 2</TabsContent>
        </Tabs>
      );

      expect(screen.getByRole('tablist')).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: 'Tab 1' })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: 'Tab 2' })).toBeInTheDocument();
      expect(screen.getByText('Content 1')).toBeInTheDocument();
    });

    it('shows correct default tab', () => {
      render(
        <Tabs defaultValue="tab2">
          <TabsList>
            <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            <TabsTrigger value="tab2">Tab 2</TabsTrigger>
          </TabsList>
          <TabsContent value="tab1">Content 1</TabsContent>
          <TabsContent value="tab2">Content 2</TabsContent>
        </Tabs>
      );

      expect(screen.getByText('Content 2')).toBeInTheDocument();
      expect(screen.queryByText('Content 1')).not.toBeInTheDocument();
      expect(screen.getByRole('tab', { name: 'Tab 2' })).toHaveAttribute('data-state', 'active');
    });

    it('renders with custom className', () => {
      render(
        <Tabs defaultValue="tab1" className="custom-tabs">
          <TabsList className="custom-list">
            <TabsTrigger value="tab1" className="custom-trigger">Tab 1</TabsTrigger>
          </TabsList>
          <TabsContent value="tab1" className="custom-content">Content 1</TabsContent>
        </Tabs>
      );

      const tablist = screen.getByRole('tablist');
      expect(tablist).toHaveClass('custom-list');
      expect(screen.getByRole('tab')).toHaveClass('custom-trigger');
      expect(screen.getByRole('tabpanel')).toHaveClass('custom-content');
    });
  });

  describe('Interactions', () => {
    it('switches tabs on click', async () => {
      const user = userEvent.setup();
      
      render(
        <Tabs defaultValue="tab1">
          <TabsList>
            <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            <TabsTrigger value="tab2">Tab 2</TabsTrigger>
          </TabsList>
          <TabsContent value="tab1">Content 1</TabsContent>
          <TabsContent value="tab2">Content 2</TabsContent>
        </Tabs>
      );

      expect(screen.getByText('Content 1')).toBeInTheDocument();
      expect(screen.queryByText('Content 2')).not.toBeInTheDocument();

      await user.click(screen.getByRole('tab', { name: 'Tab 2' }));

      expect(screen.queryByText('Content 1')).not.toBeInTheDocument();
      expect(screen.getByText('Content 2')).toBeInTheDocument();
    });

    it('updates active state correctly', async () => {
      const user = userEvent.setup();
      
      render(
        <Tabs defaultValue="tab1">
          <TabsList>
            <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            <TabsTrigger value="tab2">Tab 2</TabsTrigger>
          </TabsList>
          <TabsContent value="tab1">Content 1</TabsContent>
          <TabsContent value="tab2">Content 2</TabsContent>
        </Tabs>
      );

      const tab1 = screen.getByRole('tab', { name: 'Tab 1' });
      const tab2 = screen.getByRole('tab', { name: 'Tab 2' });

      expect(tab1).toHaveAttribute('data-state', 'active');
      expect(tab2).toHaveAttribute('data-state', 'inactive');

      await user.click(tab2);

      expect(tab1).toHaveAttribute('data-state', 'inactive');
      expect(tab2).toHaveAttribute('data-state', 'active');
    });

    it('calls onValueChange when tab changes', async () => {
      const user = userEvent.setup();
      const handleChange = jest.fn();
      
      render(
        <Tabs defaultValue="tab1" onValueChange={handleChange}>
          <TabsList>
            <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            <TabsTrigger value="tab2">Tab 2</TabsTrigger>
          </TabsList>
          <TabsContent value="tab1">Content 1</TabsContent>
          <TabsContent value="tab2">Content 2</TabsContent>
        </Tabs>
      );

      await user.click(screen.getByRole('tab', { name: 'Tab 2' }));
      expect(handleChange).toHaveBeenCalledWith('tab2');
    });
  });

  describe('Keyboard Navigation', () => {
    it('supports arrow key navigation', async () => {
      const user = userEvent.setup();
      
      render(
        <Tabs defaultValue="tab1">
          <TabsList>
            <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            <TabsTrigger value="tab2">Tab 2</TabsTrigger>
            <TabsTrigger value="tab3">Tab 3</TabsTrigger>
          </TabsList>
          <TabsContent value="tab1">Content 1</TabsContent>
          <TabsContent value="tab2">Content 2</TabsContent>
          <TabsContent value="tab3">Content 3</TabsContent>
        </Tabs>
      );

      const tab1 = screen.getByRole('tab', { name: 'Tab 1' });
      tab1.focus();

      // Right arrow
      await user.keyboard('{ArrowRight}');
      expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Tab 2' }));

      // Right arrow again
      await user.keyboard('{ArrowRight}');
      expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Tab 3' }));

      // Left arrow
      await user.keyboard('{ArrowLeft}');
      expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Tab 2' }));
    });

    it('wraps around at ends', async () => {
      const user = userEvent.setup();
      
      render(
        <Tabs defaultValue="tab1">
          <TabsList>
            <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            <TabsTrigger value="tab2">Tab 2</TabsTrigger>
            <TabsTrigger value="tab3">Tab 3</TabsTrigger>
          </TabsList>
        </Tabs>
      );

      const tab3 = screen.getByRole('tab', { name: 'Tab 3' });
      tab3.focus();

      // Right arrow from last tab should go to first
      await user.keyboard('{ArrowRight}');
      expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Tab 1' }));

      // Left arrow from first tab should go to last
      await user.keyboard('{ArrowLeft}');
      expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Tab 3' }));
    });

    it('activates tab on Enter key', async () => {
      const user = userEvent.setup();
      
      render(
        <Tabs defaultValue="tab1">
          <TabsList>
            <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            <TabsTrigger value="tab2">Tab 2</TabsTrigger>
          </TabsList>
          <TabsContent value="tab1">Content 1</TabsContent>
          <TabsContent value="tab2">Content 2</TabsContent>
        </Tabs>
      );

      const tab2 = screen.getByRole('tab', { name: 'Tab 2' });
      tab2.focus();

      await user.keyboard('{Enter}');
      expect(screen.getByText('Content 2')).toBeInTheDocument();
    });

    it('activates tab on Space key', async () => {
      const user = userEvent.setup();
      
      render(
        <Tabs defaultValue="tab1">
          <TabsList>
            <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            <TabsTrigger value="tab2">Tab 2</TabsTrigger>
          </TabsList>
          <TabsContent value="tab1">Content 1</TabsContent>
          <TabsContent value="tab2">Content 2</TabsContent>
        </Tabs>
      );

      const tab2 = screen.getByRole('tab', { name: 'Tab 2' });
      tab2.focus();

      await user.keyboard(' ');
      expect(screen.getByText('Content 2')).toBeInTheDocument();
    });
  });

  describe('Controlled Component', () => {
    it('works as controlled component', async () => {
      const user = userEvent.setup();
      
      const ControlledTabs = () => {
        const [value, setValue] = React.useState('tab1');
        
        return (
          <>
            <Tabs value={value} onValueChange={setValue}>
              <TabsList>
                <TabsTrigger value="tab1">Tab 1</TabsTrigger>
                <TabsTrigger value="tab2">Tab 2</TabsTrigger>
              </TabsList>
              <TabsContent value="tab1">Content 1</TabsContent>
              <TabsContent value="tab2">Content 2</TabsContent>
            </Tabs>
            <div data-testid="current-tab">{value}</div>
          </>
        );
      };

      render(<ControlledTabs />);

      expect(screen.getByTestId('current-tab')).toHaveTextContent('tab1');
      
      await user.click(screen.getByRole('tab', { name: 'Tab 2' }));
      
      expect(screen.getByTestId('current-tab')).toHaveTextContent('tab2');
      expect(screen.getByText('Content 2')).toBeInTheDocument();
    });
  });

  describe('Disabled State', () => {
    it('disables individual tabs', async () => {
      const user = userEvent.setup();
      
      render(
        <Tabs defaultValue="tab1">
          <TabsList>
            <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            <TabsTrigger value="tab2" disabled>Tab 2</TabsTrigger>
            <TabsTrigger value="tab3">Tab 3</TabsTrigger>
          </TabsList>
          <TabsContent value="tab1">Content 1</TabsContent>
          <TabsContent value="tab2">Content 2</TabsContent>
          <TabsContent value="tab3">Content 3</TabsContent>
        </Tabs>
      );

      const disabledTab = screen.getByRole('tab', { name: 'Tab 2' });
      expect(disabledTab).toBeDisabled();
      expect(disabledTab).toHaveClass('disabled:pointer-events-none');
      expect(disabledTab).toHaveClass('disabled:opacity-50');

      await user.click(disabledTab);
      expect(screen.queryByText('Content 2')).not.toBeInTheDocument();
    });

    it('skips disabled tabs in keyboard navigation', async () => {
      const user = userEvent.setup();
      
      render(
        <Tabs defaultValue="tab1">
          <TabsList>
            <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            <TabsTrigger value="tab2" disabled>Tab 2</TabsTrigger>
            <TabsTrigger value="tab3">Tab 3</TabsTrigger>
          </TabsList>
        </Tabs>
      );

      const tab1 = screen.getByRole('tab', { name: 'Tab 1' });
      tab1.focus();

      // Right arrow should skip disabled tab
      await user.keyboard('{ArrowRight}');
      expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Tab 3' }));
    });
  });

  describe('Orientation', () => {
    it('supports vertical orientation', () => {
      render(
        <Tabs defaultValue="tab1" orientation="vertical">
          <TabsList>
            <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            <TabsTrigger value="tab2">Tab 2</TabsTrigger>
          </TabsList>
          <TabsContent value="tab1">Content 1</TabsContent>
          <TabsContent value="tab2">Content 2</TabsContent>
        </Tabs>
      );

      const tablist = screen.getByRole('tablist');
      expect(tablist).toHaveAttribute('aria-orientation', 'vertical');
    });

    it('uses up/down arrows for vertical navigation', async () => {
      const user = userEvent.setup();
      
      render(
        <Tabs defaultValue="tab1" orientation="vertical">
          <TabsList>
            <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            <TabsTrigger value="tab2">Tab 2</TabsTrigger>
            <TabsTrigger value="tab3">Tab 3</TabsTrigger>
          </TabsList>
        </Tabs>
      );

      const tab1 = screen.getByRole('tab', { name: 'Tab 1' });
      tab1.focus();

      // Down arrow
      await user.keyboard('{ArrowDown}');
      expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Tab 2' }));

      // Up arrow
      await user.keyboard('{ArrowUp}');
      expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Tab 1' }));
    });
  });

  describe('Accessibility', () => {
    it('has correct ARIA attributes', () => {
      render(
        <Tabs defaultValue="tab1">
          <TabsList>
            <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            <TabsTrigger value="tab2">Tab 2</TabsTrigger>
          </TabsList>
          <TabsContent value="tab1">Content 1</TabsContent>
          <TabsContent value="tab2">Content 2</TabsContent>
        </Tabs>
      );

      const tablist = screen.getByRole('tablist');
      expect(tablist).toHaveAttribute('aria-orientation', 'horizontal');

      const activeTab = screen.getByRole('tab', { name: 'Tab 1' });
      expect(activeTab).toHaveAttribute('aria-selected', 'true');
      expect(activeTab).toHaveAttribute('tabindex', '0');

      const inactiveTab = screen.getByRole('tab', { name: 'Tab 2' });
      expect(inactiveTab).toHaveAttribute('aria-selected', 'false');
      expect(inactiveTab).toHaveAttribute('tabindex', '-1');

      const tabpanel = screen.getByRole('tabpanel');
      expect(tabpanel).toHaveAttribute('aria-labelledby', activeTab.id);
    });

    it('supports aria-label on tabs', () => {
      render(
        <Tabs defaultValue="tab1" aria-label="Settings tabs">
          <TabsList>
            <TabsTrigger value="tab1">General</TabsTrigger>
            <TabsTrigger value="tab2">Security</TabsTrigger>
          </TabsList>
          <TabsContent value="tab1">General settings</TabsContent>
          <TabsContent value="tab2">Security settings</TabsContent>
        </Tabs>
      );

      const tablist = screen.getByRole('tablist', { name: 'Settings tabs' });
      expect(tablist).toBeInTheDocument();
    });

    it('focuses tab panel when activated', async () => {
      const user = userEvent.setup();
      
      render(
        <Tabs defaultValue="tab1">
          <TabsList>
            <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            <TabsTrigger value="tab2">Tab 2</TabsTrigger>
          </TabsList>
          <TabsContent value="tab1" tabIndex={0}>
            <button>Button in tab 1</button>
          </TabsContent>
          <TabsContent value="tab2" tabIndex={0}>
            <button>Button in tab 2</button>
          </TabsContent>
        </Tabs>
      );

      await user.click(screen.getByRole('tab', { name: 'Tab 2' }));
      
      const tabpanel = screen.getByRole('tabpanel');
      expect(tabpanel).toHaveAttribute('tabindex', '0');
    });
  });

  describe('Styling', () => {
    it('applies correct active styles', () => {
      render(
        <Tabs defaultValue="tab1">
          <TabsList>
            <TabsTrigger value="tab1">Tab 1</TabsTrigger>
            <TabsTrigger value="tab2">Tab 2</TabsTrigger>
          </TabsList>
        </Tabs>
      );

      const activeTab = screen.getByRole('tab', { name: 'Tab 1' });
      expect(activeTab).toHaveClass('data-[state=active]:bg-background');
      expect(activeTab).toHaveClass('data-[state=active]:text-foreground');
      expect(activeTab).toHaveClass('data-[state=active]:shadow-sm');
    });

    it('shows focus ring when focused', async () => {
      const user = userEvent.setup();
      
      render(
        <Tabs defaultValue="tab1">
          <TabsList>
            <TabsTrigger value="tab1">Tab 1</TabsTrigger>
          </TabsList>
        </Tabs>
      );

      const tab = screen.getByRole('tab');
      await user.tab();
      
      expect(document.activeElement).toBe(tab);
      expect(tab).toHaveClass('focus-visible:ring-2');
      expect(tab).toHaveClass('focus-visible:ring-ring');
    });
  });

  describe('Complex Content', () => {
    it('handles complex content in tabs', () => {
      render(
        <Tabs defaultValue="tab1">
          <TabsList>
            <TabsTrigger value="tab1">Overview</TabsTrigger>
            <TabsTrigger value="tab2">Details</TabsTrigger>
          </TabsList>
          <TabsContent value="tab1">
            <h3>Overview</h3>
            <p>This is the overview content</p>
            <button>Action</button>
          </TabsContent>
          <TabsContent value="tab2">
            <form>
              <input type="text" placeholder="Name" />
              <button type="submit">Submit</button>
            </form>
          </TabsContent>
        </Tabs>
      );

      expect(screen.getByRole('heading', { name: 'Overview' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Action' })).toBeInTheDocument();
    });

    it('maintains content state when switching tabs', async () => {
      const user = userEvent.setup();
      
      render(
        <Tabs defaultValue="tab1">
          <TabsList>
            <TabsTrigger value="tab1">Form</TabsTrigger>
            <TabsTrigger value="tab2">Other</TabsTrigger>
          </TabsList>
          <TabsContent value="tab1">
            <input type="text" placeholder="Enter text" />
          </TabsContent>
          <TabsContent value="tab2">Other content</TabsContent>
        </Tabs>
      );

      const input = screen.getByPlaceholderText('Enter text');
      await user.type(input, 'Hello');
      
      // Switch to tab 2
      await user.click(screen.getByRole('tab', { name: 'Other' }));
      
      // Switch back to tab 1
      await user.click(screen.getByRole('tab', { name: 'Form' }));
      
      // Input value should be preserved
      expect(screen.getByPlaceholderText('Enter text')).toHaveValue('Hello');
    });
  });
});