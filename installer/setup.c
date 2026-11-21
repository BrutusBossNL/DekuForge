// Standalone per-user setup. It embeds only the verified launcher package and
// installs it natively: no script host, no scripts written to the temp folder.
// Every step runs in a worker thread; only the UI thread touches the window.
#define UNICODE 1
#define _UNICODE 1
#define COBJMACROS 1
#include <windows.h>
#include <shellapi.h>
#include <shlobj.h>
#include <shobjidl.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#include "runtime.h"
#include "runtime_pin.h"
#include "setup_payload.h"

#define WM_SETUP_STAGE (WM_APP + 1)
#define WM_SETUP_DONE (WM_APP + 2)

static HINSTANCE app;
static HWND main_window, path_edit, status_text, install_button, browse_button, tools_check;
static HANDLE worker;
static int silent_mode, no_launch, skip_tools, no_shortcut;
static HBRUSH background;
static wchar_t install_root[DEKU_PATH], log_path[DEKU_PATH], failure[1024];

static const wchar_t *stages[] = {
    L"Checking the embedded DekuForge package...",
    L"Downloading and verifying the launcher runtime...",
    L"Installing and preparing tools. This can take several minutes...\nThe game is built later from your own files.",
    L"Adding DekuForge to the Start Menu...",
};

static void stage(int index) { PostMessageW(main_window, WM_SETUP_STAGE, (WPARAM)index, 0); }

static void log_line(HANDLE log, const char *text) {
    DWORD written;
    if (log != INVALID_HANDLE_VALUE) { WriteFile(log, text, (DWORD)strlen(text), &written, NULL); WriteFile(log, "\r\n", 2, &written, NULL); }
}

static int failed(HANDLE log, const wchar_t *what) {
    const char *reason = deku_error();
    wchar_t detail[600];
    if (!MultiByteToWideChar(CP_UTF8, 0, reason, -1, detail, 600)) wcscpy(detail, L"Unknown error");
    swprintf(failure, 1024, L"%ls\n%ls", what, detail);
    char line[2048] = "Setup failed: ";
    int used = (int)strlen(line);
    int length = WideCharToMultiByte(CP_UTF8, 0, what, -1, line + used, (int)sizeof line - used - 600, NULL, NULL);
    if (length > 0) snprintf(line + used + length - 1, sizeof line - (size_t)(used + length - 1), ": %s", reason);
    log_line(log, line);
    return 0;
}

static int write_payload(HANDLE log, const wchar_t *path) {
    HRSRC resource = FindResourceW(app, MAKEINTRESOURCEW(102), RT_RCDATA);
    HGLOBAL loaded = resource ? LoadResource(app, resource) : NULL;
    const void *data = loaded ? LockResource(loaded) : NULL;
    DWORD size = resource ? SizeofResource(app, resource) : 0;
    char digest[65];
    if (!data || !size || !deku_sha256_bytes(data, size, digest) || strcmp(digest, DEKU_SETUP_PAYLOAD_SHA256))
        return failed(log, L"The embedded package is damaged. Download DekuForge-Setup.exe again.");
    if (!deku_write_file(path, data, size, CREATE_NEW) || !deku_sha256_file(path, digest) || strcmp(digest, DEKU_SETUP_PAYLOAD_SHA256))
        return failed(log, L"Could not store the DekuForge package");
    log_line(log, "Verified embedded package SHA-256 " DEKU_SETUP_PAYLOAD_SHA256);
    return 1;
}

static int set_text(HKEY key, const wchar_t *name, const wchar_t *value) {
    return RegSetValueExW(key, name, 0, REG_SZ, (const BYTE *)value, (DWORD)((wcslen(value) + 1) * sizeof(wchar_t))) == ERROR_SUCCESS;
}

static int set_number(HKEY key, const wchar_t *name, DWORD value) {
    return RegSetValueExW(key, name, 0, REG_DWORD, (const BYTE *)&value, sizeof value) == ERROR_SUCCESS;
}

