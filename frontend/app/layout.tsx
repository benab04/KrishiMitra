import './globals.css';
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'कृषिमित्र - KrishiMitra | AI Agricultural Assistant',
  description: 'Your intelligent agricultural assistant for crop diseases, pest control, weather insights, and market prices. Multimodal AI support with voice, text, and image inputs.',
  keywords: 'agriculture, farming, AI assistant, crop diseases, pest control, weather, market prices, KrishiMitra',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>{children}</body>
    </html>
  );
}