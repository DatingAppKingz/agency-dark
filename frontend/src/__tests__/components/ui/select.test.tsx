import React from 'react';
import { render, screen, waitFor } from '@/test-utils/enhanced-test-utils';
import userEvent from '@testing-library/user-event';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

describe('Select Component', () => {
  describe('Basic Rendering', () => {
    it('renders select trigger correctly', () => {
      render(
        <Select>
          <SelectTrigger>
            <SelectValue placeholder="Select an option" />
          </SelectTrigger>
        </Select>
      );

      const trigger = screen.getByRole('combobox');
      expect(trigger).toBeInTheDocument();
      expect(trigger).toHaveAttribute('aria-haspopup', 'listbox');
      expect(screen.getByText('Select an option')).toBeInTheDocument();
    });

    it('renders with default value', () => {
      render(
        <Select defaultValue="option1">
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="option1">Option 1</SelectItem>
            <SelectItem value="option2">Option 2</SelectItem>
          </SelectContent>
        </Select>
      );

      expect(screen.getByRole('combobox')).toHaveTextContent('Option 1');
    });

    it('renders with custom className', () => {
      render(
        <Select>
          <SelectTrigger className="custom-trigger">
            <SelectValue />
          </SelectTrigger>
        </Select>
      );

      expect(screen.getByRole('combobox')).toHaveClass('custom-trigger');
    });
  });

  describe('Interactions', () => {
    it('opens dropdown when trigger is clicked', async () => {
      const user = userEvent.setup();
      
      render(
        <Select>
          <SelectTrigger>
            <SelectValue placeholder="Select an option" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="option1">Option 1</SelectItem>
            <SelectItem value="option2">Option 2</SelectItem>
          </SelectContent>
        </Select>
      );

      const trigger = screen.getByRole('combobox');
      await user.click(trigger);

      await waitFor(() => {
        expect(screen.getByRole('listbox')).toBeInTheDocument();
        expect(screen.getByRole('option', { name: 'Option 1' })).toBeInTheDocument();
        expect(screen.getByRole('option', { name: 'Option 2' })).toBeInTheDocument();
      });
    });

    it('selects an option when clicked', async () => {
      const user = userEvent.setup();
      const handleChange = jest.fn();
      
      render(
        <Select onValueChange={handleChange}>
          <SelectTrigger>
            <SelectValue placeholder="Select an option" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="option1">Option 1</SelectItem>
            <SelectItem value="option2">Option 2</SelectItem>
          </SelectContent>
        </Select>
      );

      // Open select
      await user.click(screen.getByRole('combobox'));

      // Click option
      await user.click(screen.getByRole('option', { name: 'Option 2' }));

      expect(handleChange).toHaveBeenCalledWith('option2');
      expect(screen.getByRole('combobox')).toHaveTextContent('Option 2');
    });

    it('closes dropdown after selection', async () => {
      const user = userEvent.setup();
      
      render(
        <Select>
          <SelectTrigger>
            <SelectValue placeholder="Select an option" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="option1">Option 1</SelectItem>
          </SelectContent>
        </Select>
      );

      // Open and select
      await user.click(screen.getByRole('combobox'));
      await user.click(screen.getByRole('option', { name: 'Option 1' }));

      // Dropdown should be closed
      await waitFor(() => {
        expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
      });
    });

    it('handles keyboard navigation', async () => {
      const user = userEvent.setup();
      
      render(
        <Select>
          <SelectTrigger>
            <SelectValue placeholder="Select an option" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="option1">Option 1</SelectItem>
            <SelectItem value="option2">Option 2</SelectItem>
            <SelectItem value="option3">Option 3</SelectItem>
          </SelectContent>
        </Select>
      );

      const trigger = screen.getByRole('combobox');
      await user.click(trigger);

      // Navigate with arrow keys
      await user.keyboard('{ArrowDown}');
      await user.keyboard('{ArrowDown}');
      await user.keyboard('{Enter}');

      expect(trigger).toHaveTextContent('Option 2');
    });
  });

  describe('Select Groups', () => {
    it('renders grouped items correctly', async () => {
      const user = userEvent.setup();
      
      render(
        <Select>
          <SelectTrigger>
            <SelectValue placeholder="Select a fruit" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectLabel>Fruits</SelectLabel>
              <SelectItem value="apple">Apple</SelectItem>
              <SelectItem value="banana">Banana</SelectItem>
            </SelectGroup>
            <SelectSeparator />
            <SelectGroup>
              <SelectLabel>Vegetables</SelectLabel>
              <SelectItem value="carrot">Carrot</SelectItem>
              <SelectItem value="broccoli">Broccoli</SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>
      );

      await user.click(screen.getByRole('combobox'));

      expect(screen.getByText('Fruits')).toBeInTheDocument();
      expect(screen.getByText('Vegetables')).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Apple' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Carrot' })).toBeInTheDocument();
    });
  });

  describe('Disabled State', () => {
    it('disables the trigger when disabled prop is true', () => {
      render(
        <Select disabled>
          <SelectTrigger>
            <SelectValue placeholder="Select an option" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="option1">Option 1</SelectItem>
          </SelectContent>
        </Select>
      );

      const trigger = screen.getByRole('combobox');
      expect(trigger).toBeDisabled();
      expect(trigger).toHaveClass('disabled:cursor-not-allowed');
      expect(trigger).toHaveClass('disabled:opacity-50');
    });

    it('does not open when disabled', async () => {
      const user = userEvent.setup();
      
      render(
        <Select disabled>
          <SelectTrigger>
            <SelectValue placeholder="Select an option" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="option1">Option 1</SelectItem>
          </SelectContent>
        </Select>
      );

      await user.click(screen.getByRole('combobox'));
      expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    });

    it('disables individual items', async () => {
      const user = userEvent.setup();
      
      render(
        <Select>
          <SelectTrigger>
            <SelectValue placeholder="Select an option" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="option1">Option 1</SelectItem>
            <SelectItem value="option2" disabled>Option 2</SelectItem>
          </SelectContent>
        </Select>
      );

      await user.click(screen.getByRole('combobox'));

      const disabledOption = screen.getByRole('option', { name: 'Option 2' });
      expect(disabledOption).toHaveAttribute('aria-disabled', 'true');
      expect(disabledOption).toHaveClass('data-[disabled]:opacity-50');
    });
  });

  describe('Controlled Component', () => {
    it('works as controlled component', async () => {
      const user = userEvent.setup();
      const ControlledSelect = () => {
        const [value, setValue] = React.useState('option1');
        
        return (
          <>
            <Select value={value} onValueChange={setValue}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="option1">Option 1</SelectItem>
                <SelectItem value="option2">Option 2</SelectItem>
              </SelectContent>
            </Select>
            <span data-testid="current-value">{value}</span>
          </>
        );
      };

      render(<ControlledSelect />);

      expect(screen.getByTestId('current-value')).toHaveTextContent('option1');
      expect(screen.getByRole('combobox')).toHaveTextContent('Option 1');

      await user.click(screen.getByRole('combobox'));
      await user.click(screen.getByRole('option', { name: 'Option 2' }));

      expect(screen.getByTestId('current-value')).toHaveTextContent('option2');
      expect(screen.getByRole('combobox')).toHaveTextContent('Option 2');
    });
  });

  describe('Accessibility', () => {
    it('has correct ARIA attributes', () => {
      render(
        <Select>
          <SelectTrigger aria-label="Select a color">
            <SelectValue placeholder="Select a color" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="red">Red</SelectItem>
            <SelectItem value="blue">Blue</SelectItem>
          </SelectContent>
        </Select>
      );

      const trigger = screen.getByRole('combobox');
      expect(trigger).toHaveAttribute('aria-haspopup', 'listbox');
      expect(trigger).toHaveAttribute('aria-expanded', 'false');
      expect(trigger).toHaveAttribute('aria-label', 'Select a color');
    });

    it('updates aria-expanded when opened', async () => {
      const user = userEvent.setup();
      
      render(
        <Select>
          <SelectTrigger>
            <SelectValue placeholder="Select an option" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="option1">Option 1</SelectItem>
          </SelectContent>
        </Select>
      );

      const trigger = screen.getByRole('combobox');
      expect(trigger).toHaveAttribute('aria-expanded', 'false');

      await user.click(trigger);
      expect(trigger).toHaveAttribute('aria-expanded', 'true');
    });

    it('supports keyboard shortcuts', async () => {
      const user = userEvent.setup();
      
      render(
        <Select>
          <SelectTrigger>
            <SelectValue placeholder="Select an option" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="option1">Option 1</SelectItem>
            <SelectItem value="option2">Option 2</SelectItem>
          </SelectContent>
        </Select>
      );

      const trigger = screen.getByRole('combobox');
      trigger.focus();

      // Open with Space
      await user.keyboard(' ');
      await waitFor(() => {
        expect(screen.getByRole('listbox')).toBeInTheDocument();
      });

      // Close with Escape
      await user.keyboard('{Escape}');
      await waitFor(() => {
        expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
      });
    });
  });

  describe('Select with Icons', () => {
    it('renders chevron icon in trigger', () => {
      render(
        <Select>
          <SelectTrigger>
            <SelectValue placeholder="Select an option" />
          </SelectTrigger>
        </Select>
      );

      const chevron = screen.getByRole('combobox').querySelector('svg');
      expect(chevron).toBeInTheDocument();
      expect(chevron).toHaveClass('h-4 w-4 opacity-50');
    });

    it('shows check icon for selected item', async () => {
      const user = userEvent.setup();
      
      render(
        <Select defaultValue="option1">
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="option1">Option 1</SelectItem>
            <SelectItem value="option2">Option 2</SelectItem>
          </SelectContent>
        </Select>
      );

      await user.click(screen.getByRole('combobox'));

      const selectedOption = screen.getByRole('option', { name: 'Option 1' });
      const checkIcon = selectedOption.querySelector('svg');
      expect(checkIcon).toBeInTheDocument();
    });
  });

  describe('Custom Styling', () => {
    it('applies custom content styles', async () => {
      const user = userEvent.setup();
      
      render(
        <Select>
          <SelectTrigger>
            <SelectValue placeholder="Select an option" />
          </SelectTrigger>
          <SelectContent className="custom-content">
            <SelectItem value="option1">Option 1</SelectItem>
          </SelectContent>
        </Select>
      );

      await user.click(screen.getByRole('combobox'));
      
      const content = screen.getByRole('listbox').parentElement;
      expect(content).toHaveClass('custom-content');
    });

    it('handles position prop correctly', async () => {
      const user = userEvent.setup();
      
      render(
        <Select>
          <SelectTrigger>
            <SelectValue placeholder="Select an option" />
          </SelectTrigger>
          <SelectContent position="popper">
            <SelectItem value="option1">Option 1</SelectItem>
          </SelectContent>
        </Select>
      );

      await user.click(screen.getByRole('combobox'));
      
      const content = screen.getByRole('listbox').parentElement;
      expect(content).toHaveClass('data-[side=bottom]:translate-y-1');
    });
  });

  describe('Error Handling', () => {
    it('handles missing value gracefully', () => {
      render(
        <Select>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
        </Select>
      );

      const trigger = screen.getByRole('combobox');
      expect(trigger).toBeInTheDocument();
      expect(trigger).toHaveTextContent('');
    });

    it('handles empty options list', async () => {
      const user = userEvent.setup();
      
      render(
        <Select>
          <SelectTrigger>
            <SelectValue placeholder="Select an option" />
          </SelectTrigger>
          <SelectContent>
            {/* No items */}
          </SelectContent>
        </Select>
      );

      await user.click(screen.getByRole('combobox'));
      expect(screen.getByRole('listbox')).toBeInTheDocument();
      expect(screen.queryByRole('option')).not.toBeInTheDocument();
    });
  });
});