// Pinned launcher runtime bootstrap shared by DekuForge.exe and the setup.
// It replaces the hidden PowerShell runtime bootstrap in shipped binaries.
#ifndef DEKUFORGE_RUNTIME_H
#define DEKUFORGE_RUNTIME_H
#include "native.h"

typedef enum { DEKU_RUNTIME_MISSING, DEKU_RUNTIME_READY, DEKU_RUNTIME_FOREIGN } deku_runtime_state;

deku_runtime_state deku_runtime_status(const wchar_t *root);
// Downloads, verifies and installs the pinned runtime at root\python\<id>.
// Writes local\python-path.txt and local\runtime-bootstrap.log.
int deku_prepare_runtime(const wchar_t *root);

#endif
