import React from 'react';
import { render, screen, waitFor } from '@/test-utils/enhanced-test-utils';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';

describe('Avatar Component', () => {
  describe('Basic Rendering', () => {
    it('renders avatar correctly', () => {
      render(
        <Avatar>
          <AvatarImage src="https://example.com/avatar.jpg" alt="User Avatar" />
          <AvatarFallback>JD</AvatarFallback>
        </Avatar>
      );

      const img = screen.getByRole('img', { name: 'User Avatar' });
      expect(img).toBeInTheDocument();
      expect(img).toHaveAttribute('src', 'https://example.com/avatar.jpg');
    });

    it('renders with custom className', () => {
      const { container } = render(
        <Avatar className="custom-avatar">
          <AvatarImage src="test.jpg" />
          <AvatarFallback>AB</AvatarFallback>
        </Avatar>
      );

      const avatar = container.firstChild;
      expect(avatar).toHaveClass('custom-avatar');
      expect(avatar).toHaveClass('relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full');
    });

    it('renders with custom size through className', () => {
      const { container } = render(
        <Avatar className="h-20 w-20">
          <AvatarImage src="test.jpg" />
          <AvatarFallback>LG</AvatarFallback>
        </Avatar>
      );

      const avatar = container.firstChild;
      expect(avatar).toHaveClass('h-20 w-20');
    });
  });

  describe('Avatar Image', () => {
    it('renders image with correct attributes', () => {
      render(
        <Avatar>
          <AvatarImage 
            src="/avatar.png" 
            alt="Profile picture"
            className="object-cover"
          />
        </Avatar>
      );

      const img = screen.getByRole('img');
      expect(img).toHaveAttribute('src', '/avatar.png');
      expect(img).toHaveAttribute('alt', 'Profile picture');
      expect(img).toHaveClass('aspect-square h-full w-full object-cover');
    });

    it('handles image loading states', async () => {
      const onLoadingStatusChange = jest.fn();
      
      render(
        <Avatar>
          <AvatarImage 
            src="https://example.com/avatar.jpg"
            onLoadingStatusChange={onLoadingStatusChange}
          />
          <AvatarFallback>FB</AvatarFallback>
        </Avatar>
      );

      // Image starts loading
      expect(onLoadingStatusChange).toHaveBeenCalledWith('loading');
    });

    it('shows fallback when image fails to load', async () => {
      // Mock image error
      const onError = jest.fn();
      
      render(
        <Avatar>
          <AvatarImage 
            src="invalid-url.jpg" 
            onError={onError}
          />
          <AvatarFallback>ER</AvatarFallback>
        </Avatar>
      );

      // Simulate image error
      const img = screen.getByRole('img');
      img.dispatchEvent(new Event('error'));

      await waitFor(() => {
        expect(screen.getByText('ER')).toBeInTheDocument();
      });
    });
  });

  describe('Avatar Fallback', () => {
    it('renders fallback text', () => {
      render(
        <Avatar>
          <AvatarFallback>JD</AvatarFallback>
        </Avatar>
      );

      expect(screen.getByText('JD')).toBeInTheDocument();
    });

    it('renders fallback with custom className', () => {
      render(
        <Avatar>
          <AvatarFallback className="bg-primary text-primary-foreground">
            AB
          </AvatarFallback>
        </Avatar>
      );

      const fallback = screen.getByText('AB');
      expect(fallback).toHaveClass('bg-primary text-primary-foreground');
      expect(fallback).toHaveClass('flex h-full w-full items-center justify-center rounded-full');
    });

    it('renders fallback with icon', () => {
      const UserIcon = () => (
        <svg data-testid="user-icon" width="24" height="24">
          <circle cx="12" cy="12" r="10" />
        </svg>
      );

      render(
        <Avatar>
          <AvatarFallback>
            <UserIcon />
          </AvatarFallback>
        </Avatar>
      );

      expect(screen.getByTestId('user-icon')).toBeInTheDocument();
    });

    it('shows fallback immediately when no image provided', () => {
      render(
        <Avatar>
          <AvatarFallback>NO</AvatarFallback>
        </Avatar>
      );

      expect(screen.getByText('NO')).toBeInTheDocument();
    });
  });

  describe('Loading States', () => {
    it('delays showing fallback with delayMs', async () => {
      jest.useFakeTimers();
      
      render(
        <Avatar>
          <AvatarImage src="slow-loading.jpg" />
          <AvatarFallback delayMs={600}>DL</AvatarFallback>
        </Avatar>
      );

      // Fallback should not be visible immediately
      expect(screen.queryByText('DL')).not.toBeInTheDocument();

      // Fast forward time
      jest.advanceTimersByTime(700);

      await waitFor(() => {
        expect(screen.getByText('DL')).toBeInTheDocument();
      });

      jest.useRealTimers();
    });
  });

  describe('Accessibility', () => {
    it('image has proper alt text', () => {
      render(
        <Avatar>
          <AvatarImage src="avatar.jpg" alt="John Doe's avatar" />
          <AvatarFallback>JD</AvatarFallback>
        </Avatar>
      );

      expect(screen.getByAltText("John Doe's avatar")).toBeInTheDocument();
    });

    it('fallback provides accessible text', () => {
      render(
        <Avatar>
          <AvatarFallback aria-label="User initials">UI</AvatarFallback>
        </Avatar>
      );

      const fallback = screen.getByText('UI');
      expect(fallback).toHaveAttribute('aria-label', 'User initials');
    });

    it('supports additional ARIA attributes', () => {
      render(
        <Avatar aria-label="User profile picture">
          <AvatarImage src="test.jpg" />
          <AvatarFallback>FB</AvatarFallback>
        </Avatar>
      );

      const avatar = screen.getByLabelText('User profile picture');
      expect(avatar).toBeInTheDocument();
    });
  });

  describe('Common Use Cases', () => {
    it('renders user avatar with initials fallback', () => {
      const user = {
        name: 'Jane Smith',
        avatarUrl: 'https://example.com/jane.jpg',
        initials: 'JS'
      };

      render(
        <Avatar>
          <AvatarImage src={user.avatarUrl} alt={user.name} />
          <AvatarFallback>{user.initials}</AvatarFallback>
        </Avatar>
      );

      expect(screen.getByRole('img')).toHaveAttribute('alt', 'Jane Smith');
    });

    it('renders group of avatars', () => {
      const users = [
        { id: 1, name: 'User 1', initials: 'U1' },
        { id: 2, name: 'User 2', initials: 'U2' },
        { id: 3, name: 'User 3', initials: 'U3' },
      ];

      render(
        <div className="flex -space-x-2">
          {users.map(user => (
            <Avatar key={user.id} className="border-2 border-background">
              <AvatarFallback>{user.initials}</AvatarFallback>
            </Avatar>
          ))}
        </div>
      );

      expect(screen.getByText('U1')).toBeInTheDocument();
      expect(screen.getByText('U2')).toBeInTheDocument();
      expect(screen.getByText('U3')).toBeInTheDocument();
    });

    it('renders avatar with status indicator', () => {
      render(
        <div className="relative">
          <Avatar>
            <AvatarImage src="user.jpg" />
            <AvatarFallback>US</AvatarFallback>
          </Avatar>
          <span 
            className="absolute bottom-0 right-0 h-3 w-3 rounded-full bg-green-500 ring-2 ring-white"
            aria-label="Online"
          />
        </div>
      );

      expect(screen.getByLabelText('Online')).toBeInTheDocument();
    });
  });

  describe('Image Sources', () => {
    it('handles base64 image sources', () => {
      const base64Image = 'data:image/png;base64,iVBORw0KGgoAAAANS...';
      
      render(
        <Avatar>
          <AvatarImage src={base64Image} alt="Base64 avatar" />
          <AvatarFallback>B64</AvatarFallback>
        </Avatar>
      );

      expect(screen.getByRole('img')).toHaveAttribute('src', base64Image);
    });

    it('handles external URLs', () => {
      render(
        <Avatar>
          <AvatarImage 
            src="https://api.dicebear.com/7.x/avataaars/svg?seed=John" 
            alt="Generated avatar"
          />
          <AvatarFallback>GA</AvatarFallback>
        </Avatar>
      );

      const img = screen.getByRole('img');
      expect(img).toHaveAttribute('src', 'https://api.dicebear.com/7.x/avataaars/svg?seed=John');
    });

    it('handles relative paths', () => {
      render(
        <Avatar>
          <AvatarImage src="/images/avatar.jpg" alt="Local avatar" />
          <AvatarFallback>LA</AvatarFallback>
        </Avatar>
      );

      expect(screen.getByRole('img')).toHaveAttribute('src', '/images/avatar.jpg');
    });
  });

  describe('Styling Variants', () => {
    it('renders square avatar variant', () => {
      const { container } = render(
        <Avatar className="rounded-md">
          <AvatarImage src="test.jpg" />
          <AvatarFallback className="rounded-md">SQ</AvatarFallback>
        </Avatar>
      );

      const avatar = container.firstChild;
      expect(avatar).toHaveClass('rounded-md');
      expect(avatar).not.toHaveClass('rounded-full');
    });

    it('renders different sizes', () => {
      const sizes = {
        sm: 'h-8 w-8',
        md: 'h-10 w-10',
        lg: 'h-12 w-12',
        xl: 'h-16 w-16'
      };

      const { rerender } = render(
        <Avatar className={sizes.sm}>
          <AvatarFallback>SM</AvatarFallback>
        </Avatar>
      );

      let avatar = screen.getByText('SM').parentElement?.parentElement;
      expect(avatar).toHaveClass('h-8 w-8');

      rerender(
        <Avatar className={sizes.xl}>
          <AvatarFallback>XL</AvatarFallback>
        </Avatar>
      );

      avatar = screen.getByText('XL').parentElement?.parentElement;
      expect(avatar).toHaveClass('h-16 w-16');
    });

    it('renders with custom colors', () => {
      render(
        <Avatar>
          <AvatarFallback className="bg-blue-500 text-white">
            BL
          </AvatarFallback>
        </Avatar>
      );

      const fallback = screen.getByText('BL');
      expect(fallback).toHaveClass('bg-blue-500 text-white');
    });
  });

  describe('Error Handling', () => {
    it('handles missing src gracefully', () => {
      render(
        <Avatar>
          <AvatarImage src="" alt="Empty source" />
          <AvatarFallback>ES</AvatarFallback>
        </Avatar>
      );

      // Should show fallback for empty src
      expect(screen.getByText('ES')).toBeInTheDocument();
    });

    it('handles network errors', async () => {
      const consoleError = jest.spyOn(console, 'error').mockImplementation();
      
      render(
        <Avatar>
          <AvatarImage 
            src="https://invalid-domain-12345.com/avatar.jpg" 
            alt="Network error test"
          />
          <AvatarFallback>NE</AvatarFallback>
        </Avatar>
      );

      // Simulate network error
      const img = screen.getByRole('img');
      img.dispatchEvent(new Event('error'));

      await waitFor(() => {
        expect(screen.getByText('NE')).toBeInTheDocument();
      });

      consoleError.mockRestore();
    });
  });

  describe('Dynamic Updates', () => {
    it('updates image source dynamically', () => {
      const { rerender } = render(
        <Avatar>
          <AvatarImage src="avatar1.jpg" alt="First avatar" />
          <AvatarFallback>AV</AvatarFallback>
        </Avatar>
      );

      expect(screen.getByRole('img')).toHaveAttribute('src', 'avatar1.jpg');

      rerender(
        <Avatar>
          <AvatarImage src="avatar2.jpg" alt="Second avatar" />
          <AvatarFallback>AV</AvatarFallback>
        </Avatar>
      );

      expect(screen.getByRole('img')).toHaveAttribute('src', 'avatar2.jpg');
    });

    it('updates fallback text dynamically', () => {
      const { rerender } = render(
        <Avatar>
          <AvatarFallback>AB</AvatarFallback>
        </Avatar>
      );

      expect(screen.getByText('AB')).toBeInTheDocument();

      rerender(
        <Avatar>
          <AvatarFallback>CD</AvatarFallback>
        </Avatar>
      );

      expect(screen.queryByText('AB')).not.toBeInTheDocument();
      expect(screen.getByText('CD')).toBeInTheDocument();
    });
  });
});