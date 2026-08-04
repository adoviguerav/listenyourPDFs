import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "listenyourPDFs",
  description: "Tus PDFs, escuchables — tutor de audio self-hosted",
  manifest: "/manifest.json",
  appleWebApp: { capable: true, statusBarStyle: "default", title: "listenyourPDFs" },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f7f5" },
    { media: "(prefers-color-scheme: dark)", color: "#141817" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>
        {children}
        <script
          dangerouslySetInnerHTML={{
            __html:
              "if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js')}",
          }}
        />
      </body>
    </html>
  );
}
