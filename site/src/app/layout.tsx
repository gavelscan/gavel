import type { Metadata } from "next";
import { Newsreader, Instrument_Sans, JetBrains_Mono } from "next/font/google";
import Cursor from "@/components/Cursor";
import Nav from "@/components/Nav";
import "./globals.css";

/* Display: a reading serif with real character — the register of a written
   record, deliberately against the grotesk every crypto site reaches for.
   Body: Instrument Sans, quiet and modern. Data: JetBrains Mono, because
   every figure on this site comes off a chain and should look like it. */
const newsreader = Newsreader({
  variable: "--font-newsreader",
  subsets: ["latin"],
  weight: ["300", "400", "500"],
  style: ["normal", "italic"],
  display: "swap",
});

const instrument = Instrument_Sans({
  variable: "--font-instrument",
  subsets: ["latin"],
  display: "swap",
});

const mono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://gavelscan.xyz"),
  title: "GAVEL",
  description:
    "Every launch auction on Robinhood Chain, read before the money moves. One verdict per launch: PASS, FLAG or FAIL.",
  icons: { icon: "/brand/favicon.ico" },
  openGraph: {
    title: "GAVEL",
    description:
      "Every launch auction on Robinhood Chain, read before the money moves.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${newsreader.variable} ${instrument.variable} ${mono.variable} h-full`}
    >
      <body className="min-h-full">
        <Cursor />
        <Nav />
        {children}
      </body>
    </html>
  );
}
