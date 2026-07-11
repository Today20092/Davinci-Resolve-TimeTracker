/// <reference types="vite/client" />

interface Window {
  desktop?: {
    exportPdf(filename: string): Promise<boolean>
    getSettings(): Promise<{ launchAtStartup: boolean }>
    setLaunchAtStartup(enabled: boolean): Promise<boolean>
    setCloseBehavior(behavior: "tray" | "quit"): Promise<void>
    openDataFolder(dbPath: string): Promise<boolean>
  }
}
