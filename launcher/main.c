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

static int regular_file(const wchar_t *path) {
    DWORD attributes = GetFileAttributesW(path);
    return attributes != INVALID_FILE_ATTRIBUTES && !(attributes & FILE_ATTRIBUTE_DIRECTORY);
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR args, int show) {
    (void)instance; (void)previous; (void)show;
    wchar_t root[32768], config[32768], python[32768] = {0}, script[32768], command[32768];
    DWORD count = GetModuleFileNameW(NULL, root, 32768);
    if (!count || count >= 32768) return 1;
    wchar_t *slash = wcsrchr(root, L'\\');
    if (!slash) return 1;
    *slash = 0;
    if (swprintf(config, 32768, L"%ls\\local\\python-path.txt", root) < 0) return 1;
    HANDLE input = CreateFileW(config, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (input != INVALID_HANDLE_VALUE) {
        char bytes[16384]; DWORD length = 0;
        if (ReadFile(input, bytes, sizeof(bytes) - 1, &length, NULL)) {
            bytes[length] = 0;
            char *end = strpbrk(bytes, "\r\n");
            if (end) *end = 0;
            MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, bytes, -1, python, 32768);
        }
        CloseHandle(input);
    }
    if (!python[0]) swprintf(python, 32768, L"%ls\\python\\pythonw.exe", root);
    if (!regular_file(python)) swprintf(python, 32768, L"%ls\\.venv\\Scripts\\pythonw.exe", root);
    if (!regular_file(python)) {
        MessageBoxW(NULL, L"Configure Python in local\\python-path.txt or install it in the project's .venv.",
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
