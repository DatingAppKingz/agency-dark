import React, { useState, useEffect, useRef, ImgHTMLAttributes } from 'react';
import { Box, Skeleton } from '@mui/material';

interface OptimizedImageProps extends ImgHTMLAttributes<HTMLImageElement> {
  src: string;
  alt: string;
  width?: number | string;
  height?: number | string;
  aspectRatio?: string;
  lazy?: boolean;
  placeholder?: 'blur' | 'skeleton' | 'none';
  blurDataURL?: string;
  onLoad?: () => void;
  onError?: () => void;
  quality?: number;
  priority?: boolean;
}

export const OptimizedImage: React.FC<OptimizedImageProps> = ({
  src,
  alt,
  width,
  height,
  aspectRatio = '16/9',
  lazy = true,
  placeholder = 'skeleton',
  blurDataURL,
  onLoad,
  onError,
  quality = 85,
  priority = false,
  className,
  style,
  ...rest
}) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [imageSrc, setImageSrc] = useState<string>('');
  const imgRef = useRef<HTMLImageElement>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);

  // CDN configuration
  const CDN_BASE_URL = process.env.REACT_APP_CDN_URL || '';
  const CDN_ENABLED = !!CDN_BASE_URL;
  
  // Generate optimized image URL with CDN support
  const getOptimizedUrl = (url: string, width?: number) => {
    // If URL is already absolute, check if it needs CDN
    const isAbsoluteUrl = url.startsWith('http://') || url.startsWith('https://');
    
    // Cloudflare/Cloudinary-style transformations
    if (CDN_ENABLED) {
      // Extract path from absolute URL or use as-is for relative URLs
      const imagePath = isAbsoluteUrl ? new URL(url).pathname : url;
      
      // Build transformation parameters
      const transforms = [];
      if (width && typeof width === 'number') {
        transforms.push(`w_${width}`);
      }
      transforms.push(`q_${quality}`);
      transforms.push('f_auto'); // Auto format selection
      transforms.push('c_limit'); // Limit dimensions to original
      
      // Cloudflare Images URL format
      if (CDN_BASE_URL.includes('cloudflare')) {
        return `${CDN_BASE_URL}/cdn-cgi/image/${transforms.join(',')}${imagePath}`;
      }
      
      // Cloudinary URL format
      if (CDN_BASE_URL.includes('cloudinary')) {
        const transformString = transforms.join(',');
        return `${CDN_BASE_URL}/image/upload/${transformString}${imagePath}`;
      }
      
      // Generic CDN with query params
      return `${CDN_BASE_URL}${imagePath}?${transforms.map(t => {
        const [key, value] = t.split('_');
        return `${key}=${value}`;
      }).join('&')}`;
    }
    
    // Fallback to simple query params
    if (width && typeof width === 'number') {
      return `${url}?w=${width}&q=${quality}`;
    }
    return url;
  };

  useEffect(() => {
    if (!lazy || priority) {
      // Load immediately
      setImageSrc(getOptimizedUrl(src, typeof width === 'number' ? width : undefined));
      return;
    }

    // Set up IntersectionObserver for lazy loading
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setImageSrc(getOptimizedUrl(src, typeof width === 'number' ? width : undefined));
            observer.unobserve(entry.target);
          }
        });
      },
      {
        rootMargin: '50px', // Start loading 50px before entering viewport
      }
    );

    observerRef.current = observer;

    if (imgRef.current) {
      observer.observe(imgRef.current);
    }

    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
    };
  }, [src, lazy, priority, width, quality, getOptimizedUrl]);

  const handleLoad = () => {
    setLoading(false);
    setError(false);
    onLoad?.();
  };

  const handleError = () => {
    setLoading(false);
    setError(true);
    onError?.();
  };

  // Preload priority images
  useEffect(() => {
    if (priority && src) {
      const link = document.createElement('link');
      link.rel = 'preload';
      link.as = 'image';
      link.href = getOptimizedUrl(src, typeof width === 'number' ? width : undefined);
      document.head.appendChild(link);
      
      return () => {
        document.head.removeChild(link);
      };
    }
  }, [src, priority, width, quality, getOptimizedUrl]);

  const containerStyle = {
    position: 'relative' as const,
    width,
    height,
    aspectRatio,
    overflow: 'hidden',
    ...style,
  };

  const imageStyle = {
    width: '100%',
    height: '100%',
    objectFit: 'cover' as const,
    opacity: loading ? 0 : 1,
    transition: 'opacity 0.3s ease-in-out',
  };

  return (
    <Box sx={containerStyle} className={className}>
      {/* Placeholder */}
      {loading && placeholder === 'skeleton' && (
        <Skeleton
          variant="rectangular"
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
          }}
        />
      )}
      
      {/* Blur placeholder */}
      {loading && placeholder === 'blur' && blurDataURL && (
        <img
          src={blurDataURL}
          alt=""
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            filter: 'blur(20px)',
            transform: 'scale(1.1)',
          }}
        />
      )}

      {/* Main image */}
      {!error && (
        <img
          ref={imgRef}
          src={imageSrc}
          alt={alt}
          onLoad={handleLoad}
          onError={handleError}
          loading={lazy && !priority ? 'lazy' : undefined}
          style={imageStyle}
          {...rest}
        />
      )}

      {/* Error state */}
      {error && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '100%',
            height: '100%',
            backgroundColor: 'grey.200',
            color: 'text.secondary',
          }}
        >
          Failed to load image
        </Box>
      )}
    </Box>
  );
};

// Hook for responsive images
export const useResponsiveImage = (
  baseSrc: string,
  sizes: { [breakpoint: string]: number }
) => {
  const [currentSrc, setCurrentSrc] = useState(baseSrc);

  useEffect(() => {
    const updateSrc = () => {
      const width = window.innerWidth;
      let selectedSize = 0;

      // Find the appropriate size based on viewport
      Object.entries(sizes).forEach(([breakpoint, size]) => {
        const bp = parseInt(breakpoint);
        if (width >= bp && size > selectedSize) {
          selectedSize = size;
        }
      });

      if (selectedSize > 0) {
        setCurrentSrc(`${baseSrc}?w=${selectedSize}`);
      }
    };

    updateSrc();
    window.addEventListener('resize', updateSrc);
    
    return () => window.removeEventListener('resize', updateSrc);
  }, [baseSrc, sizes]);

  return currentSrc;
};
