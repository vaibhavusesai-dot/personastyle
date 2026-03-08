import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PersonaStyle — AI Style DNA",
  description: "Discover your face shape, body type, and seasonal colour palette — then get hyper-personalised hairstyle and fashion recommendations.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
