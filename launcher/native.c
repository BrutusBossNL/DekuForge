// Native file, digest, process and archive helpers for the DekuForge
// executables. Digests use Windows CNG; archives are listed, checked and then
// extracted by the Windows tar.exe. No script host is started.
#ifndef UNICODE
#define UNICODE 1
#endif
#ifndef _UNICODE
#define _UNICODE 1
#endif
#include "native.h"
#include <bcrypt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

#define MAX_LISTING (16u * 1024u * 1024u)

static _Thread_local char error_text[512];

const char *deku_error(void) { return error_text[0] ? error_text : "Unknown error"; }

int deku_fail(const char *message) {
    snprintf(error_text, sizeof error_text, "%s", message);
    return 0;
}

int deku_fail_code(const char *message, DWORD code) {
    snprintf(error_text, sizeof error_text, "%s (Windows error %lu)", message, (unsigned long)code);
    return 0;
}

int deku_join(wchar_t *output, const wchar_t *left, const wchar_t *right) {
    int count = swprintf(output, DEKU_PATH, L"%ls\\%ls", left, right);
    return count > 0 && count < DEKU_PATH - 1 ? 1 : deku_fail("Path is too long");
}

int deku_regular_file(const wchar_t *path) {
    DWORD attributes = GetFileAttributesW(path);
    return attributes != INVALID_FILE_ATTRIBUTES && !(attributes & FILE_ATTRIBUTE_DIRECTORY);
}

int deku_full_path(const wchar_t *input, wchar_t *output) {
    DWORD length = GetFullPathNameW(input, DEKU_PATH, output, NULL);
    if (!length || length >= DEKU_PATH) return deku_fail("Invalid path");
    while (length > 3 && output[length - 1] == L'\\') output[--length] = 0;
    return 1;
}

int deku_owned_path(const wchar_t *root, const wchar_t *path) {
    wchar_t *current = malloc(DEKU_PATH * sizeof *current);
    if (!current) return deku_fail("Not enough memory");
    int ok = deku_full_path(path, current);
    size_t base = wcslen(root);
    if (ok && (wcslen(current) <= base || _wcsnicmp(current, root, base) || current[base] != L'\\'))
        ok = deku_fail("Path outside the DekuForge folder refused");
    while (ok) {
        DWORD attributes = GetFileAttributesW(current);
        if (attributes != INVALID_FILE_ATTRIBUTES && (attributes & FILE_ATTRIBUTE_REPARSE_POINT)) {
            ok = deku_fail("Linked path refused");
            break;
        }
        wchar_t *slash = wcsrchr(current, L'\\');
        if (wcslen(current) <= base || !slash || (size_t)(slash - current) < base) break;
        *slash = 0;
    }
    free(current);
    return ok;
}

typedef struct { BCRYPT_ALG_HANDLE algorithm; BCRYPT_HASH_HANDLE hash; } hasher;

static int hash_open(hasher *state) {
    state->algorithm = NULL; state->hash = NULL;
    if (!BCRYPT_SUCCESS(BCryptOpenAlgorithmProvider(&state->algorithm, BCRYPT_SHA256_ALGORITHM, NULL, 0)))
        return deku_fail("SHA-256 is unavailable");
    if (!BCRYPT_SUCCESS(BCryptCreateHash(state->algorithm, &state->hash, NULL, 0, NULL, 0, 0))) {
        BCryptCloseAlgorithmProvider(state->algorithm, 0);
        return deku_fail("SHA-256 is unavailable");
    }
    return 1;
}

static int hash_finish(hasher *state, int ok, char hex[65]) {
    UCHAR digest[32];
    if (ok && !BCRYPT_SUCCESS(BCryptFinishHash(state->hash, digest, sizeof digest, 0))) ok = deku_fail("SHA-256 failed");
    BCryptDestroyHash(state->hash);
    BCryptCloseAlgorithmProvider(state->algorithm, 0);
    if (!ok) return 0;
    for (int i = 0; i < 32; ++i) snprintf(hex + 2 * i, 3, "%02x", digest[i]);
    return 1;
}

