// DekuForge desktop bootstrap. The application icon is embedded at build time.
// The pinned runtime is prepared natively (see runtime.c); no script host runs.
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
#include "runtime.h"
#include "native.h"

static int regular_file(const wchar_t *path) {
    DWORD attributes = GetFileAttributesW(path);
    return attributes != INVALID_FILE_ATTRIBUTES && !(attributes & FILE_ATTRIBUTE_DIRECTORY);
}

static int development_python(const wchar_t *root, wchar_t *python) {
    if (wcscmp(DEKU_PYTHON_ID, L"development-interpreter")) return 0;
    wchar_t config[32768];
    swprintf(config,32768,L"%ls\\local\\python-path.txt",root);
    FILE *stream = _wfopen(config,L"rb");
    if (!stream) return 0;
    char bytes[32768];
    size_t count = fread(bytes,1,sizeof(bytes)-1,stream);
    int extra = fgetc(stream);
    fclose(stream);
    if (!count || extra != EOF) return 0;
    while (count && (bytes[count-1]=='\n' || bytes[count-1]=='\r')) --count;
    bytes[count]=0;
    if (memchr(bytes,'\n',count) || memchr(bytes,'\r',count) || memchr(bytes,0,count)) return 0;
    wchar_t candidate[32768];
    if (!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,bytes,-1,candidate,32768)) return 0;
    size_t length=wcslen(candidate);
    // Explicit developer opt-in, never an implicit interpreter found on PATH.
    if (length<=7 || candidate[1]!=L':' || candidate[2]!=L'\\' ||
        _wcsicmp(candidate+length-4,L".exe") || !regular_file(candidate)) return 0;
    wcscpy(python,candidate);
    return 1;
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

static DWORD WINAPI prepare_worker(LPVOID root) {
    return deku_prepare_runtime((const wchar_t *)root) ? 0 : 1;
}

// A progress window is shown only while a missing runtime is downloaded.
static int prepare_runtime(const wchar_t *root, HINSTANCE instance) {
    if (deku_runtime_status(root) != DEKU_RUNTIME_MISSING) return deku_prepare_runtime(root);
    HANDLE worker = CreateThread(NULL, 1 << 20, prepare_worker, (LPVOID)root, 0, NULL);
    if (!worker) return 0;
    WNDCLASSW wc={0}; wc.lpfnWndProc=setup_window; wc.hInstance=instance; wc.lpszClassName=L"DekuForgeRuntimeSetup";
    wc.hCursor=LoadCursorW(NULL,IDC_ARROW); wc.hIcon=LoadIconW(instance,MAKEINTRESOURCEW(101)); RegisterClassW(&wc);
    HWND window=CreateWindowW(wc.lpszClassName,L"DekuForge",WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU,
        (GetSystemMetrics(SM_CXSCREEN)-480)/2,(GetSystemMetrics(SM_CYSCREEN)-205)/2,480,205,NULL,NULL,instance,NULL);
    ShowWindow(window,SW_SHOW); SetTimer(window,1,80,NULL);
    int cancelled = 0;
    while (WaitForSingleObject(worker,20)==WAIT_TIMEOUT) {
        MSG event;
        while(PeekMessageW(&event,NULL,0,0,PM_REMOVE)) { TranslateMessage(&event); DispatchMessageW(&event); }
        // Closing the window ends this process; the next start resumes from verified downloads.
        if (!IsWindow(window)) { cancelled = 1; break; }
    }
    DWORD code=1;
    if (!cancelled) GetExitCodeThread(worker,&code);
    if(IsWindow(window)) DestroyWindow(window);
    CloseHandle(worker);
    return !cancelled && code==0;
}

static int run_recomplauncher(const wchar_t *root, const wchar_t *args) {
    HANDLE output = GetStdHandle(STD_OUTPUT_HANDLE);
    if (output == INVALID_HANDLE_VALUE) output = NULL;
    if (!deku_prepare_runtime(root)) {
        if (output) {
            const char *error = deku_error();
            DWORD written;
            WriteFile(output, error, (DWORD)strlen(error), &written, NULL);
            WriteFile(output, "\n", 1, &written, NULL);
        }
        return 1;
    }
    wchar_t python[DEKU_PATH], command[DEKU_PATH];
    if (swprintf(python, DEKU_PATH, L"%ls\\python\\%ls\\python.exe", root, DEKU_PYTHON_ID) < 0 ||
        swprintf(command, DEKU_PATH, L"\"%ls\" -B -u \"%ls\\run_launcher.py\" %ls", python, root, args) < 0)
        return 1;
    DWORD code;
    return deku_run(python, command, root, output, &code) ? (int)code : 1;
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR args, int show) {
    (void)previous; (void)show;
    wchar_t root[32768], python[32768] = {0}, script[32768], command[32768];
    DWORD count = GetModuleFileNameW(NULL, root, 32768);
    if (!count || count >= 32768) return 1;
    wchar_t *slash = wcsrchr(root, L'\\');
    if (!slash) return 1;
    *slash = 0;
    if (!wcscmp(args, L"--recomp-play") || !wcscmp(args, L"--recomp-prepare") ||
        !wcsncmp(args, L"--recomp-prepare ", 17))
        return run_recomplauncher(root, args);
    wchar_t owned[32768];
    swprintf(owned,32768,L"%ls\\python\\%ls\\pythonw.exe",root,DEKU_PYTHON_ID);
    wcscpy(python,owned);
    if (!wcscmp(args,L"--prepare-runtime")) {
        // Used by the update helper after it installs a package with a new runtime pin.
        return prepare_runtime(root,instance) && regular_file(owned) ? 0 : 1;
    }
    int developer = development_python(root,python);
    if (!regular_file(python) && !wcscmp(DEKU_PYTHON_ID,L"development-interpreter")) {
        MessageBoxW(NULL,L"This development launcher needs Python with Tk and Pillow. Set its absolute python.exe path in local\\python-path.txt.",
                    L"DekuForge development",MB_OK|MB_ICONINFORMATION);
        return 1;
    }
    if (!regular_file(python) && !developer) {
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
    const wchar_t *option = !wcscmp(args, L"--self-test") ? L" --self-test" :
                           !wcscmp(args,L"--startup-smoke") ? L" --startup-smoke" : L"";
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
