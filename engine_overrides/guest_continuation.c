// Guest nonlocal returns resume a live translated caller, not the dispatch table.
// Windows x64 implementation; other hosts must supply their own continuation ABI.
#ifdef _WIN32
#include "df_windows_continuation.h"
#include <stdlib.h>
#include "host.h"
#include "dispatch.h"
#include "platform/platform.h"

typedef struct DfContinuation {
    struct DfContinuation *next;
    uint64_t buffer;
    void *thread;
    uint64_t registers[12], stack, vectors[8];
    int host_depth;
    CONTEXT host;
} DfContinuation;

static DfContinuation *df_continuations;
static PlatMutex df_continuation_lock = PLAT_MUTEX_INIT;

static uintptr_t df_caller_function(uint64_t return_pc) {
    RtModule modules[16];
    int count = rt_linked_modules(modules, 16);
    uint64_t pc = return_pc - 4;
    for (int i = 0; i < count; ++i) {
        const RtModule *m = &modules[i];
        if (pc < m->base || pc >= m->base + m->size) continue;
        uint64_t lo = 0, hi = m->count;
        while (lo < hi) {
            uint64_t middle = lo + (hi - lo) / 2;
            if (m->addrs[middle] <= pc) lo = middle + 1;
            else hi = middle;
        }
        return lo ? (uintptr_t)m->fns[lo - 1] : 0;
    }
    return 0;
}

static void df_guest_setjmp(Cpu *cpu) {
    DfContinuation snapshot = {.buffer = cpu->x[0], .thread = cpu->thread, .stack = cpu->sp};
    if (cpu->thread) snapshot.host_depth = *kern_host_depth(cpu->thread) - !!kern_host_track;
    uintptr_t caller = df_caller_function(cpu->x[30]);
    if (!caller || !df_capture_caller(&snapshot.host, caller))
        rt_fatal("setjmp: cannot capture live caller at %#llx", (unsigned long long)cpu->x[30]);
    for (int i = 0; i < 12; ++i) snapshot.registers[i] = cpu->x[19 + i];
    for (int i = 0; i < 8; ++i) snapshot.vectors[i] = (uint64_t)cpu->v[8 + i];
    plat_mutex_lock(&df_continuation_lock);
    DfContinuation *entry = df_continuations;
    while (entry && (entry->buffer != snapshot.buffer || entry->thread != snapshot.thread)) entry = entry->next;
    if (!entry) {
        entry = malloc(sizeof *entry);
        if (!entry) rt_fatal("setjmp: cannot allocate continuation");
        entry->next = df_continuations;
        df_continuations = entry;
    }
    snapshot.next = entry->next;
    *entry = snapshot;
    plat_mutex_unlock(&df_continuation_lock);
    cpu->x[0] = 0;
}

static void df_guest_longjmp(Cpu *cpu) {
    // The destination context must not be on the stack that is being unwound.
    static _Thread_local DfContinuation destination;
    uint32_t value = (uint32_t)cpu->x[1];
    plat_mutex_lock(&df_continuation_lock);
    DfContinuation *entry = df_continuations;
    while (entry && (entry->buffer != cpu->x[0] || entry->thread != cpu->thread)) entry = entry->next;
    if (entry) destination = *entry;
    plat_mutex_unlock(&df_continuation_lock);
    if (!entry) rt_fatal("longjmp: no continuation for this guest thread and buffer");
    uintptr_t current_stack = (uintptr_t)&entry;
    MEMORY_BASIC_INFORMATION current_region, saved_region;
    if (destination.host.Rsp <= current_stack ||
        !df_stack_region(current_stack, &current_region) ||
        !df_stack_region(destination.host.Rsp, &saved_region) ||
        current_region.AllocationBase != saved_region.AllocationBase)
        rt_fatal("longjmp: destination is not on the current live stack");
    for (int i = 0; i < 12; ++i) cpu->x[19 + i] = destination.registers[i];
    for (int i = 0; i < 8; ++i)
        cpu->v[8 + i] = (cpu->v[8 + i] & ~(__uint128_t)UINT64_MAX) | destination.vectors[i];
    cpu->sp = destination.stack;
    if (cpu->thread) *kern_host_depth(cpu->thread) = destination.host_depth;
    cpu->x[0] = value ? value : 1;
    cpu->pc = cpu->x[30];
    RtlRestoreContext(&destination.host, NULL);
    __builtin_unreachable();
}

HOST_OVERRIDE("setjmp", df_guest_setjmp);
HOST_OVERRIDE("_setjmp", df_guest_setjmp);
HOST_OVERRIDE("longjmp", df_guest_longjmp);
HOST_OVERRIDE("_longjmp", df_guest_longjmp);
#endif
