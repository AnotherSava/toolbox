; Coordinate grid overlay. Shows one click-through window per monitor, sized to
; match that monitor, with a chroma-keyed grid image rendered on top. Doesn't
; touch the desktop wallpaper, so Windows Spotlight / Slideshow / Picture modes
; keep running underneath.
;
;   Ctrl+Shift+9  - cycle overlay state:
;                     hidden -> dark variant -> light variant -> hidden
;
; Two variants cover different wallpaper brightness:
;   - "dark"  : dark lines for light/bright wallpapers
;   - "light" : light lines for dark wallpapers
;
; Uses magenta (#FF00FF) as chroma key; WinSetTransColor makes those pixels
; fully transparent so only the grid lines and labels are visible.

#Requires AutoHotkey v2.0
#SingleInstance Force
Persistent

A_IconTip := "Overlay Grid"

fso := ComObject("Scripting.FileSystemObject")
scriptDir := A_ScriptDir
outputDir := fso.GetAbsolutePathName(scriptDir "\..\output")
projectRoot := fso.GetAbsolutePathName(scriptDir "\..\..\..")
venvExe := projectRoot "\.venv\Scripts\overlay-grid.exe"

OVERLAY_BG := "FF00FF"  ; magenta chroma-key color
WS_EX_TRANSPARENT := "E0x20"  ; click-through

; Cycle order matches the hotkey cycle: dark first, then light, then hidden.
VARIANTS := ["dark", "light"]

; state: 0 = hidden, 1..VARIANTS.Length = that variant visible
state := 0
overlaysByVariant := Map()

EnsureOverlayImage(variant, width, height) {
    global outputDir, venvExe, OVERLAY_BG
    filename := outputDir "\overlay_grid_" variant "_" width "x" height ".png"
    if FileExist(filename)
        return filename

    exe := FileExist(venvExe) ? venvExe : "overlay-grid"
    cmd := Format('"{1}" --width {2} --height {3} --variant {4} --background {5} "{6}"', exe, width, height, variant, OVERLAY_BG, filename)
    TrayTip("Generating " variant " " width "x" height " overlay...", "Overlay Grid", 1)
    RunWait(cmd, , "Hide")

    if !FileExist(filename)
        throw Error("Failed to generate overlay image: " filename)
    return filename
}

BuildOverlays(variant) {
    global OVERLAY_BG, WS_EX_TRANSPARENT
    guis := []
    loop MonitorGetCount() {
        MonitorGet(A_Index, &left, &top, &right, &bottom)
        width := right - left
        height := bottom - top
        imgPath := EnsureOverlayImage(variant, width, height)

        g := Gui("+AlwaysOnTop -Caption +ToolWindow -DPIScale +" WS_EX_TRANSPARENT, "Overlay Grid " variant)
        g.BackColor := OVERLAY_BG
        g.MarginX := 0
        g.MarginY := 0
        g.AddPicture("x0 y0 w" width " h" height, imgPath)
        g.Show("x" left " y" top " w" width " h" height " NoActivate Hide")
        WinSetTransColor(OVERLAY_BG, g.Hwnd)
        guis.Push(g)
    }
    return guis
}

HideAll() {
    global overlaysByVariant
    for _, guis in overlaysByVariant {
        for g in guis
            g.Hide()
    }
}

ShowVariant(variant) {
    global overlaysByVariant
    if !overlaysByVariant.Has(variant)
        overlaysByVariant[variant] := BuildOverlays(variant)
    for g in overlaysByVariant[variant]
        g.Show("NoActivate")
}

; Ctrl+Shift+9 -> cycle: hidden -> dark -> light -> hidden
^+9::{
    global state, VARIANTS
    state := Mod(state + 1, VARIANTS.Length + 1)
    HideAll()
    if (state > 0)
        ShowVariant(VARIANTS[state])
}
