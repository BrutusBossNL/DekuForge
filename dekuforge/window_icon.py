"""Assign the brand icon to the native Windows frame owned by Tk."""

import ctypes
from ctypes import wintypes


def install(window, path):
    """Retain both HICONs for the window lifetime and verify WM_GETICON."""
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user.GetAncestor.restype = wintypes.HWND
    user.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                               ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user.LoadImageW.restype = wintypes.HANDLE
    user.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t]
    user.SendMessageW.restype = ctypes.c_ssize_t
    user.DestroyIcon.argtypes = [wintypes.HANDLE]
    user.DestroyIcon.restype = wintypes.BOOL
    handles = []
    for small, metric in ((True, 49), (False, 11)):
        size = user.GetSystemMetrics(metric)
        handle = user.LoadImageW(None, str(path), 1, size, size, 0x10)
        if not handle:
            for _, loaded in handles:
                user.DestroyIcon(loaded)
            raise ctypes.WinError(ctypes.get_last_error())
        handles.append((0 if small else 1, handle))

    def apply(event=None):
        if event is not None and event.widget is not window:
            return
        frame = user.GetAncestor(window.winfo_id(), 2)
        if not frame:
            raise ctypes.WinError(ctypes.get_last_error())
        for kind, handle in handles:
            user.SendMessageW(frame, 0x80, kind, handle)  # WM_SETICON
        window._native_icon_verified = all(
            user.SendMessageW(frame, 0x7F, kind, 0) == handle for kind, handle in handles)
        if not window._native_icon_verified:
            raise RuntimeError("Windows did not retain the DekuForge window icons")

    def release(event):
        if event.widget is window:
            window.after_cancel(idle_job)
            for _, handle in handles:
                user.DestroyIcon(handle)

    window._native_icon_handles = handles
    window.bind("<Map>", apply, add="+")
    window.bind("<Destroy>", release, add="+")
    idle_job = window.after_idle(apply)
