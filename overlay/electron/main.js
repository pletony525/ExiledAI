import { app, BrowserWindow, globalShortcut } from 'electron'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

let mainWindow = null

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 420,
    height: 560,
    alwaysOnTop: true,
    frame: false,
    transparent: true,
    skipTaskbar: true,
    resizable: false,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
    },
  })
  mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
}

function toggleWindow() {
  if (!mainWindow) return
  if (mainWindow.isVisible()) {
    mainWindow.hide()
  } else {
    mainWindow.show()
  }
}

app.whenReady().then(() => {
  createWindow()
  const registered = globalShortcut.register('CommandOrControl+Shift+Space', toggleWindow)
  if (!registered) {
    console.error('Failed to register global hotkey CommandOrControl+Shift+Space - it may be in use by another application.')
  }
})

app.on('will-quit', () => {
  globalShortcut.unregisterAll()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
