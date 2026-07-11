/// <reference types="vite/client" />

interface Window {
  desktop?: {
    exportPdf(filename: string): Promise<boolean>
  }
}
