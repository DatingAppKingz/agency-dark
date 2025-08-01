import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Grid,
  Card,
  CardMedia,
  CardContent,
  CardActions,
  Typography,
  IconButton,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
  Alert,
  Tabs,
  Tab,
  Breadcrumbs,
  Link,
  Menu,
  Checkbox,
  Tooltip,
  LinearProgress,
  Paper,
  InputAdornment,
  Fab
} from '@mui/material';
import {
  CloudUpload as UploadIcon,
  Delete as DeleteIcon,
  Download as DownloadIcon,
  Share as ShareIcon,
  Edit as EditIcon,
  MoreVert as MoreIcon,
  Folder as FolderIcon,
  Image as ImageIcon,
  VideoLibrary as VideoIcon,
  AudioFile as AudioIcon,
  Description as DocumentIcon,
  Search as SearchIcon,
  FilterList as FilterIcon,
  CreateNewFolder as CreateFolderIcon,
  ArrowBack as BackIcon,
  Visibility as ViewIcon,
  CheckBox as SelectAllIcon,
  CheckBoxOutlineBlank as DeselectIcon
} from '@mui/icons-material';
import { useDropzone } from 'react-dropzone';
import { useSnackbar } from 'notistack';
import { useMediaService } from '../../hooks/useMediaService';
import { MediaUploadDialog } from './MediaUploadDialog';
import { MediaDetailDialog } from './MediaDetailDialog';
import { MediaShareDialog } from './MediaShareDialog';
import { FolderCreateDialog } from './FolderCreateDialog';
import { 
  Media, 
  MediaFolder, 
  MediaType, 
  MediaVisibility,
  MediaSearchParams 
} from '../../types/media';

interface MediaLibraryProps {
  agencyId: string;
  modelId?: string;
  onMediaSelect?: (media: Media) => void;
  selectionMode?: boolean;
  maxSelection?: number;
}

