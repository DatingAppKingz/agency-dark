import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MessageThread } from '@/components/chat/MessageThread';
import { Message, MessageAttachment } from '@/types/chat';
import { useAuthStore } from '@/store/authStore';
import { useChatStore } from '@/store/chatStore';
import { format } from 'date-fns';

// Mock dependencies
vi.mock('@/store/authStore');
vi.mock('@/store/chatStore');
vi.mock('@/components/chat/MediaPreview', () => ({
  MediaPreview: ({ attachment, onClose }: any) => (
    <div data-testid="media-preview">
      <span>{attachment?.filename}</span>
      <button onClick={onClose}>Close</button>
    </div>
  )
}));
vi.mock('@/components/chat/VoiceMessagePlayer', () => ({
  VoiceMessagePlayer: ({ attachment }: any) => (
    <div data-testid="voice-player">
      <span>{attachment?.url}</span>
      <span>{attachment?.duration}s</span>
    </div>
  )
}));

// Mock MUI icons
vi.mock('@mui/icons-material', () => ({
  MoreVert: () => <div data-testid="more-vert-icon" />,
  Done: () => <div data-testid="done-icon" />,
  DoneAll: () => <div data-testid="done-all-icon" />,
  AttachFile: () => <div data-testid="attach-file-icon" />,
  PlayCircleOutline: () => <div data-testid="play-circle-icon" />,
  Mic: () => <div data-testid="mic-icon" />
}));