// Per-user Start Menu shortcut and Installed apps entry. The uninstaller removes both.
static int register_shell(const wchar_t *root) {
    wchar_t target[DEKU_PATH], uninstall[DEKU_PATH], link_path[DEKU_PATH];
    PWSTR programs = NULL;
    int ok = swprintf(target, DEKU_PATH, L"%ls\\DekuForge.exe", root) > 0
             && swprintf(uninstall, DEKU_PATH, L"\"%ls\\DekuForge-Uninstall.exe\"", root) > 0
             && SUCCEEDED(SHGetKnownFolderPath(&FOLDERID_Programs, 0, NULL, &programs))
             && swprintf(link_path, DEKU_PATH, L"%ls\\DekuForge Preview.lnk", programs) > 0;
    CoTaskMemFree(programs);
    IShellLinkW *link = NULL;
    IPersistFile *file = NULL;
    if (ok) ok = SUCCEEDED(CoCreateInstance(&CLSID_ShellLink, NULL, CLSCTX_INPROC_SERVER, &IID_IShellLinkW, (void **)&link))
                 && SUCCEEDED(IShellLinkW_SetPath(link, target)) && SUCCEEDED(IShellLinkW_SetWorkingDirectory(link, root))
                 && SUCCEEDED(IShellLinkW_SetIconLocation(link, target, 0)) && SUCCEEDED(IShellLinkW_SetDescription(link, L"DekuForge"))
                 && SUCCEEDED(IShellLinkW_QueryInterface(link, &IID_IPersistFile, (void **)&file))
                 && SUCCEEDED(IPersistFile_Save(file, link_path, TRUE));
    if (file) IPersistFile_Release(file);
    if (link) IShellLinkW_Release(link);
    HKEY key = NULL;
    if (ok) ok = RegCreateKeyExW(HKEY_CURRENT_USER, L"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\DekuForgePreview",
                                 0, NULL, 0, KEY_SET_VALUE, NULL, &key, NULL) == ERROR_SUCCESS;
    if (ok) ok = set_text(key, L"DisplayName", L"DekuForge") && set_text(key, L"DisplayVersion", DEKU_LAUNCHER_VERSION)
                 && set_text(key, L"InstallLocation", root) && set_text(key, L"UninstallString", uninstall)
                 && set_text(key, L"DisplayIcon", target) && set_text(key, L"Publisher", L"DekuForge contributors")
                 && set_number(key, L"NoModify", 1) && set_number(key, L"NoRepair", 1);
    if (key) RegCloseKey(key);
    return ok;
}

