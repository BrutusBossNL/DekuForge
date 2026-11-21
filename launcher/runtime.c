// Pinned launcher runtime bootstrap shared by the launcher and setup. Downloads
// use WinHTTP and are verified by size and SHA-256 before tar.exe extracts them.
#ifndef UNICODE
#define UNICODE 1
#endif
#ifndef _UNICODE
#define _UNICODE 1
#endif
#include "runtime.h"
#include "runtime_pin.h"
#include <winhttp.h>
#include <bcrypt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

#ifndef WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY
#define WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY 4
#endif

static int read_small(const wchar_t *path, char *buffer, DWORD capacity) {
    HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (file == INVALID_HANDLE_VALUE) return 0;
    DWORD read = 0;
    int ok = ReadFile(file, buffer, capacity - 1, &read, NULL) && read < capacity - 1;
    CloseHandle(file);
    buffer[ok ? read : 0] = 0;
    return ok;
}

// Reads a string member from the small marker files written by DekuForge.
static int json_string(const char *text, const char *key, char *value, size_t capacity) {
    char pattern[64];
    snprintf(pattern, sizeof pattern, "\"%s\"", key);
    for (const char *found = strstr(text, pattern); found; found = strstr(found + 1, pattern)) {
        const char *p = found + strlen(pattern);
        while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') ++p;
        if (*p != ':') continue;
        ++p;
        while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') ++p;
        if (*p++ != '"') return 0;
        size_t used = 0;
        while (p[used] && p[used] != '"' && p[used] != '\\') {
            if (used + 1 >= capacity) return 0;
            value[used] = p[used];
            ++used;
        }
        value[used] = 0;
        return p[used] == '"';
    }
    return 0;
}

static int runtime_path(const wchar_t *root, wchar_t *runtime) {
    int count = swprintf(runtime, DEKU_PATH, L"%ls\\python\\%ls", root, DEKU_PYTHON_ID);
    return count > 0 && count < DEKU_PATH - 64 ? 1 : deku_fail("Path is too long");
}

deku_runtime_state deku_runtime_status(const wchar_t *root) {
    wchar_t *runtime = malloc(DEKU_PATH * sizeof *runtime), *path = malloc(DEKU_PATH * sizeof *path);
    char *marker = malloc(65536);
    deku_runtime_state state = DEKU_RUNTIME_FOREIGN;
    char python[80], pillow[80];
    if (runtime && path && marker && runtime_path(root, runtime)) {
        if (GetFileAttributesW(runtime) == INVALID_FILE_ATTRIBUTES) {
            state = DEKU_RUNTIME_MISSING;
        } else if (deku_join(path, runtime, L".dekuforge-runtime.json") && read_small(path, marker, 65536)
                   && json_string(marker, "sha256", python, sizeof python) && !strcmp(python, DEKU_PYTHON_SHA256)
                   && json_string(marker, "pillow_sha256", pillow, sizeof pillow) && !strcmp(pillow, DEKU_PILLOW_SHA256)
                   && deku_join(path, runtime, L"pythonw.exe") && deku_regular_file(path)) {
            state = DEKU_RUNTIME_READY;
        }
    }
    free(runtime); free(path); free(marker);
    return state;
}

