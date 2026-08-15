const { contextBridge, ipcRenderer } = require("electron")

contextBridge.exposeInMainWorld("desktop", {
  exportPdf: (filename) => ipcRenderer.invoke("export-pdf", filename),
  copySupportReport: (report) =>
    ipcRenderer.invoke("copy-support-report", report),
  getSupportReport: () => ipcRenderer.invoke("get-support-report"),
  saveSupportReport: (report) =>
    ipcRenderer.invoke("save-support-report", report),
  getSettings: () => ipcRenderer.invoke("desktop-settings"),
  setLaunchAtStartup: (enabled) =>
    ipcRenderer.invoke("set-launch-at-startup", enabled),
  setCloseBehavior: (behavior) =>
    ipcRenderer.invoke("set-close-behavior", behavior),
  openDataFolder: (dbPath) => ipcRenderer.invoke("open-data-folder", dbPath),
})