int deku_sha256_bytes(const void *data, size_t size, char hex[65]) {
    hasher state;
    if (!hash_open(&state)) return 0;
    int ok = 1;
    const UCHAR *bytes = data;
    while (ok && size) {
        ULONG block = size > 0x1000000 ? 0x1000000 : (ULONG)size;
        if (!BCRYPT_SUCCESS(BCryptHashData(state.hash, (PUCHAR)bytes, block, 0))) ok = deku_fail("SHA-256 failed");
        bytes += block; size -= block;
    }
    return hash_finish(&state, ok, hex);
}

int deku_sha256_file(const wchar_t *path, char hex[65]) {
    HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_FLAG_SEQUENTIAL_SCAN, NULL);
    if (file == INVALID_HANDLE_VALUE) return deku_fail_code("Cannot read file for verification", GetLastError());
    hasher state;
    UCHAR *buffer = malloc(1 << 20);
    int ok = buffer && hash_open(&state);
    if (!buffer) deku_fail("Not enough memory");
    if (ok) {
        DWORD read = 0;
        while (ok) {
            if (!ReadFile(file, buffer, 1 << 20, &read, NULL)) { ok = deku_fail_code("Cannot read file for verification", GetLastError()); break; }
            if (!read) break;
            if (!BCRYPT_SUCCESS(BCryptHashData(state.hash, buffer, read, 0))) ok = deku_fail("SHA-256 failed");
        }
        ok = hash_finish(&state, ok, hex);
    }
    free(buffer);
    CloseHandle(file);
    return ok;
}

int deku_write_file(const wchar_t *path, const void *data, size_t size, DWORD disposition) {
    HANDLE file = CreateFileW(path, GENERIC_WRITE, 0, NULL, disposition, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) return deku_fail_code("Cannot create file", GetLastError());
    const char *bytes = data;
    int ok = 1;
    while (ok && size) {
        DWORD block = size > 0x1000000 ? 0x1000000 : (DWORD)size, written = 0;
        if (!WriteFile(file, bytes, block, &written, NULL) || written != block) ok = deku_fail_code("Cannot write file", GetLastError());
        bytes += block; size -= block;
    }
    if (!CloseHandle(file)) ok = ok && deku_fail_code("Cannot write file", GetLastError());
    return ok;
}

int deku_remove_tree(const wchar_t *path) {
    DWORD attributes = GetFileAttributesW(path);
    if (attributes == INVALID_FILE_ATTRIBUTES) {
        DWORD code = GetLastError();
        return code == ERROR_FILE_NOT_FOUND || code == ERROR_PATH_NOT_FOUND ? 1 : deku_fail_code("Cannot inspect cleanup path", code);
    }
    if (attributes & FILE_ATTRIBUTE_REPARSE_POINT) return deku_fail("Linked path refused during cleanup");
    if (!(attributes & FILE_ATTRIBUTE_DIRECTORY)) {
        if (attributes & FILE_ATTRIBUTE_READONLY) SetFileAttributesW(path, attributes & ~FILE_ATTRIBUTE_READONLY);
        return DeleteFileW(path) ? 1 : deku_fail_code("Cannot remove temporary file", GetLastError());
    }
    wchar_t *child = malloc(DEKU_PATH * sizeof *child);
    if (!child) return deku_fail("Not enough memory");
    int ok = deku_join(child, path, L"*");
    WIN32_FIND_DATAW item;
    HANDLE search = ok ? FindFirstFileExW(child, FindExInfoBasic, &item, FindExSearchNameMatch, NULL, 0) : INVALID_HANDLE_VALUE;
    if (ok && search == INVALID_HANDLE_VALUE) ok = deku_fail_code("Cannot list cleanup folder", GetLastError());
    while (ok) {
        if (wcscmp(item.cFileName, L".") && wcscmp(item.cFileName, L".."))
            ok = deku_join(child, path, item.cFileName) && deku_remove_tree(child);
        if (ok && !FindNextFileW(search, &item)) {
            if (GetLastError() != ERROR_NO_MORE_FILES) ok = deku_fail_code("Cannot list cleanup folder", GetLastError());
            break;
        }
    }
    if (search != INVALID_HANDLE_VALUE) FindClose(search);
    free(child);
    return ok && (RemoveDirectoryW(path) ? 1 : deku_fail_code("Cannot remove temporary folder", GetLastError()));
}

