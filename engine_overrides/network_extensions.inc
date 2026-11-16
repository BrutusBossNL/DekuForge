// Original offline socket facade. Event descriptors remain functional because
// the game's workers also use the socket layer for local wakeups.
typedef struct { int id; uint32_t flags; uint64_t value; } df_event_counter;
static df_event_counter df_counters[64];
static PlatMutex df_net_lock = PLAT_MUTEX_INIT;
static PlatCond df_net_changed = PLAT_COND_INIT;
static int df_next_descriptor = 16384, df_net_initialized;
static _Thread_local int df_net_errno;

static df_event_counter *df_counter(int descriptor) {
    for (unsigned i = 0; i < 64; i++)
        if (df_counters[i].id == descriptor && descriptor >= 16384) return &df_counters[i];
    return NULL;
}
static void df_net_fail(Cpu *c, int error) { df_net_errno = error; ret_x(c, UINT64_MAX); }
static void df_net_init(Cpu *c) {
    plat_mutex_lock(&df_net_lock); df_net_initialized = 1; plat_mutex_unlock(&df_net_lock);
    ret_x(c, 0);
}
static void df_net_finish(Cpu *c) {
    plat_mutex_lock(&df_net_lock);
    df_net_initialized = 0;
    memset(df_counters, 0, sizeof df_counters);
    plat_cond_broadcast(&df_net_changed);
    plat_mutex_unlock(&df_net_lock);
    ret_x(c, 0);
}
static void df_net_ready(Cpu *c) {
    plat_mutex_lock(&df_net_lock); int value = df_net_initialized; plat_mutex_unlock(&df_net_lock);
    ret_x(c, value);
}
// Called with the counter lock held. Reacquire the virtual CPU only after
// releasing the host lock, so a runnable guest cannot deadlock its producer.
static void df_net_wait(uint64_t ns, int forever) {
    int away = kern_core_away();
    if (forever) plat_cond_wait(&df_net_changed, &df_net_lock);
    else plat_cond_wait_ns(&df_net_changed, &df_net_lock, ns);
    plat_mutex_unlock(&df_net_lock);
    kern_core_back(&away);
    plat_mutex_lock(&df_net_lock);
}
static void df_event_create(Cpu *c) {
    uint64_t initial = arg_x(c, 0);
    uint32_t flags = (uint32_t)arg_x(c, 1);
    // The guest wakeup factory passes 6 for nonblocking + close-on-exec;
    // these are SDK enum bits, not Linux's 0x800/0x80000 constants.
    // Keep the verified combinations explicit until individual bits are verified.
    if (initial == UINT64_MAX || (flags != 0 && flags != 1 && flags != 6 && flags != 7)) { df_net_fail(c, 22); return; }
    plat_mutex_lock(&df_net_lock);
    for (unsigned i = 0; i < 64; i++) if (!df_counters[i].id) {
        if (df_next_descriptor == INT32_MAX) rt_fatal("Event descriptor identity exhausted");
        int id = df_next_descriptor++;
        df_counters[i] = (df_event_counter){id, flags, initial};
        plat_mutex_unlock(&df_net_lock);
        ret_x(c, id);
        return;
    }
    plat_mutex_unlock(&df_net_lock);
    df_net_fail(c, 24);
}
static void df_event_write(Cpu *c) {
    int fd = (int)arg_x(c, 0);
    uint64_t increment = arg_x(c, 1);
    if (increment == UINT64_MAX) { df_net_fail(c, 22); return; }
    plat_mutex_lock(&df_net_lock);
    for (;;) {
        df_event_counter *counter = df_counter(fd);
        if (!counter) { plat_mutex_unlock(&df_net_lock); df_net_fail(c, 9); return; }
        if (increment <= UINT64_MAX - 1 - counter->value) {
            counter->value += increment;
            plat_cond_broadcast(&df_net_changed);
            plat_mutex_unlock(&df_net_lock);
            ret_x(c, 0); return;
        }
        if ((counter->flags & 6) == 6) { plat_mutex_unlock(&df_net_lock); df_net_fail(c, 35); return; }
        df_net_wait(0, 1);
    }
}
static void df_event_read(Cpu *c) {
    int fd = (int)arg_x(c, 0);
    uint64_t *output = arg_p(c, 1);
    if (!output) { df_net_fail(c, 22); return; }
    plat_mutex_lock(&df_net_lock);
    for (;;) {
        df_event_counter *counter = df_counter(fd);
        if (!counter) { plat_mutex_unlock(&df_net_lock); df_net_fail(c, 9); return; }
        if (counter->value) {
            uint64_t value = counter->flags & 1 ? 1 : counter->value;
            counter->value -= value;
            plat_cond_broadcast(&df_net_changed);
            plat_mutex_unlock(&df_net_lock);
            *output = value;
            ret_x(c, 0); return;
        }
        if ((counter->flags & 6) == 6) { plat_mutex_unlock(&df_net_lock); df_net_fail(c, 35); return; }
        df_net_wait(0, 1);
    }
}
static void df_socket_close(Cpu *c) {
    plat_mutex_lock(&df_net_lock);
    df_event_counter *counter = df_counter((int)arg_x(c, 0));
    int valid = counter != NULL;
    if (valid) { memset(counter, 0, sizeof *counter); plat_cond_broadcast(&df_net_changed); }
    plat_mutex_unlock(&df_net_lock);
    if (valid) ret_x(c, 0); else df_net_fail(c, 9);
}
typedef struct { int32_t fd; int16_t events, revents; } df_poll_descriptor;
static void df_socket_poll(Cpu *c) {
    df_poll_descriptor *fds = arg_p(c, 0);
    uint64_t count = arg_x(c, 1);
    int32_t milliseconds = (int32_t)arg_x(c, 2);
    if (count > 64 || (count && !fds)) { df_net_fail(c, 22); return; }
    uint64_t end = plat_now_ns() + (milliseconds > 0 ? (uint64_t)milliseconds * 1000000 : 0);
    plat_mutex_lock(&df_net_lock);
    for (;;) {
        int ready = 0;
        for (uint64_t i = 0; i < count; i++) {
            df_event_counter *counter = df_counter(fds[i].fd);
            fds[i].revents = 0;
            if (fds[i].fd < 0) continue;
            if (!counter) fds[i].revents = 0x20; // POLLNVAL
            else {
                if (counter->value && (fds[i].events & 1)) fds[i].revents |= 1;
                if (counter->value < UINT64_MAX - 1 && (fds[i].events & 4)) fds[i].revents |= 4;
            }
            ready += fds[i].revents != 0;
        }
        uint64_t now = plat_now_ns();
        if (ready || (!milliseconds) || (milliseconds > 0 && now >= end)) {
            plat_mutex_unlock(&df_net_lock); ret_x(c, ready); return;
        }
        df_net_wait(milliseconds > 0 ? end - now : 0, milliseconds < 0);
    }
}
static void df_socket_unavailable(Cpu *c) { df_net_fail(c, 50); } // BSD ENETDOWN
static void df_socket_bad_descriptor(Cpu *c) { df_net_fail(c, 9); }
static void df_socket_errno(Cpu *c) { ret_x(c, df_net_errno); }
static void df_socket_set_errno(Cpu *c) { df_net_errno = (int)arg_x(c, 0); }
static void df_resolve_name(Cpu *c) {
    if (arg_p(c, 3)) *(void **)arg_p(c, 3) = NULL;
    ret_x(c, 8); // EAI_NONAME
}
static void df_free_address(Cpu *c) { (void)c; }
static void df_resolve_message(Cpu *c) { ret_x(c, (uintptr_t)"Network unavailable in offline runtime"); }
HOST_OVERRIDE("_ZN2nn6socket10InitializeERKNS0_6ConfigE", df_net_init);
HOST_OVERRIDE("_ZN2nn6socket8FinalizeEv", df_net_finish);
HOST_OVERRIDE("_ZN2nn6socket13IsInitializedEv", df_net_ready);
HOST_OVERRIDE("_ZN2nn6socket7EventFdEmNS0_12EventFdFlagsE", df_event_create);
HOST_OVERRIDE("_ZN2nn6socket11EventFdReadEiPm", df_event_read);
HOST_OVERRIDE("_ZN2nn6socket12EventFdWriteEim", df_event_write);
HOST_OVERRIDE("_ZN2nn6socket10SetSockOptEiNS0_5LevelENS0_6OptionEPKvj", df_socket_bad_descriptor);
HOST_OVERRIDE("nnsocketSocket", df_socket_unavailable);
HOST_OVERRIDE("nnsocketClose", df_socket_close);
HOST_OVERRIDE("nnsocketPoll", df_socket_poll);
HOST_OVERRIDE("nnsocketGetLastErrno", df_socket_errno);
HOST_OVERRIDE("nnsocketSetLastErrno", df_socket_set_errno);
HOST_OVERRIDE("nnsocketGetAddrInfo", df_resolve_name);
HOST_OVERRIDE("nnsocketFreeAddrInfo", df_free_address);
HOST_OVERRIDE("nnsocketGAIStrError", df_resolve_message);
HOST_OVERRIDE("nnsocketConnect", df_socket_bad_descriptor);
HOST_OVERRIDE("nnsocketBind", df_socket_bad_descriptor);
HOST_OVERRIDE("nnsocketListen", df_socket_bad_descriptor);
HOST_OVERRIDE("nnsocketAccept", df_socket_bad_descriptor);
HOST_OVERRIDE("nnsocketRecv", df_socket_bad_descriptor);
HOST_OVERRIDE("nnsocketSend", df_socket_bad_descriptor);
HOST_OVERRIDE("nnsocketSetSockOpt", df_socket_bad_descriptor);
HOST_OVERRIDE("nnsocketGetSockOpt", df_socket_bad_descriptor);
HOST_OVERRIDE("nnsocketShutdown", df_socket_bad_descriptor);

