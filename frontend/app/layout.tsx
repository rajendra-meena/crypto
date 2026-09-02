import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

import { Header } from '../components/header/Header';
import { TradingProvider } from '../context/TradingContext';


const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Delta Algo Trading Terminal | Phase 1',
  description: 'Automated crypto algorithmic trading terminal and analysis engine',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-zinc-950 text-zinc-100 min-h-screen antialiased selection:bg-emerald-500/30`}>
        <TradingProvider>
          <Header />
          <main>{children}</main>
        </TradingProvider>
      </body>
    </html>
  );
}