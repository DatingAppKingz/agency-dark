import { useState, useCallback } from 'react';
import axios from 'axios';
import { 
  Media, 
  MediaFolder, 
  MediaShare,
  MediaVisibility,
  MediaSearchParams,
  MediaBulkOperation
} from '../types/media';

const API_BASE = '/api/v1/media';

export const useMediaService = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Upload file
  const uploadFile = useCallback(async (
    file: File,
    options: {
      folderId?: string;
      visibility?: MediaVisibility;
      tags?: string[];
      title?: string;
      description?: string;
      onProgress?: (progress: number) => void;
    } = {}
  ): Promise<Media> => {
    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      
      if (options.folderId) formData.append('folder_id', options.folderId);
      if (options.visibility) formData.append('visibility', options.visibility);
      if (options.tags) formData.append('tags', JSON.stringify(options.tags));
      if (options.title) formData.append('title', options.title);
      if (options.description) formData.append('description', options.description);

      const response = await axios.post<Media>(`${API_BASE}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total && options.onProgress) {
            const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            options.onProgress(progress);
          }
        },
      });

      return response.data;
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Upload failed';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  // Batch upload
  const batchUpload = useCallback(async (
    files: File[],
    options: {
      folderId?: string;
      visibility?: MediaVisibility;
    } = {}
  ): Promise<Media[]> => {
    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      files.forEach(file => formData.append('files', file));
      
      if (options.folderId) formData.append('folder_id', options.folderId);
      if (options.visibility) formData.append('visibility', options.visibility);

      const response = await axios.post<Media[]>(`${API_BASE}/upload/batch`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      return response.data;
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Batch upload failed';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  // List media
  const listMedia = useCallback(async (params: MediaSearchParams = {}) => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.get(`${API_BASE}/`, { params });
      return response.data;
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Failed to load media';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  // Get media details
  const getMedia = useCallback(async (mediaId: string): Promise<Media> => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.get<Media>(`${API_BASE}/${mediaId}`);
      return response.data;
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Failed to load media details';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  // Update media
  const updateMedia = useCallback(async (
    mediaId: string,
    updates: Partial<Media>
  ): Promise<Media> => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.put<Media>(`${API_BASE}/${mediaId}`, updates);
      return response.data;
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Failed to update media';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  // Delete media
  const deleteMedia = useCallback(async (
    mediaId: string,
    permanent: boolean = false
  ): Promise<void> => {
    setLoading(true);
    setError(null);

    try {
      await axios.delete(`${API_BASE}/${mediaId}`, {
        params: { permanent }
      });
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Failed to delete media';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  // Bulk operations
  const bulkOperation = useCallback(async (
    operation: MediaBulkOperation
  ): Promise<{ success_count: number; error_count: number; errors: any[] }> => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.post(`${API_BASE}/bulk`, operation);
      return response.data;
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Bulk operation failed';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  // Folder operations
  const listFolders = useCallback(async (parentId?: string | null): Promise<MediaFolder[]> => {
    setLoading(true);
    setError(null);

    try {
      const params = parentId !== undefined ? { parent_id: parentId } : {};
      const response = await axios.get<MediaFolder[]>(`${API_BASE}/folders`, { params });
      return response.data;
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Failed to load folders';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  const createFolder = useCallback(async (folder: {
    name: string;
    description?: string;
    parent_id?: string;
    color?: string;
    icon?: string;
  }): Promise<MediaFolder> => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.post<MediaFolder>(`${API_BASE}/folders`, folder);
      return response.data;
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Failed to create folder';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  const updateFolder = useCallback(async (
    folderId: string,
    updates: Partial<MediaFolder>
  ): Promise<MediaFolder> => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.put<MediaFolder>(`${API_BASE}/folders/${folderId}`, updates);
      return response.data;
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Failed to update folder';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  const deleteFolder = useCallback(async (
    folderId: string,
    moveContentsTo?: string
  ): Promise<void> => {
    setLoading(true);
    setError(null);

    try {
      const params = moveContentsTo ? { move_contents_to: moveContentsTo } : {};
      await axios.delete(`${API_BASE}/folders/${folderId}`, { params });
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Failed to delete folder';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  // Share operations
  const createShareLink = useCallback(async (share: {
    media_id: string;
    expires_at?: string;
    max_views?: number;
    password_protected?: boolean;
    password?: string;
    allow_download?: boolean;
    allow_embed?: boolean;
  }): Promise<MediaShare> => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.post<MediaShare>(`${API_BASE}/share`, share);
      return response.data;
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Failed to create share link';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  const getSharedMedia = useCallback(async (
    shareToken: string,
    password?: string
  ): Promise<{ media: Media; allow_download: boolean; allow_embed: boolean }> => {
    setLoading(true);
    setError(null);

    try {
      const params = password ? { password } : {};
      const response = await axios.get(`${API_BASE}/share/${shareToken}`, { params });
      return response.data;
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Failed to access shared media';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  // Download
  const getDownloadUrl = useCallback(async (mediaId: string): Promise<string> => {
    try {
      const response = await axios.get(`${API_BASE}/download/${mediaId}`);
      
      if (response.data.download_url) {
        return response.data.download_url;
      }
      
      // For streaming response, create blob URL
      const blob = new Blob([response.data]);
      return URL.createObjectURL(blob);
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Failed to get download URL';
      throw new Error(errorMessage);
    }
  }, []);

  // Storage quota
  const getStorageQuota = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.get(`${API_BASE}/quota`);
      return response.data;
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Failed to load storage quota';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    // State
    loading,
    error,
    
    // File operations
    uploadFile,
    batchUpload,
    listMedia,
    getMedia,
    updateMedia,
    deleteMedia,
    bulkOperation,
    
    // Folder operations
    listFolders,
    createFolder,
    updateFolder,
    deleteFolder,
    
    // Share operations
    createShareLink,
    getSharedMedia,
    
    // Download
    getDownloadUrl,
    
    // Storage
    getStorageQuota,
  };
};