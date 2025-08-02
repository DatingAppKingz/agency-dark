import React from 'react';
import { render, screen, waitFor, fireEvent } from '@/tests/utils/enhanced-test-utils';
import userEvent from '@testing-library/user-event';
import { server } from '@/tests/utils/test-server';
import { rest } from 'msw';
import { MediaLibrary } from '@/components/media_library/MediaLibrary';
import { createMockFile } from '@/tests/utils/mock-factories';

describe('Media Upload Integration', () => {
  beforeEach(() => {
    localStorage.setItem('auth_token', 'valid-token');
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('Media Library', () => {
    it('displays media library with existing files', async () => {
      render(<MediaLibrary agencyId="agency-1" />);

      // Wait for media to load
      await waitFor(() => {
        expect(screen.getByText('test-image.jpg')).toBeInTheDocument();
      });

      // Check file details are displayed
      expect(screen.getByText('1.00 MB')).toBeInTheDocument();
    });

    it('opens upload dialog when upload button is clicked', async () => {
      const user = userEvent.setup();
      
      render(<MediaLibrary agencyId="agency-1" />);

      const uploadButton = await screen.findByRole('button', { name: /upload/i });
      await user.click(uploadButton);

      // Upload dialog should be visible
      expect(screen.getByText('Upload Media')).toBeInTheDocument();
      expect(screen.getByText(/drag & drop files here/i)).toBeInTheDocument();
    });
  });

  describe('File Upload', () => {
    it('uploads single file successfully', async () => {
      const user = userEvent.setup();
      
      render(<MediaLibrary agencyId="agency-1" />);

      // Open upload dialog
      const uploadButton = await screen.findByRole('button', { name: /upload/i });
      await user.click(uploadButton);

      // Create a mock file
      const file = createMockFile('new-image.jpg', 'image/jpeg', 2048000);

      // Find the file input
      const input = screen.getByLabelText(/drag & drop files here/i).parentElement?.querySelector('input[type="file"]');
      
      // Upload the file
      if (input) {
        await user.upload(input as HTMLInputElement, file);
      }

      // Check file appears in upload list
      await waitFor(() => {
        expect(screen.getByText('new-image.jpg')).toBeInTheDocument();
        expect(screen.getByText('2.0 MB')).toBeInTheDocument();
      });

      // Check upload progress
      expect(screen.getByRole('progressbar')).toBeInTheDocument();

      // Wait for upload to complete
      await waitFor(() => {
        expect(screen.getByTestId('CheckCircleIcon')).toBeInTheDocument();
      }, { timeout: 5000 });
    });

    it('handles multiple file upload', async () => {
      const user = userEvent.setup();
      
      render(<MediaLibrary agencyId="agency-1" />);

      const uploadButton = await screen.findByRole('button', { name: /upload/i });
      await user.click(uploadButton);

      // Create multiple mock files
      const files = [
        createMockFile('image1.jpg', 'image/jpeg', 1024000),
        createMockFile('image2.png', 'image/png', 2048000),
        createMockFile('document.pdf', 'application/pdf', 512000),
      ];

      const input = screen.getByLabelText(/drag & drop files here/i).parentElement?.querySelector('input[type="file"]');
      
      if (input) {
        await user.upload(input as HTMLInputElement, files);
      }

      // All files should be listed
      await waitFor(() => {
        expect(screen.getByText('image1.jpg')).toBeInTheDocument();
        expect(screen.getByText('image2.png')).toBeInTheDocument();
        expect(screen.getByText('document.pdf')).toBeInTheDocument();
      });
    });

    it('validates file size limits', async () => {
      const user = userEvent.setup();
      
      render(<MediaLibrary agencyId="agency-1" />);

      const uploadButton = await screen.findByRole('button', { name: /upload/i });
      await user.click(uploadButton);

      // Create a file that's too large (over 100MB)
      const largeFile = createMockFile('huge-file.jpg', 'image/jpeg', 150 * 1024 * 1024);

      const input = screen.getByLabelText(/drag & drop files here/i).parentElement?.querySelector('input[type="file"]');
      
      if (input) {
        await user.upload(input as HTMLInputElement, largeFile);
      }

      // Should show error message
      await waitFor(() => {
        expect(screen.getByText(/file too large/i)).toBeInTheDocument();
      });
    });

    it('handles upload errors gracefully', async () => {
      const user = userEvent.setup();

      server.use(
        rest.post('http://localhost:8000/api/v1/media/upload', (req, res, ctx) => {
          return res(
            ctx.status(500),
            ctx.json({ detail: 'Upload failed' })
          );
        })
      );

      render(<MediaLibrary agencyId="agency-1" />);

      const uploadButton = await screen.findByRole('button', { name: /upload/i });
      await user.click(uploadButton);

      const file = createMockFile('error-file.jpg', 'image/jpeg', 1024000);
      const input = screen.getByLabelText(/drag & drop files here/i).parentElement?.querySelector('input[type="file"]');
      
      if (input) {
        await user.upload(input as HTMLInputElement, file);
      }

      // Should show error message
      await waitFor(() => {
        expect(screen.getByText(/upload failed/i)).toBeInTheDocument();
      });
    });
  });

  describe('Drag and Drop', () => {
    it('handles file drop', async () => {
      render(<MediaLibrary agencyId="agency-1" />);

      const dropZone = await screen.findByText('Media Library').closest('div');
      const file = createMockFile('dropped-file.jpg', 'image/jpeg', 1024000);

      // Simulate drag enter
      fireEvent.dragEnter(dropZone!, {
        dataTransfer: {
          files: [file],
          types: ['Files'],
        },
      });

      // Should show drop indicator
      await waitFor(() => {
        expect(screen.getByText(/drop files here to upload/i)).toBeInTheDocument();
      });

      // Simulate drop
      fireEvent.drop(dropZone!, {
        dataTransfer: {
          files: [file],
          types: ['Files'],
        },
      });

      // Upload dialog should open
      await waitFor(() => {
        expect(screen.getByText('Upload Media')).toBeInTheDocument();
      });
    });
  });

  describe('File Management', () => {
    it('deletes file with confirmation', async () => {
      const user = userEvent.setup();
      
      render(<MediaLibrary agencyId="agency-1" />);

      // Wait for media to load
      await waitFor(() => {
        expect(screen.getByText('test-image.jpg')).toBeInTheDocument();
      });

      // Right-click on media item to open context menu
      const mediaItem = screen.getByText('test-image.jpg').closest('[role="img"]') || screen.getByText('test-image.jpg').closest('div');
      
      if (mediaItem) {
        fireEvent.contextMenu(mediaItem);
      }

      // Click delete option
      const deleteOption = await screen.findByText('Delete');
      await user.click(deleteOption);

      // Confirm deletion
      window.confirm = jest.fn(() => true);

      // File should be removed
      await waitFor(() => {
        expect(screen.queryByText('test-image.jpg')).not.toBeInTheDocument();
      });
    });

    it('shows media details on click', async () => {
      const user = userEvent.setup();
      
      render(<MediaLibrary agencyId="agency-1" />);

      // Wait for media to load
      await waitFor(() => {
        expect(screen.getByText('test-image.jpg')).toBeInTheDocument();
      });

      // Click on media item
      const mediaItem = screen.getByText('test-image.jpg').closest('div');
      if (mediaItem) {
        await user.click(mediaItem);
      }

      // Detail dialog should open
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
        expect(screen.getByText(/type: image\/jpeg/i)).toBeInTheDocument();
        expect(screen.getByText(/size: 1.00 MB/i)).toBeInTheDocument();
      });
    });

    it('supports bulk selection and deletion', async () => {
      const user = userEvent.setup();

      server.use(
        rest.get('http://localhost:8000/api/v1/media', (req, res, ctx) => {
          return res(
            ctx.json({
              items: [
                {
                  id: '1',
                  filename: 'image1.jpg',
                  original_filename: 'image1.jpg',
                  file_path: '/media/image1.jpg',
                  file_size: 1024000,
                  mime_type: 'image/jpeg',
                  media_type: 'image',
                  status: 'ready',
                  tags: [],
                  visibility: 'private',
                  agency_id: 'agency-1',
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                },
                {
                  id: '2',
                  filename: 'image2.jpg',
                  original_filename: 'image2.jpg',
                  file_path: '/media/image2.jpg',
                  file_size: 2048000,
                  mime_type: 'image/jpeg',
                  media_type: 'image',
                  status: 'ready',
                  tags: [],
                  visibility: 'private',
                  agency_id: 'agency-1',
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                },
              ],
              total: 2,
              has_more: false,
            })
          );
        })
      );

      render(<MediaLibrary agencyId="agency-1" />);

      // Wait for media to load
      await waitFor(() => {
        expect(screen.getByText('image1.jpg')).toBeInTheDocument();
        expect(screen.getByText('image2.jpg')).toBeInTheDocument();
      });

      // Select multiple items (Ctrl+Click)
      const item1 = screen.getByText('image1.jpg').closest('div');
      const item2 = screen.getByText('image2.jpg').closest('div');
      
      if (item1 && item2) {
        await user.click(item1, { ctrlKey: true });
        await user.click(item2, { ctrlKey: true });
      }

      // Should show selection count
      expect(screen.getByText('2 selected')).toBeInTheDocument();

      // Delete button should be visible
      const deleteButton = screen.getByRole('button', { name: /delete/i });
      await user.click(deleteButton);

      // Confirm bulk deletion
      window.confirm = jest.fn(() => true);

      // Items should be deleted
      await waitFor(() => {
        expect(screen.getByText(/items deleted successfully/i)).toBeInTheDocument();
      });
    });
  });

  describe('Search and Filter', () => {
    it('filters media by type', async () => {
      const user = userEvent.setup();
      
      render(<MediaLibrary agencyId="agency-1" />);

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByText('test-image.jpg')).toBeInTheDocument();
      });

      // Open type filter
      const typeFilter = screen.getByLabelText('Type');
      await user.click(typeFilter);

      // Select images only
      const imageOption = screen.getByRole('option', { name: /images/i });
      await user.click(imageOption);

      // Should trigger new request with filter
      await waitFor(() => {
        // Verify filtered results
        expect(screen.getByText('test-image.jpg')).toBeInTheDocument();
      });
    });

    it('searches media by name', async () => {
      const user = userEvent.setup();
      
      render(<MediaLibrary agencyId="agency-1" />);

      const searchInput = screen.getByPlaceholderText(/search media/i);
      await user.type(searchInput, 'test');

      // Should trigger search after debounce
      await waitFor(() => {
        expect(screen.getByText('test-image.jpg')).toBeInTheDocument();
      }, { timeout: 1000 });
    });
  });
});