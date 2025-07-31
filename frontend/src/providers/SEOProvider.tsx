import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { StructuredData, organizationSchema, websiteSchema, softwareApplicationSchema } from '@/components/seo/StructuredData';

interface SEOProviderProps {
  children: React.ReactNode;
}

export const SEOProvider = ({ children }: SEOProviderProps) => {
  const location = useLocation();

  useEffect(() => {
    // Track page views with analytics (if configured)
    if (typeof window !== 'undefined' && window.gtag) {
      window.gtag('config', import.meta.env.VITE_PUBLIC_GA_ID || '', {
        page_path: location.pathname,
      });
    }
  }, [location]);

  // Add global structured data
  return (
    <>
      {/* Organization schema - appears on all pages */}
      <StructuredData type="Organization" data={organizationSchema} />
      
      {/* Website schema - appears on all pages */}
      <StructuredData type="WebSite" data={websiteSchema} />
      
      {/* Software Application schema - appears on all pages */}
      <StructuredData type="SoftwareApplication" data={softwareApplicationSchema} />
      
      {children}
    </>
  );
};

// Utility function to generate page-specific metadata
export const generateMetadata = (page: string) => {
  const metadata: Record<string, { title: string; description: string; keywords?: string[] }> = {
    home: {
      title: 'Agency Dark - OnlyFans Management Platform',
      description: 'Comprehensive platform for managing OnlyFans models, chatters, and agency operations with advanced analytics and financial tracking.',
      keywords: ['OnlyFans management', 'agency platform', 'model management', 'chatter system'],
    },
    models: {
      title: 'Model Management',
      description: 'Manage your OnlyFans models, track performance, and optimize content strategies.',
      keywords: ['model management', 'content creators', 'performance tracking'],
    },
    chat: {
      title: 'Chat Management',
      description: 'Efficient chat system for managing fan conversations across multiple models.',
      keywords: ['chat management', 'fan engagement', 'messaging system'],
    },
    analytics: {
      title: 'Analytics Dashboard',
      description: 'Comprehensive analytics for tracking revenue, engagement, and performance metrics.',
      keywords: ['analytics', 'revenue tracking', 'performance metrics'],
    },
    financial: {
      title: 'Financial Management',
      description: 'Track earnings, manage payouts, and monitor financial performance.',
      keywords: ['financial tracking', 'payout management', 'revenue analytics'],
    },
  };

  return metadata[page] || metadata.home;
};

// Google Analytics types
declare global {
  interface Window {
    gtag?: (command: string, targetId: string, config?: any) => void;
  }
}