static int download(const wchar_t *url, const wchar_t *target, unsigned long long expected) {
    URL_COMPONENTS parts;
    wchar_t host[256], path[4096], extra[2048];
    ZeroMemory(&parts, sizeof parts);
    parts.dwStructSize = sizeof parts;
    parts.lpszHostName = host; parts.dwHostNameLength = 256;
    parts.lpszUrlPath = path; parts.dwUrlPathLength = 4096;
    parts.lpszExtraInfo = extra; parts.dwExtraInfoLength = 2048;
    if (!WinHttpCrackUrl(url, 0, 0, &parts) || parts.nScheme != INTERNET_SCHEME_HTTPS
        || wcslen(path) + wcslen(extra) >= 4096)
        return deku_fail("Invalid runtime download address");
    wcscat(path, extra);
    HINTERNET session = WinHttpOpen(L"DekuForge/" DEKU_LAUNCHER_VERSION, WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY,
                                    WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (!session) session = WinHttpOpen(L"DekuForge/" DEKU_LAUNCHER_VERSION, WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
                                        WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (!session) return deku_fail_code("Cannot start the runtime download", GetLastError());
    WinHttpSetTimeouts(session, 30000, 30000, 60000, 120000);
    HINTERNET connection = WinHttpConnect(session, host, parts.nPort, 0);
    HINTERNET request = connection ? WinHttpOpenRequest(connection, L"GET", path, NULL, WINHTTP_NO_REFERER,
                                                        WINHTTP_DEFAULT_ACCEPT_TYPES, WINHTTP_FLAG_SECURE) : NULL;
    DWORD status = 0, size = sizeof status;
    int ok = request && WinHttpSendRequest(request, WINHTTP_NO_ADDITIONAL_HEADERS, 0, WINHTTP_NO_REQUEST_DATA, 0, 0, 0)
             && WinHttpReceiveResponse(request, NULL);
    if (!ok) deku_fail_code("Runtime download failed; check the internet connection", GetLastError());
    if (ok && (!WinHttpQueryHeaders(request, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
                                    WINHTTP_HEADER_NAME_BY_INDEX, &status, &size, WINHTTP_NO_HEADER_INDEX) || status != 200))
        ok = deku_fail("Runtime download was refused by the server");
    HANDLE file = ok ? CreateFileW(target, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL) : INVALID_HANDLE_VALUE;
    if (ok && file == INVALID_HANDLE_VALUE) ok = deku_fail_code("Cannot create the runtime download", GetLastError());
    unsigned long long total = 0;
    char *buffer = ok ? malloc(65536) : NULL;
    if (ok && !buffer) ok = deku_fail("Not enough memory");
    while (ok) {
        DWORD read = 0, written = 0;
        if (!WinHttpReadData(request, buffer, 65536, &read)) { ok = deku_fail_code("Runtime download was interrupted", GetLastError()); break; }
        if (!read) break;
        total += read;
        if (total > expected) { ok = deku_fail("Runtime download is larger than its pinned size"); break; }
        if (!WriteFile(file, buffer, read, &written, NULL) || written != read) ok = deku_fail_code("Cannot write the runtime download", GetLastError());
    }
    free(buffer);
    if (file != INVALID_HANDLE_VALUE && !CloseHandle(file)) ok = ok && deku_fail("Cannot write the runtime download");
    if (ok && total != expected) ok = deku_fail("Runtime download size mismatch");
    if (request) WinHttpCloseHandle(request);
    if (connection) WinHttpCloseHandle(connection);
    WinHttpCloseHandle(session);
    return ok;
}

static int file_size(const wchar_t *path, unsigned long long *size) {
    WIN32_FILE_ATTRIBUTE_DATA data;
    if (!GetFileAttributesExW(path, GetFileExInfoStandard, &data) || (data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) return 0;
    *size = ((unsigned long long)data.nFileSizeHigh << 32) | data.nFileSizeLow;
    return 1;
}

static int matches(const wchar_t *path, const char *sha, unsigned long long size) {
    unsigned long long actual = 0;
    char digest[65];
    return file_size(path, &actual) && actual == size && deku_sha256_file(path, digest) && !strcmp(digest, sha);
}

static int fetch(const wchar_t *root, const wchar_t *cache, const wchar_t *url, const wchar_t *name,
                 const char *sha, unsigned long long size, wchar_t *file) {
    wchar_t *partial = malloc(DEKU_PATH * sizeof *partial);
    int ok = partial ? deku_join(file, cache, name) && deku_owned_path(root, file) : deku_fail("Not enough memory");
    if (ok && !matches(file, sha, size)) {
        ok = swprintf(partial, DEKU_PATH, L"%ls.part", file) > 0 && deku_owned_path(root, partial)
             && download(url, partial, size);
        if (ok && !matches(partial, sha, size)) ok = deku_fail("Runtime download checksum mismatch");
        if (ok && !MoveFileExW(partial, file, MOVEFILE_REPLACE_EXISTING)) ok = deku_fail_code("Cannot store the runtime download", GetLastError());
        if (!ok) DeleteFileW(partial);
    }
    free(partial);
    return ok;
}

static int write_utf8_line(const wchar_t *path, const wchar_t *text) {
    char *bytes = malloc(DEKU_PATH * 3 + 2);
    int length = bytes ? WideCharToMultiByte(CP_UTF8, 0, text, -1, bytes, DEKU_PATH * 3, NULL, NULL) : 0;
    int ok = length > 0;
    if (ok) {
        bytes[length - 1] = '\n';
        ok = deku_write_file(path, bytes, (size_t)length, CREATE_ALWAYS);
    } else {
        deku_fail("Cannot encode path");
    }
    free(bytes);
    return ok;
}

static int install_runtime(const wchar_t *root, const wchar_t *local, const wchar_t *runtime) {
    wchar_t *cache = malloc(DEKU_PATH * sizeof *cache), *archive = malloc(DEKU_PATH * sizeof *archive),
            *wheel = malloc(DEKU_PATH * sizeof *wheel), *staging = malloc(DEKU_PATH * sizeof *staging),
            *python = malloc(DEKU_PATH * sizeof *python), *path = malloc(DEKU_PATH * sizeof *path),
            *command = malloc(DEKU_PATH * sizeof *command);
    int ok = cache && archive && wheel && staging && python && path && command ? 1 : deku_fail("Not enough memory");
    int staged = 0;
    if (ok) ok = deku_join(cache, local, L"build-tools") && deku_owned_path(root, cache);
    if (ok && !CreateDirectoryW(cache, NULL) && GetLastError() != ERROR_ALREADY_EXISTS)
        ok = deku_fail_code("Cannot create the download cache", GetLastError());
    if (ok) ok = fetch(root, cache, DEKU_PYTHON_URL, DEKU_PYTHON_CACHE, DEKU_PYTHON_SHA256, DEKU_PYTHON_SIZE, archive);
    if (ok) ok = fetch(root, cache, DEKU_PILLOW_URL, DEKU_PILLOW_CACHE, DEKU_PILLOW_SHA256, DEKU_PILLOW_SIZE, wheel);
    if (ok) {
        UCHAR random[16];
        wchar_t name[64];
        ok = BCRYPT_SUCCESS(BCryptGenRandom(NULL, random, sizeof random, BCRYPT_USE_SYSTEM_PREFERRED_RNG)) ? 1 : deku_fail("Cannot create a staging name");
        int used = swprintf(name, 64, L"python-stage-");
        for (int i = 0; ok && i < 16; ++i) used += swprintf(name + used, 64 - used, L"%02x", random[i]);
        if (ok) ok = deku_join(staging, local, name) && deku_owned_path(root, staging);
        if (ok && !CreateDirectoryW(staging, NULL)) ok = deku_fail_code("Cannot create the runtime staging folder", GetLastError());
        staged = ok;
    }
    deku_listing_rules python_rules = {20000, 128ull * 1024 * 1024, "python/"};
    deku_listing_rules pillow_rules = {20000, 64ull * 1024 * 1024, NULL};
    if (ok) ok = deku_extract(archive, staging, &python_rules);
    if (ok) ok = deku_join(python, staging, L"python") && deku_owned_path(root, python)
                 && deku_join(path, python, L"Lib\\site-packages") && deku_owned_path(root, path)
                 && deku_extract(wheel, path, &pillow_rules);
    DWORD code = 1;
    if (ok) ok = deku_join(path, python, L"python.exe") && (deku_regular_file(path) || deku_fail("The runtime archive has no python.exe"))
                 && swprintf(command, DEKU_PATH, L"\"%ls\" -I -c \"import tkinter,PIL,ssl\"", path) > 0
                 && deku_run(path, command, python, NULL, &code);
    if (ok && code) ok = deku_fail("Independent Python/Tk/Pillow check failed");
    if (ok) {
        static const char format[] = "{\"version\": \"%s\", \"sha256\": \"%s\", \"pillow_sha256\": \"%s\", "
                                     "\"provider\": \"%s\", \"game_files\": false}\n";
        char identity[512];
        int length = snprintf(identity, sizeof identity, format, DEKU_PYTHON_VERSION, DEKU_PYTHON_SHA256,
                              DEKU_PILLOW_SHA256, DEKU_RUNTIME_SOURCE);
        ok = length > 0 && length < (int)sizeof identity && deku_join(path, python, L".dekuforge-runtime.json")
             && deku_write_file(path, identity, (size_t)length, CREATE_NEW);
    }
    if (ok) {
        ok = swprintf(path, DEKU_PATH, L"%ls\\python", root) > 0 && deku_owned_path(root, path);
        if (ok && !CreateDirectoryW(path, NULL) && GetLastError() != ERROR_ALREADY_EXISTS)
            ok = deku_fail_code("Cannot create the runtime folder", GetLastError());
    }
    if (ok) ok = deku_owned_path(root, runtime);
    if (ok && !MoveFileExW(python, runtime, 0)) ok = deku_fail_code("Cannot activate the runtime", GetLastError());
    if (staged) {
        char saved[512];
        snprintf(saved, sizeof saved, "%s", deku_error());
        if (!deku_remove_tree(staging) && ok) ok = 0;
        else if (!ok) deku_fail(saved);
    }
    free(cache); free(archive); free(wheel); free(staging); free(python); free(path); free(command);
    return ok;
}

int deku_prepare_runtime(const wchar_t *requested) {
    wchar_t *root = malloc(DEKU_PATH * sizeof *root), *local = malloc(DEKU_PATH * sizeof *local),
            *runtime = malloc(DEKU_PATH * sizeof *runtime), *path = malloc(DEKU_PATH * sizeof *path),
            *record = malloc(DEKU_PATH * sizeof *record);
    int ok = root && local && runtime && path && record ? deku_full_path(requested, root) : deku_fail("Not enough memory");
    if (ok && !wcscmp(DEKU_PYTHON_ID, L"development-interpreter")) ok = deku_fail("Development launchers use an explicit Python path");
    int logged = ok && deku_join(local, root, L"local") && deku_owned_path(root, local)
                 && (CreateDirectoryW(local, NULL) || GetLastError() == ERROR_ALREADY_EXISTS);
    ok = ok && logged;
    if (ok) ok = runtime_path(root, runtime) && deku_owned_path(root, runtime);
    if (ok) {
        deku_runtime_state state = deku_runtime_status(root);
        if (state == DEKU_RUNTIME_FOREIGN) ok = deku_fail("Existing runtime is unowned or has another identity");
        else if (state == DEKU_RUNTIME_MISSING) ok = install_runtime(root, local, runtime);
    }
    if (ok) ok = deku_join(path, runtime, L"python.exe") && deku_join(record, local, L"python-path.txt")
                 && write_utf8_line(record, path);
    if (logged && deku_join(path, local, L"runtime-bootstrap.log")) {
        const char *message = ok ? "Official standalone Python/Tk and pinned Pillow prepared natively; no script host used.\n" : deku_error();
        char saved[512];
        snprintf(saved, sizeof saved, "%s", message);
        deku_write_file(path, saved, strlen(saved), CREATE_ALWAYS);
        if (!ok) deku_fail(saved);
    }
    free(root); free(local); free(runtime); free(path); free(record);
    return ok;
}