// Only the handles in `inherit` reach the child.
static int spawn(const wchar_t *program, const wchar_t *command, const wchar_t *directory,
                 HANDLE input, HANDLE output, PROCESS_INFORMATION *process) {
    SIZE_T size = 0;
    InitializeProcThreadAttributeList(NULL, 1, 0, &size);
    LPPROC_THREAD_ATTRIBUTE_LIST attributes = malloc(size);
    wchar_t *line = _wcsdup(command);
    HANDLE inherit[2] = {input, output};
    int ok = attributes && line && InitializeProcThreadAttributeList(attributes, 1, 0, &size);
    if (!ok) { free(attributes); free(line); return deku_fail("Cannot prepare a helper process"); }
    if (UpdateProcThreadAttribute(attributes, 0, PROC_THREAD_ATTRIBUTE_HANDLE_LIST, inherit, sizeof inherit, NULL, NULL)) {
        STARTUPINFOEXW startup;
        ZeroMemory(&startup, sizeof startup);
        startup.StartupInfo.cb = sizeof startup;
        startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
        startup.StartupInfo.hStdInput = input;
        startup.StartupInfo.hStdOutput = output;
        startup.StartupInfo.hStdError = output;
        startup.lpAttributeList = attributes;
        if (!CreateProcessW(program, line, NULL, NULL, TRUE, CREATE_NO_WINDOW | EXTENDED_STARTUPINFO_PRESENT,
                            NULL, directory, &startup.StartupInfo, process))
            ok = deku_fail_code("Cannot start a helper process", GetLastError());
    } else {
        ok = deku_fail_code("Cannot prepare a helper process", GetLastError());
    }
    DeleteProcThreadAttributeList(attributes);
    free(attributes);
    free(line);
    return ok;
}

static HANDLE null_device(DWORD access) {
    SECURITY_ATTRIBUTES security = {sizeof security, NULL, TRUE};
    return CreateFileW(L"NUL", access, FILE_SHARE_READ | FILE_SHARE_WRITE, &security, OPEN_EXISTING, 0, NULL);
}

int deku_run(const wchar_t *program, const wchar_t *command, const wchar_t *directory, HANDLE output, DWORD *code) {
    HANDLE input = null_device(GENERIC_READ), target = INVALID_HANDLE_VALUE;
    if (output) {
        if (!DuplicateHandle(GetCurrentProcess(), output, GetCurrentProcess(), &target, 0, TRUE, DUPLICATE_SAME_ACCESS))
            target = INVALID_HANDLE_VALUE;
    } else {
        target = null_device(GENERIC_WRITE);
    }
    PROCESS_INFORMATION process = {0};
    int ok = input != INVALID_HANDLE_VALUE && target != INVALID_HANDLE_VALUE ? spawn(program, command, directory, input, target, &process)
                                                                            : deku_fail("Cannot prepare helper process handles");
    if (input != INVALID_HANDLE_VALUE) CloseHandle(input);
    if (target != INVALID_HANDLE_VALUE) CloseHandle(target);
    if (!ok) return 0;
    WaitForSingleObject(process.hProcess, INFINITE);
    *code = 1;
    GetExitCodeProcess(process.hProcess, code);
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return 1;
}

