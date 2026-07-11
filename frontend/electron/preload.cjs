const { contextBridge, ipcRenderer } = require("electron")

contextBridge.exposeInMainWorld("desktop", {
  exportPdf: (filename) => ipcRenderer.invoke("export-pdf", filename),
})
