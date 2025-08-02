import React from 'react';
import { render, screen, waitFor } from '@/tests/utils/enhanced-test-utils';
import userEvent from '@testing-library/user-event';
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

describe('DropdownMenu Component', () => {
  describe('Basic Rendering', () => {
    it('renders dropdown trigger correctly', () => {
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Open Menu</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem>Item 1</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      expect(screen.getByText('Open Menu')).toBeInTheDocument();
    });

    it('opens menu on click', async () => {
      const user = userEvent.setup();
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Open Menu</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem>Item 1</DropdownMenuItem>
            <DropdownMenuItem>Item 2</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      await user.click(screen.getByText('Open Menu'));

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
        expect(screen.getByRole('menuitem', { name: 'Item 1' })).toBeInTheDocument();
        expect(screen.getByRole('menuitem', { name: 'Item 2' })).toBeInTheDocument();
      });
    });

    it('renders with custom className', () => {
      render(
        <DropdownMenu>
          <DropdownMenuTrigger className="custom-trigger">Menu</DropdownMenuTrigger>
          <DropdownMenuContent className="custom-content">
            <DropdownMenuItem className="custom-item">Item</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      expect(screen.getByText('Menu')).toHaveClass('custom-trigger');
    });
  });

  describe('Menu Items', () => {
    it('executes onClick handler when item is clicked', async () => {
      const user = userEvent.setup();
      const handleClick = jest.fn();
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem onClick={handleClick}>Click me</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      await user.click(screen.getByText('Menu'));
      await user.click(screen.getByRole('menuitem', { name: 'Click me' }));

      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('closes menu after item click by default', async () => {
      const user = userEvent.setup();
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem>Item</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      await user.click(screen.getByText('Menu'));
      await user.click(screen.getByRole('menuitem', { name: 'Item' }));

      await waitFor(() => {
        expect(screen.queryByRole('menu')).not.toBeInTheDocument();
      });
    });

    it('prevents default on item click with preventDefault', async () => {
      const user = userEvent.setup();
      const handleClick = jest.fn((e) => e.preventDefault());
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem onSelect={handleClick}>Item</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      await user.click(screen.getByText('Menu'));
      await user.click(screen.getByRole('menuitem', { name: 'Item' }));

      expect(handleClick).toHaveBeenCalled();
      // Menu should stay open when preventDefault is called
      expect(screen.getByRole('menu')).toBeInTheDocument();
    });

    it('supports disabled items', async () => {
      const user = userEvent.setup();
      const handleClick = jest.fn();
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem disabled onClick={handleClick}>
              Disabled Item
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      await user.click(screen.getByText('Menu'));
      
      const disabledItem = screen.getByRole('menuitem', { name: 'Disabled Item' });
      expect(disabledItem).toHaveAttribute('aria-disabled', 'true');
      
      await user.click(disabledItem);
      expect(handleClick).not.toHaveBeenCalled();
    });
  });

  describe('Checkbox Items', () => {
    it('toggles checkbox state on click', async () => {
      const user = userEvent.setup();
      const handleChange = jest.fn();
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Settings</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuCheckboxItem
              checked={false}
              onCheckedChange={handleChange}
            >
              Show Toolbar
            </DropdownMenuCheckboxItem>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      await user.click(screen.getByText('Settings'));
      await user.click(screen.getByRole('menuitemcheckbox', { name: 'Show Toolbar' }));

      expect(handleChange).toHaveBeenCalledWith(true);
    });

    it('displays check icon when checked', async () => {
      const user = userEvent.setup();
      
      const ControlledCheckbox = () => {
        const [checked, setChecked] = React.useState(false);
        
        return (
          <DropdownMenu>
            <DropdownMenuTrigger>Settings</DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuCheckboxItem
                checked={checked}
                onCheckedChange={setChecked}
              >
                Option
              </DropdownMenuCheckboxItem>
            </DropdownMenuContent>
          </DropdownMenu>
        );
      };

      render(<ControlledCheckbox />);

      await user.click(screen.getByText('Settings'));
      
      const checkbox = screen.getByRole('menuitemcheckbox', { name: 'Option' });
      expect(checkbox).toHaveAttribute('aria-checked', 'false');
      
      await user.click(checkbox);
      expect(checkbox).toHaveAttribute('aria-checked', 'true');
    });
  });

  describe('Radio Items', () => {
    it('selects radio item on click', async () => {
      const user = userEvent.setup();
      const handleChange = jest.fn();
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Theme</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuRadioGroup value="light" onValueChange={handleChange}>
              <DropdownMenuRadioItem value="light">Light</DropdownMenuRadioItem>
              <DropdownMenuRadioItem value="dark">Dark</DropdownMenuRadioItem>
              <DropdownMenuRadioItem value="system">System</DropdownMenuRadioItem>
            </DropdownMenuRadioGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      await user.click(screen.getByText('Theme'));
      await user.click(screen.getByRole('menuitemradio', { name: 'Dark' }));

      expect(handleChange).toHaveBeenCalledWith('dark');
    });

    it('shows indicator for selected radio item', async () => {
      const user = userEvent.setup();
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Size</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuRadioGroup value="medium">
              <DropdownMenuRadioItem value="small">Small</DropdownMenuRadioItem>
              <DropdownMenuRadioItem value="medium">Medium</DropdownMenuRadioItem>
              <DropdownMenuRadioItem value="large">Large</DropdownMenuRadioItem>
            </DropdownMenuRadioGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      await user.click(screen.getByText('Size'));
      
      const mediumItem = screen.getByRole('menuitemradio', { name: 'Medium' });
      expect(mediumItem).toHaveAttribute('aria-checked', 'true');
      
      const smallItem = screen.getByRole('menuitemradio', { name: 'Small' });
      expect(smallItem).toHaveAttribute('aria-checked', 'false');
    });
  });

  describe('Sub Menus', () => {
    it('opens submenu on hover', async () => {
      const user = userEvent.setup();
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem>Item 1</DropdownMenuItem>
            <DropdownMenuSub>
              <DropdownMenuSubTrigger>More Options</DropdownMenuSubTrigger>
              <DropdownMenuSubContent>
                <DropdownMenuItem>Sub Item 1</DropdownMenuItem>
                <DropdownMenuItem>Sub Item 2</DropdownMenuItem>
              </DropdownMenuSubContent>
            </DropdownMenuSub>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      await user.click(screen.getByText('Menu'));
      
      const subTrigger = screen.getByText('More Options');
      await user.hover(subTrigger);

      await waitFor(() => {
        expect(screen.getByRole('menuitem', { name: 'Sub Item 1' })).toBeInTheDocument();
        expect(screen.getByRole('menuitem', { name: 'Sub Item 2' })).toBeInTheDocument();
      });
    });

    it('shows chevron icon in sub trigger', async () => {
      const user = userEvent.setup();
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuSub>
              <DropdownMenuSubTrigger>More</DropdownMenuSubTrigger>
              <DropdownMenuSubContent>
                <DropdownMenuItem>Item</DropdownMenuItem>
              </DropdownMenuSubContent>
            </DropdownMenuSub>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      await user.click(screen.getByText('Menu'));
      
      const subTrigger = screen.getByText('More').closest('[role="menuitem"]');
      const chevron = subTrigger?.querySelector('svg');
      expect(chevron).toBeInTheDocument();
      expect(chevron).toHaveClass('ml-auto');
    });
  });

  describe('Menu Structure', () => {
    it('renders labels correctly', async () => {
      const user = userEvent.setup();
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuLabel>Account</DropdownMenuLabel>
            <DropdownMenuItem>Profile</DropdownMenuItem>
            <DropdownMenuItem>Settings</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      await user.click(screen.getByText('Menu'));
      
      expect(screen.getByText('Account')).toBeInTheDocument();
      expect(screen.getByText('Account')).toHaveClass('font-semibold');
    });

    it('renders separators', async () => {
      const user = userEvent.setup();
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem>Item 1</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem>Item 2</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      await user.click(screen.getByText('Menu'));
      
      const separator = screen.getByRole('separator');
      expect(separator).toBeInTheDocument();
      expect(separator).toHaveClass('h-px bg-muted');
    });

    it('renders shortcuts', async () => {
      const user = userEvent.setup();
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem>
              Save
              <DropdownMenuShortcut>⌘S</DropdownMenuShortcut>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      await user.click(screen.getByText('Menu'));
      
      expect(screen.getByText('⌘S')).toBeInTheDocument();
      expect(screen.getByText('⌘S')).toHaveClass('ml-auto text-xs tracking-widest opacity-60');
    });

    it('supports grouped items', async () => {
      const user = userEvent.setup();
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuGroup>
              <DropdownMenuLabel>My Account</DropdownMenuLabel>
              <DropdownMenuItem>Profile</DropdownMenuItem>
              <DropdownMenuItem>Billing</DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuLabel>Team</DropdownMenuLabel>
              <DropdownMenuItem>Invite users</DropdownMenuItem>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      await user.click(screen.getByText('Menu'));
      
      expect(screen.getByText('My Account')).toBeInTheDocument();
      expect(screen.getByText('Team')).toBeInTheDocument();
    });
  });

  describe('Keyboard Navigation', () => {
    it('opens with keyboard shortcuts', async () => {
      const user = userEvent.setup();
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem>Item 1</DropdownMenuItem>
            <DropdownMenuItem>Item 2</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      const trigger = screen.getByText('Menu');
      trigger.focus();
      
      await user.keyboard('{Enter}');
      
      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });
    });

    it('navigates with arrow keys', async () => {
      const user = userEvent.setup();
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem>Item 1</DropdownMenuItem>
            <DropdownMenuItem>Item 2</DropdownMenuItem>
            <DropdownMenuItem>Item 3</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      await user.click(screen.getByText('Menu'));
      
      // First item should be focused
      await user.keyboard('{ArrowDown}');
      expect(document.activeElement).toBe(screen.getByRole('menuitem', { name: 'Item 2' }));
      
      await user.keyboard('{ArrowUp}');
      expect(document.activeElement).toBe(screen.getByRole('menuitem', { name: 'Item 1' }));
    });

    it('closes with Escape key', async () => {
      const user = userEvent.setup();
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem>Item</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      await user.click(screen.getByText('Menu'));
      expect(screen.getByRole('menu')).toBeInTheDocument();
      
      await user.keyboard('{Escape}');
      
      await waitFor(() => {
        expect(screen.queryByRole('menu')).not.toBeInTheDocument();
      });
    });

    it('activates items with Enter key', async () => {
      const user = userEvent.setup();
      const handleClick = jest.fn();
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem onClick={handleClick}>Item</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      await user.click(screen.getByText('Menu'));
      
      const item = screen.getByRole('menuitem', { name: 'Item' });
      item.focus();
      
      await user.keyboard('{Enter}');
      expect(handleClick).toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    it('has correct ARIA attributes', async () => {
      const user = userEvent.setup();
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem>Item</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      const trigger = screen.getByText('Menu');
      expect(trigger).toHaveAttribute('aria-haspopup', 'menu');
      expect(trigger).toHaveAttribute('aria-expanded', 'false');
      
      await user.click(trigger);
      
      expect(trigger).toHaveAttribute('aria-expanded', 'true');
      expect(screen.getByRole('menu')).toBeInTheDocument();
    });

    it('manages focus correctly', async () => {
      const user = userEvent.setup();
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem>Item 1</DropdownMenuItem>
            <DropdownMenuItem>Item 2</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      const trigger = screen.getByText('Menu');
      await user.click(trigger);
      
      // Focus should move to menu
      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });
      
      // Close menu
      await user.keyboard('{Escape}');
      
      // Focus should return to trigger
      await waitFor(() => {
        expect(document.activeElement).toBe(trigger);
      });
    });

    it('supports aria-label on items', async () => {
      const user = userEvent.setup();
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Actions</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem aria-label="Delete the selected item">
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      await user.click(screen.getByText('Actions'));
      
      const deleteItem = screen.getByRole('menuitem', { name: 'Delete the selected item' });
      expect(deleteItem).toBeInTheDocument();
    });
  });

  describe('Controlled State', () => {
    it('works as controlled component', async () => {
      const user = userEvent.setup();
      
      const ControlledDropdown = () => {
        const [open, setOpen] = React.useState(false);
        
        return (
          <>
            <DropdownMenu open={open} onOpenChange={setOpen}>
              <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem>Item</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <button onClick={() => setOpen(true)}>Open Menu</button>
            <div data-testid="open-state">{open ? 'open' : 'closed'}</div>
          </>
        );
      };

      render(<ControlledDropdown />);
      
      expect(screen.getByTestId('open-state')).toHaveTextContent('closed');
      
      await user.click(screen.getByText('Open Menu'));
      expect(screen.getByTestId('open-state')).toHaveTextContent('open');
      expect(screen.getByRole('menu')).toBeInTheDocument();
    });
  });

  describe('Complex Use Cases', () => {
    it('handles nested checkbox and radio groups', async () => {
      const user = userEvent.setup();
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>View</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuLabel>Appearance</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuCheckboxItem checked>
              Show Sidebar
            </DropdownMenuCheckboxItem>
            <DropdownMenuCheckboxItem>
              Show Activity Bar
            </DropdownMenuCheckboxItem>
            <DropdownMenuSeparator />
            <DropdownMenuLabel>Panel Position</DropdownMenuLabel>
            <DropdownMenuRadioGroup value="bottom">
              <DropdownMenuRadioItem value="top">Top</DropdownMenuRadioItem>
              <DropdownMenuRadioItem value="bottom">Bottom</DropdownMenuRadioItem>
              <DropdownMenuRadioItem value="right">Right</DropdownMenuRadioItem>
            </DropdownMenuRadioGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      await user.click(screen.getByText('View'));
      
      expect(screen.getByRole('menuitemcheckbox', { name: 'Show Sidebar' })).toHaveAttribute('aria-checked', 'true');
      expect(screen.getByRole('menuitemradio', { name: 'Bottom' })).toHaveAttribute('aria-checked', 'true');
    });

    it('supports inset prop for alignment', async () => {
      const user = userEvent.setup();
      
      render(
        <DropdownMenu>
          <DropdownMenuTrigger>Menu</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem inset>Inset Item</DropdownMenuItem>
            <DropdownMenuLabel inset>Inset Label</DropdownMenuLabel>
          </DropdownMenuContent>
        </DropdownMenu>
      );

      await user.click(screen.getByText('Menu'));
      
      expect(screen.getByRole('menuitem', { name: 'Inset Item' })).toHaveClass('pl-8');
      expect(screen.getByText('Inset Label')).toHaveClass('pl-8');
    });
  });
});