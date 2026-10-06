/// <reference types="vite/client" />

interface Window {
  desktop?: {
    exportPdf(filename: string): Promise<boolean>
    copySupportReport(report: string): Promise<boolean>
    getSupportReport(): Promise<string>
    saveSupportReport(report: string): Promise<boolean>
    openDataFolder(dbPath: string): Promise<boolean>
  }
}
