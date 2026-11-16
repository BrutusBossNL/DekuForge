// Original multi-mount registry: every registered name exposes the same verified
// read-only application image. Registration and path lookup may run concurrently.
static char df_mounts[32][32];
static unsigned df_mount_count;
static PlatMutex df_mount_lock = PLAT_MUTEX_INIT;
static const char *df_romfs_relative(const char *path) {
    const char *relative = NULL;
    plat_mutex_lock_shared(&df_mount_lock);
    for (unsigned i = 0; i < df_mount_count && !relative; i++)
        relative = romfs_path_relative(df_mounts[i], path);
    plat_mutex_unlock_shared(&df_mount_lock);
    return relative;
}
int romfs_owns(const char *path) {
    if (!path) return 0;
    const char *separator = strchr(path, ':');
    if (!separator) return 0;
    size_t length = (size_t)(separator - path);
    int found = 0;
    plat_mutex_lock_shared(&df_mount_lock);
    for (unsigned i = 0; i < df_mount_count && !found; i++)
        found = strlen(df_mounts[i]) == length && !memcmp(df_mounts[i], path, length);
    plat_mutex_unlock_shared(&df_mount_lock);
    return found;
}
uint32_t romfs_mount(const char *name) {
    fs_init();
    if (!name || !romfs_path_valid_relative(name) || strlen(name) >= 32 || strchr(name, '/') || strchr(name, ':'))
        return FS_R_INVALID_PATH;
    plat_mutex_lock(&df_mount_lock);
    for (unsigned i = 0; i < df_mount_count; i++) if (!strcmp(name, df_mounts[i])) {
        plat_mutex_unlock(&df_mount_lock);
        return 0;
    }
    if (df_mount_count == 32) { plat_mutex_unlock(&df_mount_lock); return FS_R_INVALID; }
    strcpy(df_mounts[df_mount_count++], name);
    plat_mutex_unlock(&df_mount_lock);
    fs_trace("mount", name);
    return 0;
}