static int install(HANDLE log) {
    const wchar_t *root = install_root;
    wchar_t local[DEKU_PATH], work[DEKU_PATH], package[DEKU_PATH], application[DEKU_PATH],
            python[DEKU_PATH], script[DEKU_PATH], command[DEKU_PATH];
    stage(0);
    if (swprintf(local, DEKU_PATH, L"%ls\\local", root) < 0 || !deku_owned_path(root, local))
        return failed(log, L"Choose another installation folder");
    if (swprintf(work, DEKU_PATH, L"%ls\\setup-%lu-%llu", local, GetCurrentProcessId(), GetTickCount64()) < 0
        || !deku_owned_path(root, work) || !CreateDirectoryW(work, NULL))
        return failed(log, L"Could not create the setup workspace");
    int ok = swprintf(package, DEKU_PATH, L"%ls\\DekuForge-launcher.zip", work) > 0
             && swprintf(application, DEKU_PATH, L"%ls\\application", work) > 0 && write_payload(log, package);
    deku_listing_rules rules = {20000, 256ull * 1024 * 1024, NULL};
    if (ok && !deku_extract(package, application, &rules)) ok = failed(log, L"Could not unpack the DekuForge package");
    if (ok) {
        stage(1);
        log_line(log, "Preparing the pinned launcher runtime.");
        if (!deku_prepare_runtime(root)) ok = failed(log, L"Could not prepare the launcher runtime");
    }
    DWORD code = 1;
    if (ok) {
        stage(2);
        log_line(log, "Installing DekuForge application files.");
        ok = swprintf(python, DEKU_PATH, L"%ls\\python\\%ls\\python.exe", root, DEKU_PYTHON_ID) > 0
             && swprintf(script, DEKU_PATH, L"%ls\\tools\\install_package.py", application) > 0
             && swprintf(command, DEKU_PATH, L"\"%ls\" \"%ls\" --package \"%ls\" --root \"%ls\" --no-launch%ls",
                         python, script, package, root, skip_tools ? L" --skip-tools" : L"") > 0
             && deku_regular_file(python) && deku_regular_file(script);
        if (!ok || !deku_run(python, command, work, log != INVALID_HANDLE_VALUE ? log : NULL, &code)) ok = failed(log, L"Could not start the DekuForge installer");
        else if (code) ok = failed(log, L"DekuForge installation failed; see the setup log");
    }
    if (ok && !no_shortcut) {
        stage(3);
        if (!register_shell(root)) ok = failed(log, L"DekuForge is installed, but the Start Menu entry could not be created");
    }
    if (!deku_remove_tree(work)) log_line(log, "The setup workspace could not be removed completely.");
    if (ok) log_line(log, "DekuForge installation completed.");
    return ok;
}

