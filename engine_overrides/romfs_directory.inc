// Original read-only directory snapshots over the verified RomFS index.
static void df_directory_entry(Listing *list, const char *prefix, const char *path, uint64_t size) {
    size_t length = strlen(prefix);
    if (strncmp(path, prefix, length)) return;
    const char *child = path + length;
    const char *slash = strchr(child, '/');
    size_t n = slash ? (size_t)(slash - child) : strlen(child);
    if (!n || n > 768) return;
    char name[769];
    memcpy(name, child, n);
    name[n] = 0;
    int kind = slash ? PLAT_FS_DIR : PLAT_FS_FILE;
    for (int i = 0; i < list->n; i++) {
        if (!strcmp(list->e[i].name, name)) {
            if (list->e[i].kind != kind) rt_fatal("RomFS directory/file collision");
            list->e[i].size = slash ? 0 : size;
            return;
        }
    }
    listing_add(name, kind, slash ? 0 : size, list);
}

static int df_directory_compare(const void *a, const void *b) {
    return strcmp(((const Listed *)a)->name, ((const Listed *)b)->name);
}

static uint32_t df_open_romfs_directory(uint64_t *out, const char *path, int mode) {
    if (!out || mode < 1 || mode > 3) return FS_R_INVALID_ARGUMENT;
    const char *relative = strchr(path, ':');
    if (!relative || relative[1] != '/') return FS_R_INVALID_PATH;
    relative++;
    while (*relative == '/') relative++;
    char prefix[PATH_CAP];
    size_t n = strlen(relative);
    if (n + 2 > sizeof prefix) return FS_R_INVALID_PATH;
    memcpy(prefix, relative, n + 1);
    while (n && prefix[n - 1] == '/') prefix[--n] = 0;
    if (n && !romfs_path_valid_relative(prefix)) return FS_R_INVALID_PATH;
    if (n) { prefix[n++] = '/'; prefix[n] = 0; }
    Listing snapshot = {0};
    // Sorted file index: only scan the range with the directory prefix.
    uint64_t lo = 0, hi = romfs_file_count();
    while (lo < hi) {
        uint64_t mid = lo + (hi - lo) / 2;
        if (strcmp(romfs_entry(mid, NULL, NULL), prefix) < 0) lo = mid + 1;
        else hi = mid;
    }
    for (uint64_t i = lo; i < romfs_file_count(); i++) {
        uint64_t size;
        const char *entry = romfs_entry(i, NULL, &size);
        if (strncmp(entry, prefix, n)) break;
        df_directory_entry(&snapshot, prefix, entry, size);
    }
    // Overlay files can add children or replace existing file sizes.
    for (size_t i = 0; i < romfs_overlay_count(); i++) {
        const char *file;
        uint64_t size;
        int added;
        const char *entry = romfs_overlay(i, &file, &size, &added);
        df_directory_entry(&snapshot, prefix, entry, size);
    }
    if (!snapshot.n && n) { listing_free(snapshot.e, snapshot.n); return FS_R_PATH_NOT_FOUND; }
    if (snapshot.n > 1) qsort(snapshot.e, (size_t)snapshot.n, sizeof *snapshot.e, df_directory_compare);
    plat_mutex_lock(&lock);
    for (int i = 0; i < NDIRS; i++) if (!dirs[i].used) {
        dirs[i] = (Dir){snapshot.e, snapshot.n, 0, mode, 1};
        *out = DIR_BASE + (uint64_t)i;
        plat_mutex_unlock(&lock);
        return 0;
    }
    plat_mutex_unlock(&lock);
    listing_free(snapshot.e, snapshot.n);
    return FS_R_INVALID;
}
