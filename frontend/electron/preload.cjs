const { contextBridge, ipcRenderer } = require("electron")

contextBridge.exposeInMainWorld("desktop", {
  exportPdf: (filename) => ipcRenderer.invoke("export-pdf", filename),
  getSettings: () => ipcRenderer.invoke("desktop-settings"),
  setLaunchAtStartup: (enabled) =>
    ipcRenderer.invoke("set-launch-at-startup", enabled),
  setCloseBehavior: (behavior) =>
    ipcRenderer.invoke("set-close-behavior", behavior),
  openDataFolder: (dbPath) => ipcRenderer.invoke("open-data-folder", dbPath),
})
