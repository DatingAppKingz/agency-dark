import fs from 'fs';

interface SitemapUrl {
  loc: string;
  lastmod?: string;
  changefreq?: 'always' | 'hourly' | 'daily' | 'weekly' | 'monthly' | 'yearly' | 'never';
  priority?: number;
}

export class SitemapGenerator {
  private baseUrl: string;
  private urls: SitemapUrl[] = [];

  constructor(baseUrl: string = 'https://app.agencydark.com') {
    this.baseUrl = baseUrl.replace(/\/$/, ''); // Remove trailing slash
  }

  addUrl(url: SitemapUrl): void {
    this.urls.push({
      ...url,
      loc: url.loc.startsWith('http') ? url.loc : `${this.baseUrl}${url.loc}`,
      lastmod: url.lastmod || new Date().toISOString().split('T')[0],
    });
  }

  addUrls(urls: SitemapUrl[]): void {
    urls.forEach(url => this.addUrl(url));
  }

  generateXML(): string {
    const urlsXml = this.urls
      .map(url => `
  <url>
    <loc>${this.escapeXml(url.loc)}</loc>
    ${url.lastmod ? `<lastmod>${url.lastmod}</lastmod>` : ''}
    ${url.changefreq ? `<changefreq>${url.changefreq}</changefreq>` : ''}
    ${url.priority !== undefined ? `<priority>${url.priority}</priority>` : ''}
  </url>`)
      .join('');

    return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9
        http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd">${urlsXml}
</urlset>`;
  }

  async generateDynamicSitemap(): Promise<void> {
    // Add static pages
    this.addUrls([
      { loc: '/', changefreq: 'weekly', priority: 1.0 },
      { loc: '/auth/login', changefreq: 'monthly', priority: 0.8 },
      { loc: '/auth/register', changefreq: 'monthly', priority: 0.8 },
      { loc: '/auth/forgot-password', changefreq: 'monthly', priority: 0.6 },
      { loc: '/about', changefreq: 'monthly', priority: 0.7 },
      { loc: '/features', changefreq: 'monthly', priority: 0.7 },
      { loc: '/pricing', changefreq: 'weekly', priority: 0.8 },
      { loc: '/contact', changefreq: 'monthly', priority: 0.6 },
      { loc: '/privacy', changefreq: 'quarterly', priority: 0.5 },
      { loc: '/terms', changefreq: 'quarterly', priority: 0.5 },
    ]);

    // Add dynamic pages (e.g., public model profiles, blog posts)
    // This would typically fetch from your API
    // const publicModels = await fetchPublicModels();
    // publicModels.forEach(model => {
    //   this.addUrl({
    //     loc: `/models/${model.slug}`,
    //     lastmod: model.updatedAt,
    //     changefreq: 'weekly',
    //     priority: 0.7,
    //   });
    // });
  }

  writeToDisk(outputPath: string): void {
    const xml = this.generateXML();
    fs.writeFileSync(outputPath, xml, 'utf-8');
  }

  private escapeXml(str: string): string {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&apos;');
  }
}

// Generate sitemap index for multiple sitemaps
export class SitemapIndexGenerator {
  private baseUrl: string;
  private sitemaps: Array<{ loc: string; lastmod?: string }> = [];

  constructor(baseUrl: string = 'https://app.agencydark.com') {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  addSitemap(loc: string, lastmod?: string): void {
    this.sitemaps.push({
      loc: loc.startsWith('http') ? loc : `${this.baseUrl}${loc}`,
      lastmod: lastmod || new Date().toISOString().split('T')[0],
    });
  }

  generateXML(): string {
    const sitemapsXml = this.sitemaps
      .map(sitemap => `
  <sitemap>
    <loc>${sitemap.loc}</loc>
    ${sitemap.lastmod ? `<lastmod>${sitemap.lastmod}</lastmod>` : ''}
  </sitemap>`)
      .join('');

    return `<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${sitemapsXml}
</sitemapindex>`;
  }
}

// Next.js API route handler for dynamic sitemap
export async function generateSitemapResponse(): Promise<Response> {
  const generator = new SitemapGenerator();
  await generator.generateDynamicSitemap();
  const xml = generator.generateXML();

  return new Response(xml, {
    headers: {
      'Content-Type': 'application/xml',
      'Cache-Control': 'public, max-age=86400, s-maxage=86400',
    },
  });
}