static int capture(const wchar_t *program, const wchar_t *command, char **data, size_t *length) {
    SECURITY_ATTRIBUTES security = {sizeof security, NULL, TRUE};
    HANDLE read_end, write_end, input = null_device(GENERIC_READ);
    *data = NULL; *length = 0;
    if (input == INVALID_HANDLE_VALUE) return deku_fail("Cannot prepare helper process handles");
    if (!CreatePipe(&read_end, &write_end, &security, 0)) { CloseHandle(input); return deku_fail("Cannot create a helper pipe"); }
    SetHandleInformation(read_end, HANDLE_FLAG_INHERIT, 0);
    PROCESS_INFORMATION process = {0};
    int ok = spawn(program, command, NULL, input, write_end, &process);
    CloseHandle(write_end);
    CloseHandle(input);
    char *buffer = ok ? malloc(MAX_LISTING + 1) : NULL;
    if (ok && !buffer) ok = deku_fail("Not enough memory");
    size_t used = 0;
    while (ok) {
        DWORD read = 0;
        if (used == MAX_LISTING) { ok = deku_fail("Archive listing is too large"); break; }
        if (!ReadFile(read_end, buffer + used, (DWORD)(MAX_LISTING - used), &read, NULL) || !read) break;
        used += read;
    }
    CloseHandle(read_end);
    if (process.hProcess) {
        if (!ok) TerminateProcess(process.hProcess, 1);
        WaitForSingleObject(process.hProcess, INFINITE);
        DWORD code = 1;
        GetExitCodeProcess(process.hProcess, &code);
        if (ok && code) ok = deku_fail("Windows tar.exe could not read the archive");
        CloseHandle(process.hThread);
        CloseHandle(process.hProcess);
    }
    if (!ok) { free(buffer); return 0; }
    buffer[used] = 0;
    *data = buffer; *length = used;
    return 1;
}

static int system_tar(wchar_t *tar) {
    UINT length = GetSystemDirectoryW(tar, DEKU_PATH);
    if (!length || length > DEKU_PATH - 16) return deku_fail("Cannot locate the Windows system folder");
    wcscat(tar, L"\\tar.exe");
    return deku_regular_file(tar) ? 1 : deku_fail("Windows tar.exe is required (Windows 10 version 1803 or newer)");
}

int deku_extract(const wchar_t *archive, const wchar_t *destination, const deku_listing_rules *rules) {
    wchar_t *tar = malloc(DEKU_PATH * sizeof *tar), *command = malloc(DEKU_PATH * sizeof *command);
    char *names = NULL, *details = NULL;
    size_t names_length = 0, details_length = 0;
    int ok = tar && command ? system_tar(tar) : deku_fail("Not enough memory");
    if (ok) ok = swprintf(command, DEKU_PATH, L"\"%ls\" -tf \"%ls\"", tar, archive) > 0 && capture(tar, command, &names, &names_length);
    if (ok) ok = swprintf(command, DEKU_PATH, L"\"%ls\" -tvf \"%ls\"", tar, archive) > 0 && capture(tar, command, &details, &details_length);
    if (ok) {
        const char *problem = deku_check_listing(names, names_length, details, details_length, rules);
        if (problem) ok = deku_fail(problem);
    }
    if (ok && !CreateDirectoryW(destination, NULL) && GetLastError() != ERROR_ALREADY_EXISTS)
        ok = deku_fail_code("Cannot create the extraction folder", GetLastError());
    DWORD code = 1;
    if (ok) ok = swprintf(command, DEKU_PATH, L"\"%ls\" -xf \"%ls\" -C \"%ls\"", tar, archive, destination) > 0
                 && deku_run(tar, command, NULL, NULL, &code);
    if (ok && code) ok = deku_fail("Windows tar.exe could not extract the archive");
    free(names); free(details); free(tar); free(command);
    return ok;
}
