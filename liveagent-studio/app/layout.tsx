import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LiveAgent Studio · 直播智能工作台",
  description: "主播发现、直播拆解、直播复盘与视频编导的一体化桌面工作台。",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
