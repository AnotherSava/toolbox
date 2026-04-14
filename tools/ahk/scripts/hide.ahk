; Hide windows from taskbar automatically when they open.
;
; To auto-run this script on Windows startup, run in PowerShell (replace
; <path-to-hide.ahk> with the absolute path to this file on your machine):
;
;   $WshShell = New-Object -ComObject WScript.Shell
;   $Shortcut = $WshShell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\hide.ahk.lnk")
;   $Shortcut.TargetPath = "<path-to-hide.ahk>"
;   $Shortcut.Save()

#Requires AutoHotkey v2.0

#SingleInstance Force
Persistent
SetTitleMatchMode(2)  ; Partial title match

; Windows to hide from taskbar (checked on window creation)
; Format: {title: "partial title", class: "class name", show: true/false}
windows := [
;    {title: "Run - build123d-models", class: "SunAwtFrame", show: true},
;    {title: "Terminal - build123d-models", class: "SunAwtFrame", show: true},
    {title: "f3d", class: "CASCADIA_HOSTING_WINDOW_CLASS", show: false}
]

; Process any existing windows on startup
for win in windows {
    HideFromTaskbar(win.title, win.class, win.show)
}

; Register shell hook to detect new windows
SHELLHOOK := DllCall("RegisterWindowMessage", "Str", "SHELLHOOK")
DllCall("RegisterShellHookWindow", "Ptr", A_ScriptHwnd)
OnMessage(SHELLHOOK, OnShellMessage)

OnShellMessage(wParam, lParam, msg, hwnd) {
    static HSHELL_WINDOWCREATED := 1
    if (wParam = HSHELL_WINDOWCREATED) {
        SetTimer(() => CheckNewWindow(lParam), -100)  ; Small delay for window to initialize
    }
}

CheckNewWindow(hwnd) {
    global windows
    for win in windows {
        try {
            winTitle := WinGetTitle(hwnd)
            winClass := WinGetClass(hwnd)
            if (InStr(winTitle, win.title) && winClass = win.class) {
                HideFromTaskbar(hwnd, "", win.show, true)
            }
        }
    }
}

HideFromTaskbar(targetTitle, targetClass := "", showAgain := true, isHwnd := false) {
    try {
        if (isHwnd) {
            targetWin := targetTitle  ; Already an hwnd
        } else {
            winSelector := targetTitle (targetClass ? " ahk_class " targetClass : "")
            targetWin := WinGetID(winSelector)
        }
        if (targetWin) {
            WinHide(targetWin)                   ; Temporarily hide so style change takes effect
            WinSetExStyle("+0x80", targetWin)    ; Add WS_EX_TOOLWINDOW - removes window from taskbar/Alt+Tab
            if (showAgain) {
                WinShow(targetWin)               ; Make window visible again (but now without taskbar button)
                WinActivate(targetWin)           ; Bring window to foreground
            }
        }
    }
}

OnExit(ExitFunc)
ExitFunc(reason, code) {
    DllCall("DeregisterShellHookWindow", "Ptr", A_ScriptHwnd)
}
