# Branding assets

`logo.png` is the owner-provided wordmark for the README and launcher sidebar.
`icon.png` is the owner-provided application emblem for the window, taskbar and
native executable. Keep both masters unchanged. Tk scales them at display time
and reads their PNG bytes explicitly. `launcher.ico` is the multi-size Windows packaging derivative generated from `icon.png` by
`tools/build_launcher.py`; it is also embedded in the native bootstrap. The PNG
master remains unchanged. Shared interface colors are in
`dekuforge/theme.py`: dark forest backgrounds, leaf green, forged gold and warm
ivory text. The native setup and uninstaller also embed the application icon;
check branding at each target size when packaging.

`background.png` is the owner-provided launcher backdrop. It fills the main
client area edge to edge with a centered crop and a 46% blend over forest green.
Its viewport stays fixed during page changes. Panels show aligned artwork at
15%; text and buttons have solid readable backings. Image transfers use direct
RGB pixels rather than compressing PNGs during every redraw.

Startup begins with a dark green gradient, reveals the background and fades it
to 46%. A single unfaded logo starts near the padded top at 135% of its sidebar
size, shrinks, then slides into the fixed navigation position. The sidebar and
three home action cards follow. Hover and keyboard focus highlight action cards.
`home-actions.png` is the owner-provided triptych; its derived `home-play.png`,
`home-update.png` and `home-build.png` supply the separate action cards.
Pillow enables this artwork; without it the launcher retains its plain theme.