export const MediaLibrary: React.FC<MediaLibraryProps> = ({
  agencyId,
  modelId,
  onMediaSelect,
  selectionMode = false,
  maxSelection = 1
}) => {
  const { enqueueSnackbar } = useSnackbar();
  const mediaService = useMediaService();
  
  // State
  const [mediaItems, setMediaItems] = useState<Media[]>([]);
  const [folders, setFolders] = useState<MediaFolder[]>([]);
  const [currentFolder, setCurrentFolder] = useState<string | null>(null);
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  
  // Dialogs
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [shareDialogOpen, setShareDialogOpen] = useState(false);
  const [folderDialogOpen, setFolderDialogOpen] = useState(false);
  const [selectedMedia, setSelectedMedia] = useState<Media | null>(null);
  
  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [mediaTypeFilter, setMediaTypeFilter] = useState<MediaType | ''>('');
  const [visibilityFilter, setVisibilityFilter] = useState<MediaVisibility | ''>('');
  const [activeTab, setActiveTab] = useState(0);
  
  // Context menu
  const [contextMenu, setContextMenu] = useState<{
    mouseX: number;
    mouseY: number;
    media: Media;
  } | null>(null);
  
  // Pagination
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const limit = 20;
  
  // Load media
  const loadMedia = useCallback(async (reset = false) => {
    try {
      setLoading(true);
      
      const params: MediaSearchParams = {
        folder_id: currentFolder || undefined,
        media_type: mediaTypeFilter || undefined,
        visibility: visibilityFilter || undefined,
        search: searchQuery || undefined,
        limit,
        offset: reset ? 0 : page * limit
      };
      
      const response = await mediaService.listMedia(params);
      
      if (reset) {
        setMediaItems(response.items);
        setPage(0);
      } else {
        setMediaItems(prev => [...prev, ...response.items]);
      }
      
      setHasMore(response.has_more);
    } catch (error) {
      enqueueSnackbar('Failed to load media', { variant: 'error' });
    } finally {
      setLoading(false);
    }
  }, [currentFolder, mediaTypeFilter, visibilityFilter, searchQuery, page]);
  
  // Load folders
  const loadFolders = useCallback(async () => {
    try {
      const folderList = await mediaService.listFolders(currentFolder);
      setFolders(folderList);
    } catch (error) {
      enqueueSnackbar('Failed to load folders', { variant: 'error' });
    }
  }, [currentFolder]);
  
  // Initial load
  useEffect(() => {
    loadMedia(true);
    loadFolders();
  }, [currentFolder, mediaTypeFilter, visibilityFilter, searchQuery]);
  
  // File drop handler
  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    setUploadDialogOpen(true);
    // Upload dialog will handle the actual upload
  }, []);
  
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    noClick: true
  });
  
  // Selection handlers
  const handleItemClick = (media: Media, event: React.MouseEvent) => {
    if (event.ctrlKey || event.metaKey || selectionMode) {
      // Multi-select
      const newSelected = new Set(selectedItems);
      if (newSelected.has(media.id)) {
        newSelected.delete(media.id);
      } else {
        if (maxSelection && newSelected.size >= maxSelection) {
          enqueueSnackbar(`Maximum ${maxSelection} items can be selected`, { 
            variant: 'warning' 
          });
          return;
        }
        newSelected.add(media.id);
      }
      setSelectedItems(newSelected);
      
      if (onMediaSelect && selectionMode) {
        const selectedMedia = mediaItems.filter(m => newSelected.has(m.id));
        onMediaSelect(selectedMedia[0]); // For single selection mode
      }
    } else {
      // Single click - show details
      setSelectedMedia(media);
      setDetailDialogOpen(true);
    }
  };
  
  // Context menu
  const handleContextMenu = (event: React.MouseEvent, media: Media) => {
    event.preventDefault();
    setContextMenu({
      mouseX: event.clientX - 2,
      mouseY: event.clientY - 4,
      media
    });
  };
  
  const handleCloseContextMenu = () => {
    setContextMenu(null);
  };
  
  // Bulk operations
  const handleBulkDelete = async () => {
    if (selectedItems.size === 0) return;
    
    if (!window.confirm(`Delete ${selectedItems.size} items?`)) return;
    
    try {
      await mediaService.bulkOperation({
        media_ids: Array.from(selectedItems),
        action: 'delete',
        data: { permanent: false }
      });
      
      enqueueSnackbar('Items deleted successfully', { variant: 'success' });
      setSelectedItems(new Set());
      loadMedia(true);
    } catch (error) {
      enqueueSnackbar('Failed to delete items', { variant: 'error' });
    }
  };
  
  // Get media icon
  const getMediaIcon = (type: MediaType) => {
    switch (type) {
      case MediaType.IMAGE:
        return <ImageIcon />;
      case MediaType.VIDEO:
        return <VideoIcon />;
      case MediaType.AUDIO:
        return <AudioIcon />;
      case MediaType.DOCUMENT:
        return <DocumentIcon />;
      default:
        return <DocumentIcon />;
    }
  };
  
  // Format file size
  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  };
  
  return (
    <Box {...getRootProps()} sx={{ height: '100%', position: 'relative' }}>
      <input {...getInputProps()} />
      
      {/* Header */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={6}>
            <Box display="flex" alignItems="center" gap={2}>
              <Typography variant="h5">Media Library</Typography>
              {selectedItems.size > 0 && (
                <Chip 
                  label={`${selectedItems.size} selected`}
                  color="primary"
                  onDelete={() => setSelectedItems(new Set())}
                />
              )}
            </Box>
          </Grid>
          
          <Grid item xs={12} md={6}>
            <Box display="flex" gap={1} justifyContent="flex-end">
              <Button
                variant="contained"
                startIcon={<UploadIcon />}
                onClick={() => setUploadDialogOpen(true)}
              >
                Upload
              </Button>
              
              <Button
                startIcon={<CreateFolderIcon />}
                onClick={() => setFolderDialogOpen(true)}
              >
                New Folder
              </Button>
              
              {selectedItems.size > 0 && (
                <>
                  <IconButton 
                    color="error"
                    onClick={handleBulkDelete}
                  >
                    <DeleteIcon />
                  </IconButton>
                  
                  <IconButton
                    onClick={() => {
                      const allSelected = mediaItems.every(m => 
                        selectedItems.has(m.id)
                      );
                      if (allSelected) {
                        setSelectedItems(new Set());
                      } else {
                        setSelectedItems(new Set(mediaItems.map(m => m.id)));
                      }
                    }}
                  >
                    {selectedItems.size === mediaItems.length ? 
                      <DeselectIcon /> : <SelectAllIcon />
                    }
                  </IconButton>
                </>
              )}
            </Box>
          </Grid>
        </Grid>
        
        {/* Filters */}
        <Box mt={2}>
          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                size="small"
                placeholder="Search media..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon />
                    </InputAdornment>
                  )
                }}
              />
            </Grid>
            
            <Grid item xs={12} md={3}>
              <FormControl fullWidth size="small">
                <InputLabel>Type</InputLabel>
                <Select
                  value={mediaTypeFilter}
                  onChange={(e) => setMediaTypeFilter(e.target.value as MediaType)}
                  label="Type"
                >
                  <MenuItem value="">All Types</MenuItem>
                  <MenuItem value={MediaType.IMAGE}>Images</MenuItem>
                  <MenuItem value={MediaType.VIDEO}>Videos</MenuItem>
                  <MenuItem value={MediaType.AUDIO}>Audio</MenuItem>
                  <MenuItem value={MediaType.DOCUMENT}>Documents</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12} md={3}>
              <FormControl fullWidth size="small">
                <InputLabel>Visibility</InputLabel>
                <Select
                  value={visibilityFilter}
                  onChange={(e) => setVisibilityFilter(e.target.value as MediaVisibility)}
                  label="Visibility"
                >
                  <MenuItem value="">All</MenuItem>
                  <MenuItem value={MediaVisibility.PRIVATE}>Private</MenuItem>
                  <MenuItem value={MediaVisibility.AGENCY}>Agency</MenuItem>
                  <MenuItem value={MediaVisibility.MODEL}>Model</MenuItem>
                  <MenuItem value={MediaVisibility.PUBLIC}>Public</MenuItem>
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </Box>
      </Paper>
      
      {/* Breadcrumbs */}
      {currentFolder && (
        <Breadcrumbs sx={{ mb: 2 }}>
          <Link
            component="button"
            variant="body1"
            onClick={() => setCurrentFolder(null)}
            underline="hover"
          >
            Media Library
          </Link>
          {/* Add folder path here */}
          <Typography color="text.primary">Current Folder</Typography>
        </Breadcrumbs>
      )}
      
      {/* Content */}
      <Box sx={{ position: 'relative', minHeight: 400 }}>
        {isDragActive && (
          <Box
            sx={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: 'rgba(0, 0, 0, 0.5)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 10,
              borderRadius: 2,
              border: '2px dashed',
              borderColor: 'primary.main'
            }}
          >
            <Typography variant="h6" color="white">
              Drop files here to upload
            </Typography>
          </Box>
        )}
        
        {loading && mediaItems.length === 0 ? (
          <Box display="flex" justifyContent="center" p={4}>
            <CircularProgress />
          </Box>
        ) : mediaItems.length === 0 ? (
          <Box textAlign="center" p={4}>
            <Typography variant="h6" color="text.secondary" gutterBottom>
              No media files found
            </Typography>
            <Button
              variant="contained"
              startIcon={<UploadIcon />}
              onClick={() => setUploadDialogOpen(true)}
              sx={{ mt: 2 }}
            >
              Upload First File
            </Button>
          </Box>
        ) : (
          <>
            {/* Folders */}
            {folders.length > 0 && (
              <Grid container spacing={2} sx={{ mb: 3 }}>
                {folders.map((folder) => (
                  <Grid item xs={6} sm={4} md={3} lg={2} key={folder.id}>
                    <Card
                      sx={{ 
                        cursor: 'pointer',
                        '&:hover': { boxShadow: 3 }
                      }}
                      onClick={() => setCurrentFolder(folder.id)}
                    >
                      <CardContent sx={{ textAlign: 'center' }}>
                        <FolderIcon sx={{ fontSize: 48, color: folder.color }} />
                        <Typography variant="body2" noWrap>
                          {folder.name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {folder.media_count} items
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            )}
            
            {/* Media Grid */}
            <Grid container spacing={2}>
              {mediaItems.map((media) => (
                <Grid item xs={6} sm={4} md={3} lg={2} key={media.id}>
                  <Card
                    sx={{ 
                      cursor: 'pointer',
                      border: selectedItems.has(media.id) ? 2 : 0,
                      borderColor: 'primary.main',
                      '&:hover': { boxShadow: 3 }
                    }}
                    onClick={(e) => handleItemClick(media, e)}
                    onContextMenu={(e) => handleContextMenu(e, media)}
                  >
                    {media.media_type === MediaType.IMAGE && media.thumbnail_url ? (
                      <CardMedia
                        component="img"
                        height="140"
                        image={media.thumbnail_url}
                        alt={media.title || media.original_filename}
                      />
                    ) : (
                      <Box
                        sx={{
                          height: 140,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          backgroundColor: 'grey.100'
                        }}
                      >
                        {getMediaIcon(media.media_type)}
                      </Box>
                    )}
                    
                    <CardContent sx={{ p: 1 }}>
                      <Typography variant="body2" noWrap>
                        {media.title || media.original_filename}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {formatFileSize(media.file_size)}
                      </Typography>
                    </CardContent>
                    
                    {selectionMode && (
                      <Box sx={{ position: 'absolute', top: 8, left: 8 }}>
                        <Checkbox
                          checked={selectedItems.has(media.id)}
                          size="small"
                          sx={{ 
                            backgroundColor: 'rgba(255, 255, 255, 0.8)',
                            '&:hover': {
                              backgroundColor: 'rgba(255, 255, 255, 0.9)'
                            }
                          }}
                        />
                      </Box>
                    )}
                  </Card>
                </Grid>
              ))}
            </Grid>
            
            {/* Load more */}
            {hasMore && (
              <Box display="flex" justifyContent="center" mt={3}>
                <Button
                  onClick={() => {
                    setPage(page + 1);
                    loadMedia();
                  }}
                  disabled={loading}
                >
                  {loading ? <CircularProgress size={24} /> : 'Load More'}
                </Button>
              </Box>
            )}
          </>
        )}
      </Box>
      
      {/* Upload progress */}
      {uploadProgress !== null && (
        <Box sx={{ position: 'fixed', bottom: 20, right: 20, width: 300 }}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="body2" gutterBottom>
              Uploading...
            </Typography>
            <LinearProgress variant="determinate" value={uploadProgress} />
          </Paper>
        </Box>
      )}
      
      {/* Context Menu */}
      <Menu
        open={contextMenu !== null}
        onClose={handleCloseContextMenu}
        anchorReference="anchorPosition"
        anchorPosition={
          contextMenu !== null
            ? { top: contextMenu.mouseY, left: contextMenu.mouseX }
            : undefined
        }
      >
        <MenuItem onClick={() => {
          if (contextMenu) {
            setSelectedMedia(contextMenu.media);
            setDetailDialogOpen(true);
          }
          handleCloseContextMenu();
        }}>
          <ViewIcon sx={{ mr: 1 }} /> View Details
        </MenuItem>
        
        <MenuItem onClick={() => {
          if (contextMenu) {
            setSelectedMedia(contextMenu.media);
            setShareDialogOpen(true);
          }
          handleCloseContextMenu();
        }}>
          <ShareIcon sx={{ mr: 1 }} /> Share
        </MenuItem>
        
        <MenuItem onClick={() => {
          if (contextMenu) {
            // Download logic
            window.open(`/api/v1/media/download/${contextMenu.media.id}`, '_blank');
          }
          handleCloseContextMenu();
        }}>
          <DownloadIcon sx={{ mr: 1 }} /> Download
        </MenuItem>
        
        <MenuItem onClick={() => {
          if (contextMenu) {
            // Edit logic
          }
          handleCloseContextMenu();
        }}>
          <EditIcon sx={{ mr: 1 }} /> Edit
        </MenuItem>
        
        <MenuItem onClick={async () => {
          if (contextMenu) {
            if (window.confirm('Delete this file?')) {
              try {
                await mediaService.deleteMedia(contextMenu.media.id);
                enqueueSnackbar('File deleted', { variant: 'success' });
                loadMedia(true);
              } catch (error) {
                enqueueSnackbar('Failed to delete file', { variant: 'error' });
              }
            }
          }
          handleCloseContextMenu();
        }} sx={{ color: 'error.main' }}>
          <DeleteIcon sx={{ mr: 1 }} /> Delete
        </MenuItem>
      </Menu>
      
      {/* Dialogs */}
      <MediaUploadDialog
        open={uploadDialogOpen}
        onClose={() => setUploadDialogOpen(false)}
        folderId={currentFolder}
        onUploadComplete={() => {
          loadMedia(true);
          setUploadDialogOpen(false);
        }}
        onProgress={setUploadProgress}
      />
      
      {selectedMedia && (
        <>
          <MediaDetailDialog
            open={detailDialogOpen}
            onClose={() => setDetailDialogOpen(false)}
            media={selectedMedia}
            onUpdate={() => loadMedia(true)}
          />
          
          <MediaShareDialog
            open={shareDialogOpen}
            onClose={() => setShareDialogOpen(false)}
            media={selectedMedia}
          />
        </>
      )}
      
      <FolderCreateDialog
        open={folderDialogOpen}
        onClose={() => setFolderDialogOpen(false)}
        parentId={currentFolder}
        onFolderCreated={() => {
          loadFolders();
          setFolderDialogOpen(false);
        }}
      />
    </Box>
  );
};