import { useState, useEffect, useRef } from 'react';
import Image from 'next/image';
import { Box, Skeleton } from '@mui/material';
import { BrokenImage } from '@mui/icons-material';

interface OptimizedImageProps {
  src: string;
  alt: string;
  width?: number;
  height?: number;
  fill?: boolean;
  priority?: boolean;
  quality?: number;
  placeholder?: 'blur' | 'empty';
  blurDataURL?: string;
  onLoad?: () => void;
  onError?: () => void;
  className?: string;
  style?: React.CSSProperties;
  sizes?: string;
  objectFit?: 'contain' | 'cover' | 'fill' | 'none' | 'scale-down';
  objectPosition?: string;
  lazy?: boolean;
}

export const OptimizedImage = ({
  src,
  alt,
  width,
  height,
  fill = false,
  priority = false,
  quality = 75,
  placeholder,
  blurDataURL,
  onLoad,
  onError,
  className,
  style,
  sizes,
  objectFit = 'cover',
  objectPosition = 'center',
  lazy = true,
}: OptimizedImageProps) => {
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [isInView, setIsInView] = useState(!lazy);
  const imgRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!lazy || !imgRef.current) {
      setIsInView(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setIsInView(true);
            observer.disconnect();
          }
        });
      },
      {
        rootMargin: '50px',
      }
    );

    observer.observe(imgRef.current);

    return () => {
      observer.disconnect();
    };
  }, [lazy]);

  const handleLoad = () => {
    setIsLoading(false);
    onLoad?.();
  };

  const handleError = () => {
    setIsLoading(false);
    setHasError(true);
    onError?.();
  };

  // Generate responsive sizes if not provided
  const generateSizes = () => {
    if (sizes) return sizes;
    if (fill) return '100vw';
    if (width) {
      return `(max-width: ${width}px) 100vw, ${width}px`;
    }
    return '100vw';
  };

  // Fallback for non-Next.js environments or development
  const renderFallbackImage = () => (
    <img
      src={src}
      alt={alt}
      width={width}
      height={height}
      onLoad={handleLoad}
      onError={handleError}
      className={className}
      style={{
        width: fill ? '100%' : width,
        height: fill ? '100%' : height,
        objectFit,
        objectPosition,
        ...style,
      }}
      loading={lazy ? 'lazy' : 'eager'}
    />
  );

  if (hasError) {
    return (
      <Box
        sx={{
          width: fill ? '100%' : width,
          height: fill ? '100%' : height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: 'grey.100',
          ...style,
        }}
        className={className}
      >
        <BrokenImage sx={{ color: 'grey.400', fontSize: 40 }} />
      </Box>
    );
  }

  const imageContent = (
    <>
      {isLoading && (
        <Skeleton
          variant="rectangular"
          width={fill ? '100%' : width}
          height={fill ? '100%' : height}
          sx={{ position: 'absolute', top: 0, left: 0 }}
        />
      )}
      
      {isInView && (
        <>
          {typeof window !== 'undefined' && window.location.hostname === 'localhost' ? (
            renderFallbackImage()
          ) : (
            <Image
              src={src}
              alt={alt}
              width={!fill ? width : undefined}
              height={!fill ? height : undefined}
              fill={fill}
              priority={priority}
              quality={quality}
              placeholder={placeholder}
              blurDataURL={blurDataURL}
              onLoad={handleLoad}
              onError={handleError}
              className={className}
              style={{
                objectFit,
                objectPosition,
                ...style,
              }}
              sizes={generateSizes()}
            />
          )}
        </>
      )}
    </>
  );

  return (
    <Box
      ref={imgRef}
      sx={{
        position: 'relative',
        width: fill ? '100%' : width,
        height: fill ? '100%' : height,
        overflow: 'hidden',
      }}
    >
      {imageContent}
    </Box>
  );
};

// Preload critical images
export const preloadImage = (src: string) => {
  if (typeof window === 'undefined') return;
  
  const link = document.createElement('link');
  link.rel = 'preload';
  link.as = 'image';
  link.href = src;
  document.head.appendChild(link);
};

// Generate blur data URL for placeholder
export const generateBlurDataURL = async (src: string): Promise<string> => {
  if (typeof window === 'undefined') return '';
  
  return new Promise((resolve) => {
    const img = new window.Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      
      // Create a small canvas for blur
      canvas.width = 20;
      canvas.height = 20;
      
      if (ctx) {
        ctx.filter = 'blur(10px)';
        ctx.drawImage(img, 0, 0, 20, 20);
        resolve(canvas.toDataURL());
      } else {
        resolve('');
      }
    };
    img.onerror = () => resolve('');
    img.src = src;
  });
};