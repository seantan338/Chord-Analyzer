import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { AudioFileProvider } from "@/components/audio-file-context";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Chord Analyzer",
  description: "Upload a song and get its key, tempo, chords and a printable chord sheet.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
        <AudioFileProvider>
          <header className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
            <div className="mx-auto flex h-14 max-w-6xl items-center px-4">
              <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
                <span
                  aria-hidden
                  className="flex h-7 w-7 items-center justify-center rounded-md bg-violet-600 text-sm font-bold text-white"
                >
                  ♪
                </span>
                Chord Analyzer
              </Link>
            </div>
          </header>
          <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>
        </AudioFileProvider>
      </body>
    </html>
  );
}
