import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";
import { AuthBootstrap } from "@/components/auth-bootstrap";

export const metadata: Metadata = {
  title: "EVA — Your bilingual AI",
  description: "English–Kinyarwanda conversational intelligence",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "EVA",
  },
  formatDetection: { telephone: false },
};
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#17211d",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <AuthBootstrap>{children}</AuthBootstrap>
        </Providers>
      </body>
    </html>
  );
}
