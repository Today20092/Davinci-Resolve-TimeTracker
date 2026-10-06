const { contextBridge, ipcRenderer } = require("electron")

contextBridge.exposeInMainWorld("desktop", {
  exportPdf: (filename) => ipcRenderer.invoke("export-pdf", filename),
  copySupportReport: (report) =>
    ipcRenderer.invoke("copy-support-report", report),
  getSupportReport: () => ipcRenderer.invoke("get-support-report"),
  saveSupportReport: (report) =>
    ipcRenderer.invoke("save-support-report", report),
  openDataFolder: (dbPath) => ipcRenderer.invoke("open-data-folder", dbPath),
})