// Offline certificate discovery: an empty, terminated list. No TLS connection
// or handshake is exposed, and no certificate verification can be bypassed.
static void df_tls_local(Cpu *c) { ret_x(c, 0); }
static void df_tls_list_size(Cpu *c) {
    if (!arg_p(c, 0)) rt_fatal("Null certificate list-size output");
    *(uint32_t *)arg_p(c, 0) = 64;
    ret_x(c, 0);
}
static void df_tls_empty_list(Cpu *c) {
    if (!arg_p(c, 0) || !arg_p(c, 1) || arg_x(c, 2) < 64)
        rt_fatal("Invalid empty certificate-list buffer");
    memset(arg_p(c, 1), 0, 64);
    *(void **)arg_p(c, 0) = arg_p(c, 1);
    ret_x(c, 0);
}
HOST_OVERRIDE("_ZN2nn3ssl10InitializeEv", df_tls_local);
HOST_OVERRIDE("_ZN2nn3ssl8FinalizeEv", df_tls_local);
HOST_OVERRIDE("_ZN2nn3ssl14BuiltInManager28GetBuiltInCertificateBufSizeEPjPNS0_15CaCertificateIdEj", df_tls_list_size);
HOST_OVERRIDE("_ZN2nn3ssl14BuiltInManager22GetBuiltInCertificatesEPPNS0_26BuiltInCertificateInfoBaseEPhjPNS0_15CaCertificateIdEj", df_tls_empty_list);
static void df_network_environment(Cpu *c) {
    if (!arg_p(c, 0)) rt_fatal("Null network environment output");
    const char environment[8] = "lp1";
    memcpy(arg_p(c, 0), environment, sizeof environment);
    ret_x(c, 0);
}
static void df_network_name(Cpu *c) {
    if (!arg_p(c, 0) || !arg_p(c, 1)) rt_fatal("Null network name");
    // Preserve the requested hostname; DNS lookup still reports offline.
    memmove(arg_p(c, 0), arg_p(c, 1), 256);
    ret_x(c, 0);
}
HOST_OVERRIDE("_ZN2nn3nsd24GetEnvironmentIdentifierEPNS0_21EnvironmentIdentifierE", df_network_environment);
HOST_OVERRIDE("_ZN2nn3nsd9ResolveExEPNS0_4FqdnERKS1_", df_network_name);
