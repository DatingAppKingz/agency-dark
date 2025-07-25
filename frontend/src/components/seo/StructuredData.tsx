import Head from 'next/head';

interface StructuredDataProps {
  type: 'Organization' | 'WebSite' | 'WebPage' | 'BreadcrumbList' | 'FAQPage' | 'SoftwareApplication';
  data: Record<string, any>;
}

export const StructuredData = ({ type, data }: StructuredDataProps) => {
  const structuredData = {
    '@context': 'https://schema.org',
    '@type': type,
    ...data,
  };

  return (
    <Head>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
      />
    </Head>
  );
};

// Organization schema for the main website
export const organizationSchema = {
  name: 'Agency Dark',
  url: 'https://app.agencydark.com',
  logo: 'https://app.agencydark.com/logo.png',
  sameAs: [
    'https://twitter.com/agencydark',
    'https://linkedin.com/company/agencydark',
  ],
  contactPoint: {
    '@type': 'ContactPoint',
    telephone: '+1-555-123-4567',
    contactType: 'customer support',
    availableLanguage: ['English'],
  },
};

// WebSite schema with search action
export const websiteSchema = {
  name: 'Agency Dark',
  url: 'https://app.agencydark.com',
  potentialAction: {
    '@type': 'SearchAction',
    target: {
      '@type': 'EntryPoint',
      urlTemplate: 'https://app.agencydark.com/search?q={search_term_string}',
    },
    'query-input': 'required name=search_term_string',
  },
};

// Software Application schema
export const softwareApplicationSchema = {
  name: 'Agency Dark Platform',
  applicationCategory: 'BusinessApplication',
  operatingSystem: 'Web',
  offers: {
    '@type': 'Offer',
    price: '0',
    priceCurrency: 'USD',
  },
  aggregateRating: {
    '@type': 'AggregateRating',
    ratingValue: '4.8',
    reviewCount: '127',
  },
  features: [
    'Model Management',
    'Chat System',
    'Financial Tracking',
    'Analytics Dashboard',
    'Multi-tenant Support',
    'Real-time Communication',
  ],
};

// Helper function to generate breadcrumb schema
export const generateBreadcrumbSchema = (items: Array<{ name: string; url: string }>) => {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      item: item.url,
    })),
  };
};

// FAQ schema generator
export const generateFAQSchema = (faqs: Array<{ question: string; answer: string }>) => {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faqs.map(faq => ({
      '@type': 'Question',
      name: faq.question,
      acceptedAnswer: {
        '@type': 'Answer',
        text: faq.answer,
      },
    })),
  };
};