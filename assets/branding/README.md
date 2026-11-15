# Branding assets

`logo.png` is the owner-provided wordmark for the README and launcher sidebar.
`icon.png` is the owner-provided application emblem for the window, taskbar and
native executable. Keep both masters unchanged. Tk scales them at display time
and reads their PNG bytes explicitly. `launcher.ico` is the multi-size Windows packaging derivative generated from `icon.png` by
`tools/build_launcher.py`; it is also embedded in the native bootstrap. The PNG
master remains unchanged. Shared interface colors are in
`dekuforge/theme.py`: dark forest backgrounds, leaf green, forged gold and warm
ivory text. Future installer assets must be checked at their target size.

`background.png` is the owner-provided launcher backdrop. It fills the main
content area edge to edge with a centered crop and a 46% blend over forest green.
Panels show the same aligned artwork at 15%; buttons keep solid surfaces for
readability. Resizing is debounced and no animation runs.
Pillow enables this artwork; without it the launcher retains its plain theme.