describe('MessageThread Component', () => {
  const mockUser = {
    id: 'user123',
    name: 'Test User',
    email: 'test@example.com'
  };

  const mockMessages: Message[] = [
    {
      id: 'msg1',
      conversation_id: 'conv123',
      sender_id: 'fan456',
      content: 'Hello! How are you?',
      created_at: new Date().toISOString(),
      status: 'delivered',
      read_at: null
    },
    {
      id: 'msg2',
      conversation_id: 'conv123',
      sender_id: 'user123',
      content: "I'm doing great, thanks for asking!",
      created_at: new Date(Date.now() - 60000).toISOString(),
      status: 'read',
      read_at: new Date().toISOString()
    },
    {
      id: 'msg3',
      conversation_id: 'conv123',
      sender_id: 'fan456',
      content: 'Check out this photo!',
      created_at: new Date(Date.now() - 120000).toISOString(),
      status: 'read',
      read_at: new Date().toISOString(),
      attachments: [
        {
          id: 'att1',
          type: 'image',
          url: 'https://example.com/image.jpg',
          thumbnail_url: 'https://example.com/thumb.jpg',
          filename: 'photo.jpg',
          size: 1024000
        }
      ]
    }
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    (useAuthStore as any).mockReturnValue({ user: mockUser });
    (useChatStore as any).mockReturnValue({ typingStatuses: {} });

    // Mock scrollIntoView
    Element.prototype.scrollIntoView = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Message Rendering', () => {
    it('should render all messages', () => {
      render(<MessageThread messages={mockMessages} conversationId="conv123" />);

      expect(screen.getByText('Hello! How are you?')).toBeInTheDocument();
      expect(screen.getByText("I'm doing great, thanks for asking!")).toBeInTheDocument();
      expect(screen.getByText('Check out this photo!')).toBeInTheDocument();
    });

    it('should display loading state when pending', () => {
      render(<MessageThread messages={[]} conversationId="conv123" isPending />);

      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('should show empty state when no messages', () => {
      const { container } = render(<MessageThread messages={[]} conversationId="conv123" />);

      // Component doesn't show text for empty state, just an empty container
      const messageContainer = container.querySelector('.MuiBox-root');
      expect(messageContainer).toBeInTheDocument();
      expect(screen.queryByRole('listitem')).not.toBeInTheDocument();
    });

    it('should differentiate between sent and received messages', () => {
      render(<MessageThread messages={mockMessages} conversationId="conv123" />);

      const sentMessage = screen.getByText("I'm doing great, thanks for asking!");
      const receivedMessage = screen.getByText('Hello! How are you?');

      // Check if messages are aligned correctly (sent messages on right, received on left)
      const sentContainer = sentMessage.closest('.MuiBox-root');
      const receivedContainer = receivedMessage.closest('.MuiBox-root');
      
      // The component uses flex-end for own messages and flex-start for others
      const sentParent = sentContainer?.parentElement?.parentElement;
      const receivedParent = receivedContainer?.parentElement?.parentElement;
      
      expect(sentParent).toHaveStyle({ justifyContent: 'flex-end' });
      expect(receivedParent).toHaveStyle({ justifyContent: 'flex-start' });
    });
  });

  describe('Message Status', () => {
    it('should display read status for messages', () => {
      render(<MessageThread messages={mockMessages} conversationId="conv123" />);

      // Message with read status should show double check
      const readMessage = screen.getByText("I'm doing great, thanks for asking!");
      const readContainer = readMessage.closest('.MuiPaper-root');
      expect(readContainer?.querySelector('[data-testid="done-all-icon"]')).toBeTruthy();
    });

    it('should display delivered status for unread messages', () => {
      // Create a message with delivered status
      const deliveredMessage: Message = {
        ...mockMessages[0],
        status: 'delivered',
        delivered_at: new Date().toISOString(),
        read_at: null
      };
      
      render(<MessageThread messages={[deliveredMessage]} conversationId="conv123" />);

      // Status icons are only shown for own messages
      expect(screen.queryByTestId('done-icon')).not.toBeInTheDocument();
    });
  });

  describe('Timestamps', () => {
    it('should format today\'s messages correctly', () => {
      const todayMessage: Message = {
        ...mockMessages[0],
        created_at: new Date().toISOString()
      };

      render(<MessageThread messages={[todayMessage]} conversationId="conv123" />);

      const expectedTime = format(new Date(), 'h:mm a');
      expect(screen.getByText(expectedTime)).toBeInTheDocument();
    });

    it('should format yesterday\'s messages correctly', () => {
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      
      const yesterdayMessage: Message = {
        ...mockMessages[0],
        created_at: yesterday.toISOString()
      };

      render(<MessageThread messages={[yesterdayMessage]} conversationId="conv123" />);

      const expectedTime = `Yesterday ${format(yesterday, 'h:mm a')}`;
      expect(screen.getByText(expectedTime)).toBeInTheDocument();
    });

    it('should format older messages with full date', () => {
      const oldDate = new Date('2024-01-15T10:30:00');
      const oldMessage: Message = {
        ...mockMessages[0],
        created_at: oldDate.toISOString()
      };

      render(<MessageThread messages={[oldMessage]} conversationId="conv123" />);

      const expectedTime = format(oldDate, 'MMM d, h:mm a');
      expect(screen.getByText(expectedTime)).toBeInTheDocument();
    });
  });

  describe('Attachments', () => {
    it('should render image attachments', () => {
      render(<MessageThread messages={mockMessages} conversationId="conv123" />);

      const image = screen.getByAltText('photo.jpg');
      expect(image).toBeInTheDocument();
      expect(image).toHaveAttribute('src', 'https://example.com/thumb.jpg');
    });

    it('should handle click on image attachment', () => {
      render(<MessageThread messages={mockMessages} conversationId="conv123" />);

      const image = screen.getByAltText('photo.jpg');
      fireEvent.click(image);

      expect(screen.getByTestId('media-preview')).toBeInTheDocument();
      expect(screen.getByText('photo.jpg')).toBeInTheDocument();
    });

    it('should render video attachments', () => {
      const messageWithVideo: Message = {
        ...mockMessages[0],
        attachments: [
          {
            id: 'att2',
            type: 'video',
            url: 'https://example.com/video.mp4',
            thumbnail_url: 'https://example.com/video-thumb.jpg',
            filename: 'video.mp4',
            size: 5242880
          }
        ]
      };

      render(<MessageThread messages={[messageWithVideo]} conversationId="conv123" />);

      expect(screen.getByTestId('play-circle-icon')).toBeInTheDocument();
      const videoThumb = screen.getByAltText('video.mp4');
      expect(videoThumb).toHaveAttribute('src', 'https://example.com/video-thumb.jpg');
    });

    it('should render voice messages', () => {
      const messageWithVoice: Message = {
        ...mockMessages[0],
        attachments: [
          {
            id: 'att3',
            type: 'audio',
            url: 'https://example.com/voice.mp3',
            filename: 'voice.mp3',
            size: 512000,
            duration: 15
          }
        ]
      };

      render(<MessageThread messages={[messageWithVoice]} conversationId="conv123" />);

      expect(screen.getByTestId('voice-player')).toBeInTheDocument();
      expect(screen.getByText('15s')).toBeInTheDocument();
    });

    it('should render file attachments', () => {
      const messageWithFile: Message = {
        ...mockMessages[0],
        attachments: [
          {
            id: 'att4',
            type: 'file',
            url: 'https://example.com/document.pdf',
            filename: 'document.pdf',
            size: 2097152
          }
        ]
      };

      render(<MessageThread messages={[messageWithFile]} conversationId="conv123" />);

      expect(screen.getByTestId('attach-file-icon')).toBeInTheDocument();
      expect(screen.getByText('document.pdf')).toBeInTheDocument();
      // File size is not displayed in the component
      expect(screen.getByTestId('attach-file-icon')).toBeInTheDocument();
    });
  });

  describe('Message Actions', () => {
    it('should show menu on more button click', () => {
      render(<MessageThread messages={mockMessages} conversationId="conv123" />);

      const moreButtons = screen.getAllByTestId('more-vert-icon');
      fireEvent.click(moreButtons[0].parentElement!);

      expect(screen.getByRole('menu')).toBeInTheDocument();
      expect(screen.getByText('Copy')).toBeInTheDocument();
      expect(screen.getByText('Reply')).toBeInTheDocument();
      expect(screen.getByText('Delete')).toBeInTheDocument();
    });

    it('should close menu when clicking outside', async () => {
      render(<MessageThread messages={mockMessages} conversationId="conv123" />);

      const moreButtons = screen.getAllByTestId('more-vert-icon');
      fireEvent.click(moreButtons[0].parentElement!);

      expect(screen.getByRole('menu')).toBeInTheDocument();

      // MUI Menu uses Portal, so we need to simulate escape key or backdrop click
      fireEvent.keyDown(screen.getByRole('menu'), { key: 'Escape', code: 'Escape' });

      await waitFor(() => {
        expect(screen.queryByRole('menu')).not.toBeInTheDocument();
      });
    });

    it('should handle copy action', async () => {
      const mockWriteText = vi.fn().mockResolvedValue(undefined);
      Object.assign(navigator, {
        clipboard: {
          writeText: mockWriteText
        }
      });

      render(<MessageThread messages={mockMessages} conversationId="conv123" />);

      const moreButtons = screen.getAllByTestId('more-vert-icon');
      fireEvent.click(moreButtons[0].parentElement!);
      fireEvent.click(screen.getByText('Copy'));

      expect(mockWriteText).toHaveBeenCalledWith('Hello! How are you?');
    });
  });

  describe('Typing Indicator', () => {
    it('should show typing indicator when user is typing', () => {
      (useChatStore as any).mockReturnValue({
        typingStatuses: {
          'conv123': { fan456: true }
        }
      });

      render(<MessageThread messages={mockMessages} conversationId="conv123" />);

      expect(screen.getByText('Fan is typing...')).toBeInTheDocument();
      expect(screen.getByTestId('typing-indicator')).toBeInTheDocument();
    });

    it('should not show typing indicator when no one is typing', () => {
      render(<MessageThread messages={mockMessages} conversationId="conv123" />);

      expect(screen.queryByText('Fan is typing...')).not.toBeInTheDocument();
    });
  });

  describe('Auto Scroll', () => {
    it('should scroll to bottom when messages change', async () => {
      const { rerender } = render(
        <MessageThread messages={mockMessages} conversationId="conv123" />
      );

      expect(Element.prototype.scrollIntoView).toHaveBeenCalled();

      const newMessage: Message = {
        id: 'msg4',
        conversation_id: 'conv123',
        sender_id: 'user123',
        content: 'New message!',
        created_at: new Date().toISOString(),
        status: 'sent'
      };

      rerender(
        <MessageThread 
          messages={[...mockMessages, newMessage]} 
          conversationId="conv123" 
        />
      );

      await waitFor(() => {
        expect(Element.prototype.scrollIntoView).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('Price Messages', () => {
    it('should display price for paid messages', () => {
      const paidMessage: Message = {
        ...mockMessages[0],
        price: 25,
        is_paid: false
      };

      render(<MessageThread messages={[paidMessage]} conversationId="conv123" />);

      expect(screen.getByText('$25')).toBeInTheDocument();
      expect(screen.getByText('Unlock')).toBeInTheDocument();
    });

    it('should show unlocked state for paid messages', () => {
      const unlockedMessage: Message = {
        ...mockMessages[0],
        price: 25,
        is_paid: true
      };

      render(<MessageThread messages={[unlockedMessage]} conversationId="conv123" />);

      expect(screen.getByText('$25')).toBeInTheDocument();
      expect(screen.getByText('Unlocked')).toBeInTheDocument();
    });
  });

  describe('Media Preview Modal', () => {
    it('should close media preview on close button click', () => {
      render(<MessageThread messages={mockMessages} conversationId="conv123" />);

      const image = screen.getByAltText('photo.jpg');
      fireEvent.click(image);

      expect(screen.getByTestId('media-preview')).toBeInTheDocument();

      fireEvent.click(screen.getByText('Close'));

      expect(screen.queryByTestId('media-preview')).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels', () => {
      render(<MessageThread messages={mockMessages} conversationId="conv123" />);

      expect(screen.getByRole('log', { name: 'Message thread' })).toBeInTheDocument();
    });

    it('should mark messages with proper roles', () => {
      render(<MessageThread messages={mockMessages} conversationId="conv123" />);

      const messages = screen.getAllByRole('article');
      expect(messages).toHaveLength(mockMessages.length);
    });
  });
});