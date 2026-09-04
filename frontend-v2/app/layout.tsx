import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";
import { AuthBootstrap } from "@/components/auth-bootstrap";

export const metadata: Metadata = { title: "EVA — Your bilingual AI", description: "English–Kinyarwanda conversational intelligence" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><Providers><AuthBootstrap>{children}</AuthBootstrap></Providers></body></html>;
}
