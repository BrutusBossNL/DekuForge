#pragma once

enum { DF_OPT_WORLD = 707, DF_WORLD_SKULL = 1, DF_WORLD_HEART = 2, DF_WORLD_GROTTO = 4,
       DF_WORLD_CHEST = 8, DF_WORLD_BEAN = 16, DF_WORLD_FAIRY = 32, DF_WORLD_UPGRADE = 64 };

#ifdef DF_WORLD_HOST
/* Native map data derives from BrutusBossNL's scoped MIT marker additions.
 * All progression stays in the game. These callbacks only change map rendering. */
typedef struct {
    uint64_t id;
    uint32_t category, flags, conditions, hash[4], pad;
} DfWorldEntry;
_Static_assert(sizeof(DfWorldEntry) == 40, "unexpected map metadata layout");

static DfWorldEntry df_world_entries[2048];
static uint64_t df_world_night[1000];
static unsigned df_world_count, df_world_night_count;

static unsigned df_world_file(const char *base, const char *name, const char *magic,
                              void *entries, size_t stride, unsigned capacity) {
    char path[1024], head[8];
    unsigned count;
    const int length = snprintf(path, sizeof(path), "%s/%s", base, name);
    if (length < 0 || (size_t)length >= sizeof(path)) return 0;
    FILE *file = fopen(path, "rb");
    if (!file) return 0;
    const int ok = fread(head, 1, sizeof(head), file) == sizeof(head) && !memcmp(head, magic, sizeof(head)) &&
                   fread(&count, 4, 1, file) == 1 && count && count <= capacity &&
                   fread(entries, stride, count, file) == count && fgetc(file) == EOF;
    fclose(file);
    return ok ? count : 0;
}

static void df_world_init(void) {
    const char *directory = getenv("DEKUFORGE_WORLD_DATA");
    if (!directory || !*directory) return;
    const unsigned entries = df_world_file(directory, "extra-world.bin", "NXWEX001",
                                           df_world_entries, sizeof(DfWorldEntry), 2048);
    const unsigned nights = df_world_file(directory, "skull-night.bin", "NXWNT001",
                                          df_world_night, sizeof(uint64_t), 1000);
    for (unsigned i = 0; i < entries; ++i) {
        const DfWorldEntry *entry = &df_world_entries[i];
        if (!entry->id || (i && entry->id <= df_world_entries[i-1].id) || entry->category < 1 ||
            entry->category > 4 || entry->flags > 3 || entry->conditions > 2) return;
    }
    for (unsigned i = 0; i < nights; ++i)
        if (!df_world_night[i] || (i && df_world_night[i] <= df_world_night[i-1])) return;
    if (!entries || !nights) return;
    df_world_count = entries;
    df_world_night_count = nights;
    hos_log("world: %u extra locations and %u night-only hints ready", entries, nights);
}

static unsigned df_world_word(Ctx *c, uint64_t address) {
    return hos_mem_region(address, 4) ? recomp_load32(c, address) : 0;
}

static unsigned df_world_byte(Ctx *c, uint64_t address) {
    return hos_mem_region(address, 1) ? recomp_load8(c, address) : 0;
}

static int df_world_context(Ctx *c, uint64_t map) {
    return df_world_count && df_pointer(c, map) == 0x84c019c8ULL;
}

static unsigned df_world_options(void) {
    int rx_option(int id, int otherwise);
    return (unsigned)rx_option(DF_OPT_WORLD, 0);
}

static const DfWorldEntry *df_world_lookup(uint64_t id) {
    unsigned low = 0, high = df_world_count;
    while (low < high) {
        const unsigned mid = low + (high - low) / 2;
        if (df_world_entries[mid].id < id) low = mid + 1;
        else high = mid;
    }
    return low < df_world_count && df_world_entries[low].id == id ? &df_world_entries[low] : NULL;
}

static int df_world_nocturnal(uint64_t id) {
    unsigned low = 0, high = df_world_night_count;
    while (low < high) {
        const unsigned mid = low + (high - low) / 2;
        if (df_world_night[mid] < id) low = mid + 1;
        else high = mid;
    }
    return low < df_world_night_count && df_world_night[low] == id;
}

static unsigned df_world_collectible(unsigned kind) {
    return kind == 6 ? DF_WORLD_HEART : kind == 7 ? DF_WORLD_SKULL : 0;
}

void df_guest_world_master(Ctx *c) {
    if (df_world_context(c, c->x[19]) && (df_world_options() & (DF_WORLD_SKULL | DF_WORLD_HEART)))
        c->x[8] = 1;
}

void df_guest_world_visibility(Ctx *c) {
    if (!df_world_context(c, c->x[19])) return;
    if (df_world_options() & df_world_collectible((unsigned)c->x[9])) c->x[9] = 8;
    else if (!df_world_byte(c, c->x[19] + 0x45c)) {
        c->x[9] = 6;
        c->x[8] = 1;
    }
}

