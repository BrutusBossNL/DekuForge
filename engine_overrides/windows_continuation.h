// Capture a live Windows x64 caller using its unwind metadata.
#pragma once
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>

static int df_stack_region(uintptr_t address, MEMORY_BASIC_INFORMATION *region) {
    return VirtualQuery((void *)address, region, sizeof *region) == sizeof *region &&
           region->State == MEM_COMMIT && !(region->Protect & (PAGE_GUARD | PAGE_NOACCESS));
}

static __attribute__((noinline)) int df_capture_caller(CONTEXT *saved, uintptr_t function) {
    DWORD64 target_base = 0;
    PRUNTIME_FUNCTION target = RtlLookupFunctionEntry(function, &target_base, NULL);
    if (!target) return 0;
    CONTEXT walk;
    RtlCaptureContext(&walk);
    for (unsigned depth = 0; depth < 256 && walk.Rip && walk.Rsp; ++depth) {
        DWORD64 image = 0;
        PRUNTIME_FUNCTION entry = RtlLookupFunctionEntry(walk.Rip, &image, NULL);
        if (entry && image == target_base && entry->BeginAddress == target->BeginAddress) {
            *saved = walk;
            return 1;
        }
        DWORD64 previous = walk.Rsp;
        if (entry) {
            PVOID handler_data;
            DWORD64 frame;
            RtlVirtualUnwind(UNW_FLAG_NHANDLER, image, walk.Rip, entry, &walk,
                             &handler_data, &frame, NULL);
        } else {
            MEMORY_BASIC_INFORMATION region;
            if (!df_stack_region(walk.Rsp, &region) ||
                walk.Rsp + sizeof(uintptr_t) > (uintptr_t)region.BaseAddress + region.RegionSize) return 0;
            walk.Rip = *(uintptr_t *)walk.Rsp;
            walk.Rsp += sizeof(uintptr_t);
        }
        if (walk.Rsp <= previous) return 0;
    }
    return 0;
}
