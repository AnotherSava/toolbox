#Requires AutoHotkey v2.0

#SingleInstance Force
SetTitleMatchMode(2)  ; Partial title match

targetTitle := "Run - build123d-models"  ; Replace with actual partial title
targetClass := "YourClass"          ; Optional: from Window Spy

; F1: Hide from taskbar
F1::{
    targetWin := WinGetID(targetTitle (targetClass ? " ahk_class " targetClass : ""))
    if (targetWin) {
        WinHide(targetTitle (targetClass ? " ahk_class " targetClass : ""))
        WinSetExStyle("+0x80", targetWin)  ; Add WS_EX_TOOLWINDOW
        WinShow(targetWin)
        WinActivate(targetWin)
    }
}

; F2: Restore taskbar button
F2::{
    targetWin := WinGetID(targetTitle (targetClass ? " ahk_class " targetClass : ""))
    if (targetWin) {
        WinHide(targetWin)
        WinSetExStyle("-0x80", targetWin)  ; Remove WS_EX_TOOLWINDOW
        WinShow(targetWin)
        WinActivate(targetWin)
    }
}