static DWORD WINAPI install_worker(LPVOID unused) {
    (void)unused;
    CoInitializeEx(NULL, COINIT_APARTMENTTHREADED);
    HANDLE log = CreateFileW(log_path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    int ok = install(log);
    if (log != INVALID_HANDLE_VALUE) CloseHandle(log);
    CoUninitialize();
    PostMessageW(main_window, WM_SETUP_DONE, ok, 0);
    return ok ? 0 : 1;
}

// A drive root (C:\) or share root (\\server\share) is never an application folder.
static int volume_root(const wchar_t *path) {
    if (wcsncmp(path, L"\\\\", 2)) return wcslen(path) <= 3;
    int separators = 0;
    for (const wchar_t *p = path + 2; *p; ++p) separators += *p == L'\\';
    return separators < 2;
}

static int choose_root(HWND window) {
    wchar_t requested[DEKU_PATH], local[DEKU_PATH];
    GetWindowTextW(path_edit, requested, DEKU_PATH);
    const wchar_t *problem = NULL;
    int created = ERROR_SUCCESS;
    if (!requested[0] || !deku_full_path(requested, install_root)) problem = L"Choose an installation folder.";
    else if (volume_root(install_root)) problem = L"Choose an application folder, not a drive root.";
    else if ((created = SHCreateDirectoryExW(NULL, install_root, NULL)) != ERROR_SUCCESS && created != ERROR_ALREADY_EXISTS) problem = L"The installation folder could not be created.";
    else if (GetFileAttributesW(install_root) & FILE_ATTRIBUTE_REPARSE_POINT) problem = L"Choose a folder that is not a link.";
    else if (swprintf(local, DEKU_PATH, L"%ls\\local", install_root) < 0 || !deku_owned_path(install_root, local)
             || (!CreateDirectoryW(local, NULL) && GetLastError() != ERROR_ALREADY_EXISTS)) problem = L"The installation folder cannot be used.";
    else if (swprintf(log_path, DEKU_PATH, L"%ls\\setup.log", local) < 0) problem = L"The installation path is too long.";
    if (!problem) return 1;
    if (silent_mode) { DestroyWindow(window); PostQuitMessage(1); }
    else MessageBoxW(window, problem, L"DekuForge", MB_ICONERROR);
    return 0;
}

static void start_install(HWND window) {
    if (worker) return;
    skip_tools = skip_tools || SendMessageW(tools_check, BM_GETCHECK, 0, 0) != BST_CHECKED;
    if (!choose_root(window)) return;
    worker = CreateThread(NULL, 4 << 20, install_worker, NULL, 0, NULL);
    if (!worker) { MessageBoxW(window, L"Could not start setup.", L"DekuForge", MB_ICONERROR); return; }
    EnableWindow(install_button, FALSE); EnableWindow(path_edit, FALSE);
    EnableWindow(browse_button, FALSE); EnableWindow(tools_check, FALSE);
}

static void finish(HWND window, int ok) {
    WaitForSingleObject(worker, INFINITE);
    CloseHandle(worker); worker = NULL;
    if (ok) {
        SetWindowTextW(status_text, L"DekuForge is installed. Use DekuForge.exe or the Start Menu shortcut.");
        if (!no_launch) {
            wchar_t launcher[DEKU_PATH];
            STARTUPINFOW startup = {0}; startup.cb = sizeof startup;
            PROCESS_INFORMATION process = {0};
            if (swprintf(launcher, DEKU_PATH, L"%ls\\DekuForge.exe", install_root) > 0
                && CreateProcessW(launcher, NULL, NULL, NULL, FALSE, 0, NULL, install_root, &startup, &process)) {
                CloseHandle(process.hThread); CloseHandle(process.hProcess);
            }
        }
        if (!silent_mode)
            MessageBoxW(window, L"DekuForge is ready. Choose Build game and select your own NUP archive.", L"DekuForge", MB_OK | MB_ICONINFORMATION);
        DestroyWindow(window); PostQuitMessage(0);
        return;
    }
    wchar_t message[DEKU_PATH + 1200];
    swprintf(message, DEKU_PATH + 1200, L"Setup stopped. Your game files and saves were not removed.\n%ls\nLog: %ls", failure, log_path);
    SetWindowTextW(status_text, message);
    if (silent_mode) { DestroyWindow(window); PostQuitMessage(1); return; }
    EnableWindow(install_button, TRUE); EnableWindow(path_edit, TRUE);
    EnableWindow(browse_button, TRUE); EnableWindow(tools_check, TRUE);
}

static LRESULT CALLBACK window_proc(HWND w, UINT msg, WPARAM wp, LPARAM lp) {
    if (msg == WM_COMMAND && LOWORD(wp) == 2) {
        BROWSEINFOW browse = {0}; browse.hwndOwner = w; browse.lpszTitle = L"Where should DekuForge be installed?";
        browse.ulFlags = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE;
        PIDLIST_ABSOLUTE chosen = SHBrowseForFolderW(&browse);
        if (chosen) { wchar_t folder[MAX_PATH]; if (SHGetPathFromIDListW(chosen, folder)) SetWindowTextW(path_edit, folder); CoTaskMemFree(chosen); }
        return 0;
    }
    if (msg == WM_COMMAND && LOWORD(wp) == 1) { start_install(w); return 0; }
    if (msg == WM_SETUP_STAGE && wp < sizeof stages / sizeof stages[0]) { SetWindowTextW(status_text, stages[wp]); return 0; }
    if (msg == WM_SETUP_DONE) { finish(w, (int)wp); return 0; }
    if (msg == WM_CLOSE) {
        if (worker) { MessageBoxW(w, L"Setup is active. Please wait for it to finish.", L"DekuForge", MB_OK); return 0; }
        DestroyWindow(w); PostQuitMessage(0); return 0;
    }
    if (msg == WM_CTLCOLORSTATIC || msg == WM_CTLCOLOREDIT) { SetTextColor((HDC)wp, RGB(231, 242, 225)); SetBkColor((HDC)wp, RGB(12, 30, 19)); return (LRESULT)background; }
    return DefWindowProcW(w, msg, wp, lp);
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR args, int show) {
    (void)previous; (void)args; (void)show; app = instance; CoInitializeEx(NULL, COINIT_APARTMENTTHREADED);
    background = CreateSolidBrush(RGB(12, 30, 19));
    wchar_t initial[DEKU_PATH] = {0};
    PWSTR appdata = NULL;
    if (SUCCEEDED(SHGetKnownFolderPath(&FOLDERID_LocalAppData, 0, NULL, &appdata)))
        swprintf(initial, DEKU_PATH, L"%ls\\Programs\\DekuForge Preview", appdata);
    CoTaskMemFree(appdata);
    int argc; wchar_t **argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    for (int i = 1; argv && i < argc; i++) {
        if (!_wcsicmp(argv[i], L"/SILENT")) silent_mode = 1;
        else if (!_wcsicmp(argv[i], L"/NOLAUNCH")) no_launch = 1;
        else if (!_wcsicmp(argv[i], L"/NOSHORTCUT")) no_shortcut = 1;
        else if (!_wcsicmp(argv[i], L"/SKIPTOOLS")) skip_tools = 1;
        else if (!_wcsnicmp(argv[i], L"/DIR=", 5)) { wcsncpy(initial, argv[i] + 5, DEKU_PATH - 1); initial[DEKU_PATH - 1] = 0; }
    }
    LocalFree(argv);
    WNDCLASSW wc = {0}; wc.lpfnWndProc = window_proc; wc.hInstance = instance; wc.lpszClassName = L"DekuForgeSetup";
    wc.hbrBackground = background; wc.hCursor = LoadCursorW(NULL, IDC_ARROW); wc.hIcon = LoadIconW(instance, MAKEINTRESOURCEW(101)); RegisterClassW(&wc);
    HWND w = CreateWindowW(wc.lpszClassName, L"DekuForge Setup", WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
        (GetSystemMetrics(SM_CXSCREEN) - 650) / 2, (GetSystemMetrics(SM_CYSCREEN) - 350) / 2, 650, 350, NULL, NULL, instance, NULL);
    main_window = w;
    HFONT font = CreateFontW(-17, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE, DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"Segoe UI");
    CreateWindowW(L"STATIC", L"DekuForge - Reforging a legend.", WS_CHILD | WS_VISIBLE, 26, 22, 580, 30, w, NULL, instance, NULL);
    CreateWindowW(L"STATIC", L"Where should DekuForge be installed?", WS_CHILD | WS_VISIBLE, 26, 70, 580, 26, w, NULL, instance, NULL);
    path_edit = CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", initial, WS_CHILD | WS_VISIBLE | ES_AUTOHSCROLL, 26, 101, 470, 30, w, NULL, instance, NULL);
    browse_button = CreateWindowW(L"BUTTON", L"Browse...", WS_CHILD | WS_VISIBLE, 509, 101, 108, 30, w, (HMENU)2, instance, NULL);
    tools_check = CreateWindowW(L"BUTTON", L"Download and prepare game build tools now", WS_CHILD | WS_VISIBLE | BS_AUTOCHECKBOX, 26, 146, 580, 26, w, NULL, instance, NULL);
    SendMessageW(tools_check, BM_SETCHECK, skip_tools ? BST_UNCHECKED : BST_CHECKED, 0);
    status_text = CreateWindowW(L"STATIC", L"No game files are included. You need your own supported game dump.", WS_CHILD | WS_VISIBLE, 26, 190, 580, 60, w, NULL, instance, NULL);
    install_button = CreateWindowW(L"BUTTON", L"Install DekuForge", WS_CHILD | WS_VISIBLE | BS_DEFPUSHBUTTON, 420, 267, 197, 32, w, (HMENU)1, instance, NULL);
    for (HWND control = GetWindow(w, GW_CHILD); control; control = GetWindow(control, GW_HWNDNEXT)) SendMessageW(control, WM_SETFONT, (WPARAM)font, TRUE);
    if (silent_mode) start_install(w); else ShowWindow(w, SW_SHOW);
    MSG event; while (GetMessageW(&event, NULL, 0, 0) > 0) { TranslateMessage(&event); DispatchMessageW(&event); }
    DeleteObject(font); DeleteObject(background); CoUninitialize(); return (int)event.wParam;
}