static int df_world_skull_collected(Ctx *c, uint64_t id) {
    const uint64_t manager = df_pointer(c, 0x84ea42a8ULL);
    const uint64_t table = df_pointer(c, manager + 0xc60);
    const unsigned count = df_world_word(c, manager + 0xc58);
    if (!id || !table || !count || count > 1000000 || !hos_mem_region(table, 16ull * count)) return 0;
    unsigned low = 0, high = count;
    while (low < high) {
        const unsigned mid = low + (high - low) / 2;
        if (recomp_load64(c, table + 16ull * mid) < id) low = mid + 1;
        else high = mid;
    }
    const uint64_t entry = table + 16ull * low;
    return low < count && recomp_load64(c, entry) == id && (recomp_load8(c, entry + 12) & 1);
}

static void df_world_frame(Ctx *c, float value) {
    memcpy(&c->vreg[0][0], &value, sizeof(value));
}

void df_guest_world_style(Ctx *c) {
    const unsigned kind = (unsigned)c->x[9];
    if (!df_world_context(c, c->x[19]) || !(df_world_options() & df_world_collectible(kind))) return;
    const uint64_t stack = c->x[31];
    const uint64_t id = df_pointer(c, stack);
    const int checked = kind == 6 ? (df_projectile_call(c, 0x80226290ULL, &stack, 1) & 1) :
                        df_world_skull_collected(c, id);
    const float frame = kind == 6 ? (checked ? 0.f : 2.f) : df_world_nocturnal(id) ?
                        (checked ? 5.f : 4.f) : (checked ? 1.f : 3.f);
    df_world_frame(c, frame);
}

static unsigned df_world_facility_mask(unsigned category) {
    const unsigned bits[] = {0, DF_WORLD_GROTTO, DF_WORLD_BEAN, DF_WORLD_FAIRY, DF_WORLD_UPGRADE};
    return bits[category];
}

static const DfWorldEntry *df_world_facility(Ctx *c, uint64_t map, uint64_t index) {
    const unsigned count = df_world_word(c, map + 0x370);
    if (index >= count || index >= df_world_word(c, map + 0x1e0) || count > 2048) return NULL;
    const uint64_t base = df_pointer(c, map + 0x1e8);
    const DfWorldEntry *entry = base ? df_world_lookup(df_pointer(c, base + index * 0xc0)) : NULL;
    return entry && !entry->flags ? entry : NULL;
}

static int df_world_completed(Ctx *c, const DfWorldEntry *entry) {
    const uint64_t manager = df_pointer(c, df_pointer(c, OOT_GAMEDATA_SLOT));
    if (!entry->conditions) return 0;
    for (unsigned i = 0; i < entry->conditions; ++i) {
        const uint64_t flag = df_resource_entry(c, manager, entry->hash[2*i], entry->hash[2*i+1], DF_DATA_BOOL);
        if (!flag || !(recomp_load8(c, flag) & 1)) return 0;
    }
    return 1;
}

void df_guest_world_chests(Ctx *c) {
    const uint64_t map = c->x[19], index = c->x[23];
    if (!df_world_context(c, map)) return;
    const uint64_t base = df_pointer(c, map + 0x188);
    const DfWorldEntry *entry = base && index < df_world_word(c, map + 0x358) &&
        index < df_world_word(c, map + 0x180) ? df_world_lookup(df_pointer(c, base + index * 32)) : NULL;
    const unsigned mask = df_world_options();
    if ((mask & DF_WORLD_CHEST) || ((mask & DF_WORLD_UPGRADE) && entry && (entry->flags & 1)))
        c->x[8] = c->x[9] = 1;
    else if (entry && (entry->flags & 2)) c->x[8] = c->x[9] = 0;
}

void df_guest_world_facility_position(Ctx *c) {
    const uint64_t map = c->x[19], index = c->x[24];
    if (!df_world_context(c, map)) return;
    const DfWorldEntry *entry = df_world_facility(c, map, index);
    if (!entry || (df_world_options() & df_world_facility_mask(entry->category)) ||
        index >= df_world_word(c, map + 0xe0)) return;
    const uint64_t base = df_pointer(c, map + 0xe8);
    const uint64_t element = base ? df_pointer(c, base + index * 8) : 0;
    const uint64_t parent = df_pointer(c, map + 0x58);
    if (element && parent) {
        const uint64_t params[] = {element, parent};
        df_projectile_call(c, 0x802295e0ULL, params, 2);
    }
}

void df_guest_world_facility_style(Ctx *c) {
    const uint64_t map = c->x[19];
    if (!df_world_context(c, map)) return;
    const DfWorldEntry *entry = df_world_facility(c, map, c->x[24]);
    if (entry) df_world_frame(c, 39.f + 2.f * (entry->category - 1) + df_world_completed(c, entry));
}
#endif
