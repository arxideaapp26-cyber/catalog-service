import type { ReactNode } from "react";
import Script from "next/script";

import { TelegramBridge } from "./telegram";

export const metadata = {
  title: "Каталог",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body>
        {children}
        <Script src="https://telegram.org/js/telegram-web-app.js" strategy="beforeInteractive" />
        <TelegramBridge />
      </body>
    </html>
  );
}
