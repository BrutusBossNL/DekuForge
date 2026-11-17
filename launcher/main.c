// DekuForge desktop bootstrap. The application icon is embedded at build time.
#ifndef UNICODE
#define UNICODE 1
#endif
#ifndef _UNICODE
#define _UNICODE 1
#endif
#include <windows.h>
#include <wchar.h>
#include <stdio.h>
#include <string.h>
#include "runtime_pin.h"

static int regular_file(const wchar_t *path) {
    DWORD attributes = GetFileAttributesW(path);
    return attributes != INVALID_FILE_ATTRIBUTES && !(attributes & FILE_ATTRIBUTE_DIRECTORY);
}

static LRESULT CALLBACK setup_window(HWND window, UINT message, WPARAM wp, LPARAM lp) {
    if (message == WM_PAINT) {
        PAINTSTRUCT ps; HDC dc = BeginPaint(window, &ps); RECT r;
        GetClientRect(window, &r);
        HBRUSH bg = CreateSolidBrush(RGB(8, 25, 15)); FillRect(dc, &r, bg); DeleteObject(bg);
        SetBkMode(dc, TRANSPARENT); SetTextColor(dc, RGB(236, 191, 66));
        HFONT font = CreateFontW(-28,0,0,0,FW_SEMIBOLD,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");
        HGDIOBJ old = SelectObject(dc, font);
        RECT title = {24,20,r.right-24,64}; DrawTextW(dc,L"DekuForge",-1,&title,DT_LEFT);
        SelectObject(dc, old); DeleteObject(font);
        SetTextColor(dc, RGB(207,226,203));
        RECT line = {24,78,r.right-24,112}; DrawTextW(dc,L"Preparing the launcher runtime...",-1,&line,DT_LEFT);
        RECT track = {24,126,r.right-24,131}; HBRUSH green = CreateSolidBrush(RGB(138,181,78));
        int width = 80, x = 24 + (int)((GetTickCount64()/9) % (ULONGLONG)(r.right-128));
        RECT segment = {x,126,x+width,131}; FillRect(dc,&track,(HBRUSH)GetStockObject(BLACK_BRUSH)); FillRect(dc,&segment,green); DeleteObject(green);
        EndPaint(window,&ps); return 0;
    }
    if (message == WM_TIMER) { InvalidateRect(window,NULL,FALSE); return 0; }
    return DefWindowProcW(window,message,wp,lp);
}

static int prepare_runtime(const wchar_t *root, HINSTANCE instance) {
    wchar_t shell[32768], script[32768], command[32768];
    UINT n = GetSystemDirectoryW(shell,32768);
    if (!n || n > 32000) return 0;
    wcscat(shell,L"\\WindowsPowerShell\\v1.0\\powershell.exe");
    swprintf(script,32768,L"%ls\\tools\\bootstrap_runtime.ps1",root);
    if (!regular_file(script)) return 0;
    swprintf(command,32768,L"\"%ls\" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File \"%ls\" -Root \"%ls\"",shell,script,root);
    STARTUPINFOW startup={0}; startup.cb=sizeof startup; PROCESS_INFORMATION child={0};
    if (!CreateProcessW(shell,command,NULL,NULL,FALSE,CREATE_NO_WINDOW,NULL,root,&startup,&child)) return 0;
    WNDCLASSW wc={0}; wc.lpfnWndProc=setup_window; wc.hInstance=instance; wc.lpszClassName=L"DekuForgeRuntimeSetup";
    wc.hCursor=LoadCursorW(NULL,IDC_ARROW); wc.hIcon=LoadIconW(instance,MAKEINTRESOURCEW(101)); RegisterClassW(&wc);
    HWND window=CreateWindowW(wc.lpszClassName,L"DekuForge",WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU,
        (GetSystemMetrics(SM_CXSCREEN)-480)/2,(GetSystemMetrics(SM_CYSCREEN)-205)/2,480,205,NULL,NULL,instance,NULL);
    ShowWindow(window,SW_SHOW); SetTimer(window,1,80,NULL);
    while (WaitForSingleObject(child.hProcess,20)==WAIT_TIMEOUT) {
        MSG event;
        while(PeekMessageW(&event,NULL,0,0,PM_REMOVE)) { TranslateMessage(&event); DispatchMessageW(&event); }
        if (!IsWindow(window)) { TerminateProcess(child.hProcess,1); break; }
    }
    DWORD code=1; GetExitCodeProcess(child.hProcess,&code);
    if(IsWindow(window)) DestroyWindow(window);
    CloseHandle(child.hThread); CloseHandle(child.hProcess);
    return code==0;
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR args, int show) {
    (void)previous; (void)show;
    wchar_t root[32768], python[32768] = {0}, script[32768], command[32768];
    DWORD count = GetModuleFileNameW(NULL, root, 32768);
    if (!count || count >= 32768) return 1;
    wchar_t *slash = wcsrchr(root, L'\\');
    if (!slash) return 1;
    *slash = 0;
    wchar_t owned[32768];
    swprintf(owned,32768,L"%ls\\python\\%ls\\pythonw.exe",root,DEKU_PYTHON_ID);
    wcscpy(python,owned);
    if (!regular_file(python)) {
        if (prepare_runtime(root,instance) && regular_file(owned)) wcscpy(python,owned);
    }
    if (!regular_file(python)) {
        MessageBoxW(NULL, L"Could not prepare the launcher runtime. See local\\runtime-bootstrap.log.",
                    L"DekuForge", MB_OK | MB_ICONERROR);
        return 1;
    }
    wchar_t *filename = wcsrchr(python, L'\\');
    if (filename && !_wcsicmp(filename + 1, L"python.exe")) {
        wchar_t candidate[32768];
        wcscpy(candidate, python);
        wcscpy(wcsrchr(candidate, L'\\') + 1, L"pythonw.exe");
        if (regular_file(candidate)) wcscpy(python, candidate);
    }
    if (swprintf(script, 32768, L"%ls\\run_launcher.py", root) < 0 || !regular_file(script)) return 1;
    const wchar_t *option = !wcscmp(args, L"--self-test") ? L" --self-test" : L"";
    if (swprintf(command, 32768, L"\"%ls\" \"%ls\"%ls", python, script, option) < 0) return 1;
    STARTUPINFOW startup = {0}; startup.cb = sizeof(startup);
    PROCESS_INFORMATION process = {0};
    if (!CreateProcessW(python, command, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, root, &startup, &process)) {
        MessageBoxW(NULL, L"Could not start DekuForge. Check your Python installation.", L"DekuForge", MB_OK | MB_ICONERROR);
        return 1;
    }
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return 0;
}
