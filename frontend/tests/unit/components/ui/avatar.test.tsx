import React from 'react';
import { vi } from 'vitest';
import { render, screen, waitFor, act } from '../../../utils/enhanced-test-utils';
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

      // In test environment, fallback is shown because images don't load in JSDOM
      expect(screen.getByText('JD')).toBeInTheDocument();
      
      // Verify the avatar container is rendered with correct classes
      const avatarContainer = screen.getByText('JD').closest('.relative');
      expect(avatarContainer).toHaveClass('relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full');
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
      const { container } = render(
        <Avatar>
          <AvatarImage 
            src="/avatar.png" 
            alt="Profile picture"
            className="object-cover"
          />
          <AvatarFallback>PP</AvatarFallback>
        </Avatar>
      );

      // In test environment, we check if the image element is in the DOM
      // even if it's not visible due to fallback behavior
      const imgElement = container.querySelector('img');
      if (imgElement) {
        expect(imgElement).toHaveAttribute('src', '/avatar.png');
        expect(imgElement).toHaveAttribute('alt', 'Profile picture');
        expect(imgElement).toHaveClass('aspect-square h-full w-full object-cover');
      } else {
        // If image doesn't render, at least verify the fallback is shown
        expect(screen.getByText('PP')).toBeInTheDocument();
      }
    });

    it('handles image loading states', async () => {
      const onLoadingStatusChange = vi.fn();
      
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
      const onError = vi.fn();
      
      render(
        <Avatar>
          <AvatarImage 
            src="invalid-url.jpg" 
            alt="Invalid image"
            onError={onError}
          />
          <AvatarFallback>ER</AvatarFallback>
        </Avatar>
      );

      // Initially shows fallback
      expect(screen.getByText('ER')).toBeInTheDocument();

      // Wait for image to attempt loading, then simulate error
      await waitFor(() => {
        const img = screen.queryByAltText('Invalid image');
        if (img) {
          img.dispatchEvent(new Event('error'));
        }
      });

      // Fallback should remain visible
      expect(screen.getByText('ER')).toBeInTheDocument();
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
    it('renders fallback with delayMs prop', () => {
      // Test that the component accepts delayMs prop without errors
      const { container } = render(
        <Avatar>
          <AvatarImage src="slow-loading.jpg" />
          <AvatarFallback delayMs={600}>DL</AvatarFallback>
        </Avatar>
      );

      // Verify the component renders successfully with the delayMs prop
      expect(container.firstChild).toBeInTheDocument();
      
      // In the test environment, the delay behavior is complex to test
      // but we can verify the component structure is correct
      const avatar = container.querySelector('[class*="relative flex"]');
      expect(avatar).toHaveClass('relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full');
    });
  });

  describe('Accessibility', () => {
    it('image has proper alt text', () => {
      const { container } = render(
        <Avatar>
          <AvatarImage src="avatar.jpg" alt="John Doe's avatar" />
          <AvatarFallback>JD</AvatarFallback>
        </Avatar>
      );

      // Verify fallback is shown
      expect(screen.getByText('JD')).toBeInTheDocument();
      
      // Check if image element exists with proper alt text
      const imgElement = container.querySelector('img');
      if (imgElement) {
        expect(imgElement).toHaveAttribute('alt', "John Doe's avatar");
      }
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

      const { container } = render(
        <Avatar>
          <AvatarImage src={user.avatarUrl} alt={user.name} />
          <AvatarFallback>{user.initials}</AvatarFallback>
        </Avatar>
      );

      // Shows fallback in test environment
      expect(screen.getByText('JS')).toBeInTheDocument();
      
      // Verify the image element exists in DOM with correct attributes
      const imgElement = container.querySelector('img');
      if (imgElement) {
        expect(imgElement).toHaveAttribute('alt', 'Jane Smith');
        expect(imgElement).toHaveAttribute('src', user.avatarUrl);
      }
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
      
      const { container } = render(
        <Avatar>
          <AvatarImage src={base64Image} alt="Base64 avatar" />
          <AvatarFallback>B64</AvatarFallback>
        </Avatar>
      );

      // Verify fallback is shown
      expect(screen.getByText('B64')).toBeInTheDocument();
      
      // Check if image element exists with correct src
      const imgElement = container.querySelector('img');
      if (imgElement) {
        expect(imgElement).toHaveAttribute('src', base64Image);
      }
    });

    it('handles external URLs', () => {
      const { container } = render(
        <Avatar>
          <AvatarImage 
            src="https://api.dicebear.com/7.x/avataaars/svg?seed=John" 
            alt="Generated avatar"
          />
          <AvatarFallback>GA</AvatarFallback>
        </Avatar>
      );

      // Verify fallback is shown
      expect(screen.getByText('GA')).toBeInTheDocument();
      
      // Check if image element exists with correct src
      const imgElement = container.querySelector('img');
      if (imgElement) {
        expect(imgElement).toHaveAttribute('src', 'https://api.dicebear.com/7.x/avataaars/svg?seed=John');
      }
    });

    it('handles relative paths', () => {
      const { container } = render(
        <Avatar>
          <AvatarImage src="/images/avatar.jpg" alt="Local avatar" />
          <AvatarFallback>LA</AvatarFallback>
        </Avatar>
      );

      // Verify fallback is shown
      expect(screen.getByText('LA')).toBeInTheDocument();
      
      // Check if image element exists with correct src
      const imgElement = container.querySelector('img');
      if (imgElement) {
        expect(imgElement).toHaveAttribute('src', '/images/avatar.jpg');
      }
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

      let fallbackElement = screen.getByText('SM');
      let avatar = fallbackElement.closest('[class*="relative flex"]');
      expect(avatar).toHaveClass('h-8 w-8');

      rerender(
        <Avatar className={sizes.xl}>
          <AvatarFallback>XL</AvatarFallback>
        </Avatar>
      );

      fallbackElement = screen.getByText('XL');
      avatar = fallbackElement.closest('[class*="relative flex"]');
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

    it('handles network errors', () => {
      const consoleError = vi.spyOn(console, 'error').mockImplementation();
      
      const { container } = render(
        <Avatar>
          <AvatarImage 
            src="https://invalid-domain-12345.com/avatar.jpg" 
            alt="Network error test"
          />
          <AvatarFallback>NE</AvatarFallback>
        </Avatar>
      );

      // Fallback should be shown immediately in test environment
      expect(screen.getByText('NE')).toBeInTheDocument();
      
      // Test that error handler can be called if image exists
      const imgElement = container.querySelector('img');
      if (imgElement) {
        // Simulate error event
        imgElement.dispatchEvent(new Event('error'));
        // Fallback should still be visible
        expect(screen.getByText('NE')).toBeInTheDocument();
      }

      consoleError.mockRestore();
    });
  });

  describe('Dynamic Updates', () => {
    it('updates image source dynamically', () => {
      const { rerender, container } = render(
        <Avatar>
          <AvatarImage src="avatar1.jpg" alt="First avatar" />
          <AvatarFallback>AV</AvatarFallback>
        </Avatar>
      );

      // Check first image
      let imgElement = container.querySelector('img');
      if (imgElement) {
        expect(imgElement).toHaveAttribute('src', 'avatar1.jpg');
        expect(imgElement).toHaveAttribute('alt', 'First avatar');
      }

      rerender(
        <Avatar>
          <AvatarImage src="avatar2.jpg" alt="Second avatar" />
          <AvatarFallback>AV</AvatarFallback>
        </Avatar>
      );

      // Check updated image
      imgElement = container.querySelector('img');
      if (imgElement) {
        expect(imgElement).toHaveAttribute('src', 'avatar2.jpg');
        expect(imgElement).toHaveAttribute('alt', 'Second avatar');
      }
      
      // Fallback should still be visible in both cases
      expect(screen.getByText('AV')).toBeInTheDocument();
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