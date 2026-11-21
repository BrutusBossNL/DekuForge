// Native file, digest, process and archive helpers shared by DekuForge.exe,
// DekuForge-Setup.exe and DekuForge-Uninstall.exe. No script host is used.
#ifndef DEKUFORGE_NATIVE_H
#define DEKUFORGE_NATIVE_H
#include <windows.h>
#include "archive_check.h"

#define DEKU_PATH 32768

// Last failure reason in English, kept per thread until the next failure.
const char *deku_error(void);
int deku_fail(const char *message);
int deku_fail_code(const char *message, DWORD code);

int deku_join(wchar_t *output, const wchar_t *left, const wchar_t *right);
int deku_regular_file(const wchar_t *path);
// Full path without a trailing separator.
int deku_full_path(const wchar_t *input, wchar_t *output);
// Requires path inside root and no reparse point from path up to and including root.
int deku_owned_path(const wchar_t *root, const wchar_t *path);
int deku_sha256_bytes(const void *data, size_t size, char hex[65]);
int deku_sha256_file(const wchar_t *path, char hex[65]);
int deku_write_file(const wchar_t *path, const void *data, size_t size, DWORD disposition);
// Removes an owned tree; refuses to follow or remove reparse points.
int deku_remove_tree(const wchar_t *path);
// Runs a hidden program with stdin from NUL and stdout/stderr to `output`
// (NULL discards output). Only those handles are inherited. Waits for exit.
int deku_run(const wchar_t *program, const wchar_t *command, const wchar_t *directory, HANDLE output, DWORD *code);
// Validates both bsdtar listings, then extracts with Windows tar.exe.
int deku_extract(const wchar_t *archive, const wchar_t *destination, const deku_listing_rules *rules);

#endif
