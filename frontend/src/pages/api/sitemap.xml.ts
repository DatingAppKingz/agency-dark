import { NextApiRequest, NextApiResponse } from 'next';
import { generateSitemapResponse } from '@/utils/sitemap-generator';

export default async function handler(event: NextApiRequest, res: NextApiResponse) {
  try {
    const sitemapResponse = await generateSitemapResponse();
    const xml = await sitemapResponse.text();
    
    res.setHeader('Content-Type', 'application/xml');
    res.setHeader('Cache-Control', 'public, max-age=86400, s-maxage=86400');
    res.status(200).send(xml);
  } catch (error) {
    console.error('Error generating sitemap:', error);
    res.status(500).send('Error generating sitemap');
  }
}
