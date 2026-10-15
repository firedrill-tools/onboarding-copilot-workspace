import type { Metadata } from "next";
import { Providers } from "./providers";
import "@copilotkit/react-core/v2/styles.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Acme Setup | Onboarding workspace",
  description: "Synthetic team setup with invitation approval and a Google ADK copilot",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body><Providers>{children}</Providers></body></html>;
}
