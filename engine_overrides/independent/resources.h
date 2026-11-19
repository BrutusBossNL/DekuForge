#pragma once

/* GameData entries for the verified 1.1.1 program. Capacity and ownership
 * are read again at each refill, including after an upgrade or age change. */
#define DF_RESOURCE_ROWS(X) \
    X(RUPEES, "Refill rupees", 0xa77921d7u, 962, 0xe0010a50u, 976, 0, 0, 0) \
    X(BOMBS, "Refill bombs", 0xdb1bcd4fu, 1007, 0xe753508bu, 972, 0, 0, 0) \
    X(ARROWS, "Refill arrows", 0x518ec74bu, 1006, 0x418db791u, 971, 0, 0, 0) \
    X(BOMBCHUS, "Refill bombchus", 0xdf7c517au, 1011, 0xe753508bu, 972, 0x5ab49c8eu, 8852, 0) \
    X(NUTS, "Refill Deku nuts", 0xf30d9f54u, 1019, 0x735b00f7u, 973, 0, 0, 0) \
    X(SEEDS, "Refill Deku seeds", 0x5fadf7fcu, 1020, 0xae8cc742u, 974, 0, 0, 0) \
    X(STICKS, "Refill Deku sticks", 0xb9494411u, 1021, 0x457616b0u, 975, 0, 0, 0) \
    X(BEANS, "Refill magic beans", 0xb003124du, 1032, 0, 0, 0x6d39c600u, 8896, 10) \
    X(SCRUB, "Refill Scrub seeds", 0x600e29ebu, 1057, 0, 0, 0xcfbb16f6u, 8934, 30)

#define DF_RESOURCE_ENUM(id, label, ...) DF_RESOURCE_##id,
enum { DF_RESOURCE_ROWS(DF_RESOURCE_ENUM) DF_RESOURCE_COUNT, DF_RESOURCE_HEARTS = DF_RESOURCE_COUNT, DF_RESOURCE_TIMER,
       DF_RESOURCE_MAGIC, DF_RESOURCE_FISH, DF_RESOURCE_OPTIONS };
#undef DF_RESOURCE_ENUM
enum { DF_OPT_RESOURCE_MASK = 702 };
enum { DF_BOTTLES = 5, DF_BOTTLE_TYPES = 13, DF_OPT_BOTTLE_EDITS = 703, DF_OPT_BOTTLE_REPORT = 720 };
enum { DF_OPT_SPIN = 704, DF_SPIN_INSTANT = 4 };

#ifdef DF_RESOURCE_HOST
enum { DF_DATA_COUNT = 0xd0, DF_DATA_BOOL = 0x10, DF_DATA_FLOAT = 0x190, DF_DATA_ENUM = 0x250 };

static uint64_t df_resource_entry(Ctx *c, uint64_t mgr, uint32_t hash,
                                  uint32_t expected, int offset) {
    const int boolean = offset == DF_DATA_BOOL;
    const uint32_t count = boolean ? 11292 : offset == DF_DATA_FLOAT ? 89 : offset == DF_DATA_ENUM ? 130 : 1259;
    const uint32_t stride = boolean ? 24 : offset == DF_DATA_ENUM ? 56 : 40;
    const uint32_t value_offset = boolean ? 22 : 28;
    if (!mgr || !hos_mem_region(mgr + offset, 32) ||
        recomp_load32(c, mgr + offset) != count ||
        recomp_load32(c, mgr + offset + 28) != 2 * count || expected >= count)
        return 0;
    const uint64_t entries = recomp_load64(c, mgr + offset + 8);
    const uint64_t table = recomp_load64(c, mgr + offset + 16);
    if (!entries || !table || !hos_mem_region(table, 16 * count)) return 0;
    for (uint32_t probe = 0, slot = hash % (2 * count); probe < 2 * count;
         ++probe, slot = (slot + 1) % (2 * count)) {
        const uint64_t pair = table + 8 * slot;
        const uint32_t key = recomp_load32(c, pair);
        if (!key) break;
        if (key != hash) continue;
        if (recomp_load32(c, pair + 4) != expected) break;
        const uint64_t entry = entries + stride * expected;
        if (!hos_mem_region(entry, stride)) break;
        const uint64_t vtable = recomp_load64(c, entry);
        if (vtable < hos_image_base || vtable >= hos_image_end) break;
        return entry + value_offset;
    }
    return 0;
}

static uint64_t df_pointer(Ctx *c, uint64_t at) {
    return hos_mem_region(at, 8) ? recomp_load64(c, at) : 0;
}

static uint64_t df_jump_parameters(Ctx *c, uint64_t components) {
    const uint64_t board = df_pointer(c, components + 0xa8);
    if (!board || !hos_mem_region(board, 0x40)) return 0;
    const uint32_t count = recomp_load32(c, board + 0x30);
    const uint64_t entries = df_pointer(c, board + 0x38);
    if (!entries || !count || count > 4096 || !hos_mem_region(entries, 8 * count)) return 0;
    for (uint32_t low = 0, high = count; low < high;) {
        const uint32_t mid = low + (high - low) / 2;
        const uint64_t entry = df_pointer(c, entries + 8 * mid);
        if (!entry || !hos_mem_region(entry, 16)) return 0;
        const uint32_t key = recomp_load32(c, entry);
        if (key < 0x6b7e094au) low = mid + 1;
        else if (key > 0x6b7e094au) high = mid;
        else return df_pointer(c, df_pointer(c, entry + 8) + 0x150);
    }
    return 0;
}

void df_guest_air_jump(Ctx *c) {
    if (strcmp(hos_main_build_id, "e0f3ccfaf50065ae4ea01eb5aeb13b1a45da3348")) return;
    const uint64_t player = df_pointer(c, df_pointer(c, 0x84e571d0ULL) + 0x480);
    if (df_pointer(c, player) != 0x84b45e18ULL) return;
    const uint64_t components = df_pointer(c, player + 0x270);
    const uint64_t action = df_pointer(c, components + 0x358);
    if (df_pointer(c, action) != 0x84b6dfc0ULL) return;
    const uint64_t physics = df_pointer(c, components + 0x50);
    const uint64_t controller = df_pointer(c, physics + 0x20);
    const uint64_t character = df_pointer(c, controller + 0x10);
    const uint64_t motion = df_pointer(c, character + 8);
    const uint64_t state = df_pointer(c, motion + 0x30);
    if (!hos_mem_region(state, 0x4d) || df_pointer(c, state) != 0x84bbc298ULL ||
        df_pointer(c, state + 0x10) != character) return;
    const uint64_t parent = df_pointer(c, state + 0x30);
    const uint64_t params = df_jump_parameters(c, components);
    if (df_pointer(c, params) != 0x84b8d1a8ULL || !hos_mem_region(params + 0x334, 4) ||
        !hos_mem_region(parent + 0x20, 4)) return;
    const uint32_t bits = recomp_load32(c, params + 0x334);
    float impulse;
    memcpy(&impulse, &bits, sizeof(impulse));
    if (!(impulse > 0 && impulse <= 5)) return;
    recomp_store32(c, state + 0x3c, bits);
    recomp_store8(c, state + 0x4c, 1);
    recomp_store32(c, parent + 0x20, recomp_load32(c, parent + 0x20) | 2);
    hos_log("cheats: player jump impulse applied");
}

void df_guest_fishing_condition(Ctx *c) {
    int rx_option(int id, int otherwise);
    if (!(rx_option(DF_OPT_RESOURCE_MASK, 0) & (1 << DF_RESOURCE_FISH))) return;

    /* The battle sequence for both fish species has a dedicated condition
     * for immediate landing. Override only its evaluated result (w27). */
    static const char condition[] =
        "Work/BSA/ConditionContainer/Animal_Fish_Bass_IfImmediateGet.game__bsa__ConditionContainer.gyml";
    const uint64_t sequence = c->x[22];
    if (!hos_mem_region(sequence, 0x18)) return;
    const uint64_t config = recomp_load64(c, sequence + 0x10);
    if (!hos_mem_region(config, 0xbc) || !(recomp_load8(c, config + 0xbb) & 1)) return;
    const uint64_t path = recomp_load64(c, config + 0x90);
    if (!hos_mem_region(path, sizeof condition)) return;
    for (unsigned i = 0; i < sizeof condition; ++i)
        if (recomp_load8(c, path + i) != (unsigned char)condition[i]) return;
    c->x[27] = 1;
}

void df_guest_magic(Ctx *c) {
    int rx_option(int id, int otherwise);
    if (!(rx_option(DF_OPT_RESOURCE_MASK, 0) & (1 << DF_RESOURCE_MAGIC))) return;
    const uint64_t live = c->x[0];
    if (!hos_mem_region(live, 0x48) || recomp_load32(c, live + 0x38) != 0x76b18200u ||
        recomp_load32(c, live + 0x3c) != 0x12d63a97u || recomp_load32(c, live + 0x40) != 0x3afa3349u) return;
    const uint64_t manager = df_pointer(c, df_pointer(c, OOT_GAMEDATA_SLOT));
    const uint64_t entry = df_resource_entry(c, manager, 0x12d63a97u, 967, DF_DATA_COUNT);
    if (!entry) return;
    const uint32_t max = recomp_load32(c, entry);
    if (max && max <= 9999 && recomp_load32(c, live + 0x44) < max)
        recomp_store32(c, live + 0x44, max);
}

void df_guest_spin_charge(Ctx *c) {
    int rx_option(int id, int otherwise);
    if (!(rx_option(DF_OPT_SPIN, 0) & DF_SPIN_INSTANT)) return;
    static int logged;
    if (!__atomic_exchange_n(&logged, 1, __ATOMIC_RELAXED)) hos_log("cheats: instant magic spin charge applied");
    const float charge = 0.125f;
    memcpy(c->vreg[8], &charge, sizeof(charge));
}

void df_guest_spin_range(Ctx *c) {
    int rx_option(int id, int otherwise);
    const unsigned mode = (unsigned)rx_option(DF_OPT_SPIN, 0) & 3;
    if (!mode) return;
    const uint64_t weapon = c->x[20], sword = df_pointer(c, weapon + 0x18);
    const uint64_t actor = df_pointer(c, df_pointer(c, 0x84e571d0ULL) + 0x480);
    const uint64_t components = actor ? df_pointer(c, actor + 0x270) : 0;
    const uint64_t equipment = components ? df_pointer(c, components + 0x200) : 0;
    const uint64_t entry = equipment ? df_pointer(c, equipment + 0x28) : 0;
    if (!sword || !actor || df_pointer(c, actor) != 0x84b45e18ULL ||
        !hos_mem_region(equipment, 0x34) || !hos_mem_region(entry, 0x4c)) return;
    const uint32_t generation = recomp_load32(c, equipment + 0x30);
    if (generation == UINT32_MAX || recomp_load32(c, entry + 0x48) != generation ||
        df_pointer(c, entry + 0x40) != sword || df_pointer(c, df_pointer(c, sword + 0x270) + 0x458) != weapon) return;
    const uint64_t name = df_pointer(c, sword + 0x20);
    static const char prefix[] = "Weapon_Sword_";
    if (!hos_mem_region(name, sizeof(prefix)-1)) return;
    for (unsigned i = 0; i < sizeof(prefix)-1; ++i)
        if (recomp_load8(c, name + i) != (uint8_t)prefix[i]) return;
    float length, radius;
    memcpy(&length, c->vreg[0], sizeof(length));
    memcpy(&radius, c->vreg[1], sizeof(radius));
    if (!(length > -1 && length <= 20 && radius >= 1 && radius <= 20)) return;
    const float factor = 1.0f + (float)mode * 0.5f;
    static int logged;
    if (!__atomic_exchange_n(&logged, 1, __ATOMIC_RELAXED)) hos_log("cheats: sword spin range multiplier applied");
    length = (length + 1) * factor - 1;
    radius *= factor;
    memcpy(c->vreg[0], &length, sizeof(length));
    memcpy(c->vreg[1], &radius, sizeof(radius));
}

static void df_refill_hearts(Ctx *c, uint64_t actor, uint64_t manager) {
    if (!hos_mem_region(actor + 7184, 8)) return;
    const uint64_t life = recomp_load64(c, actor + 7184);
    if (!life || !hos_mem_region(life, 32)) return;
    const uint64_t vtable = 0x84b83438ULL;
    if (recomp_load64(c, life) != vtable || recomp_load32(c, life + 12) != 0x31ab5580u ||
        recomp_load64(c, life + 16) != vtable || recomp_load32(c, life + 28) != 0xfbe01da1u) return;
    const uint32_t value = recomp_load32(c, life + 8);
    const uint32_t capacity = recomp_load32(c, life + 24);
    const uint64_t saved_cap = df_resource_entry(c, manager, 0xfbe01da1u, 964, DF_DATA_COUNT);
    if (value && value < capacity && capacity >= 4 && capacity <= 160 && !(capacity % 4) &&
        saved_cap && recomp_load32(c, saved_cap) == capacity)
        recomp_store32(c, life + 8, capacity);
}

static void df_freeze_timer(Ctx *c, uint64_t manager, int enabled) {
    static uint64_t timer;
    static float held;
    const uint64_t running = enabled ? df_resource_entry(c, manager, 0xf0312188u, 10101, DF_DATA_BOOL) : 0;
    const uint64_t countdown = running && recomp_load8(c, running) == 1 ?
        df_resource_entry(c, manager, 0xdd49184au, 10100, DF_DATA_BOOL) : 0;
    const uint64_t slot = countdown && recomp_load8(c, countdown) == 1 ?
        df_resource_entry(c, manager, 0x9d350590u, 67, DF_DATA_FLOAT) : 0;
    if (!slot) {
        timer = 0;
        return;
    }
    uint32_t bits = recomp_load32(c, slot);
    float value;
    memcpy(&value, &bits, sizeof(value));
    if (!(value > 0 && value <= 216000)) {
        timer = 0;
        return;
    }
    if (timer != slot || value > held + 0.1f || held - value > 120.0f) {
        timer = slot;
        held = value;
    }
    memcpy(&bits, &held, sizeof(bits));
    recomp_store32(c, slot, bits);
    recomp_store32(c, slot + 4, bits);
}

static int df_bottle_update(Ctx *c, uint64_t manager, unsigned slot, unsigned choice) {
    const uint32_t owned[] = {0xf39ce410u, 0x000ff6eau, 0xf63b1194u, 0xb7f052ceu, 0xe27b136du};
    const uint32_t contents[] = {0x7d48df76u, 0x1edd164au, 0xb80c70a8u, 0xe4c1b1fcu, 0x365e1953u};
    const uint32_t types[DF_BOTTLE_TYPES] = {0xbe69de49u, 0xeaba6067u, 0x049d37c1u, 0xf383d6e5u,
        0x1c293517u, 0x1e834ef8u, 0x0f24e808u, 0xcdc21471u, 0x02084f9eu, 0x74d62ecbu,
        0x6f49e357u, 0x73356827u, 0xeef6e4b0u};
    const uint64_t flag = df_resource_entry(c, manager, owned[slot], 10756 + slot, DF_DATA_BOOL);
    if (!flag || recomp_load8(c, flag) != 1) return -1;
    const uint64_t entry = df_resource_entry(c, manager, contents[slot], 60 + slot, DF_DATA_ENUM);
    if (!entry) return -1;
    uint32_t actual = recomp_load32(c, entry);
    if (choice && choice <= DF_BOTTLE_TYPES && recomp_load32(c, entry + 12) == DF_BOTTLE_TYPES) {
        const uint64_t enum_list = recomp_load64(c, entry + 20);
        const uint32_t desired = types[choice - 1];
        if (enum_list && hos_mem_region(enum_list, sizeof(types)))
            for (unsigned i = 0; i < DF_BOTTLE_TYPES; ++i)
                if (recomp_load32(c, enum_list + 4 * i) == desired) {
                    recomp_store32(c, entry, desired);
                    recomp_store32(c, entry + 4, desired);
                    actual = desired;
                    break;
                }
    }
    for (unsigned i = 0; i < DF_BOTTLE_TYPES; ++i) if (actual == types[i]) return (int)i;
    return -1;
}

static void df_refill_resources(Ctx *c, uint64_t actor, unsigned mask, int bottle_edits) {
    if (!mask && bottle_edits < 0) {
        df_freeze_timer(c, 0, 0);
        return;
    }
    if (strcmp(hos_main_build_id, "e0f3ccfaf50065ae4ea01eb5aeb13b1a45da3348")) return;
    if (!hos_mem_region(OOT_GAMEDATA_SLOT, 8)) return;
    const uint64_t singleton = recomp_load64(c, OOT_GAMEDATA_SLOT);
    if (!singleton || !hos_mem_region(singleton, 8)) return;
    const uint64_t manager = recomp_load64(c, singleton);
    if (bottle_edits >= 0) {
        void rx_option_set(int id, int value);
        static int reported[DF_BOTTLES];
        static int64_t next_probe;
        const int64_t now = hos_now_ns();
        if (bottle_edits || now >= next_probe) {
            next_probe = now + 250000000LL;
            for (unsigned i = 0; i < DF_BOTTLES; ++i) {
                const unsigned choice = ((unsigned)bottle_edits >> (4 * i)) & 15;
                const int value = df_bottle_update(c, manager, i, choice);
                if (choice || value + 2 != reported[i]) {
                    reported[i] = value + 2;
                    rx_option_set(DF_OPT_BOTTLE_REPORT + (int)i, value);
                }
            }
        }
    }
    if (mask & (1u << DF_RESOURCE_HEARTS)) df_refill_hearts(c, actor, manager);
    df_freeze_timer(c, manager, (mask & (1u << DF_RESOURCE_TIMER)) != 0);
    static const struct {
        uint32_t hash, index, cap_hash, cap_index, flag_hash, flag_index, limit;
    } resources[] = {
#define DF_RESOURCE_VALUES(id, label, ...) {__VA_ARGS__},
        DF_RESOURCE_ROWS(DF_RESOURCE_VALUES)
#undef DF_RESOURCE_VALUES
    };
    for (unsigned i = 0; i < DF_RESOURCE_COUNT; ++i) {
        if (!(mask & (1u << i))) continue;
        const uint64_t target = df_resource_entry(c, manager, resources[i].hash, resources[i].index, DF_DATA_COUNT);
        if (!target) continue;
        if (resources[i].flag_hash) {
            const uint64_t flag = df_resource_entry(c, manager, resources[i].flag_hash, resources[i].flag_index, DF_DATA_BOOL);
            if (!flag || recomp_load8(c, flag) != 1) continue;
        }
        uint32_t limit = resources[i].limit;
        if (resources[i].cap_hash) {
            const uint64_t cap = df_resource_entry(c, manager, resources[i].cap_hash, resources[i].cap_index, DF_DATA_COUNT);
            if (!cap) continue;
            limit = recomp_load32(c, cap);
        }
        const uint32_t value = recomp_load32(c, target);
        if (limit && limit <= 9999 && value < limit) {
            recomp_store32(c, target, limit);
            recomp_store32(c, target + 4, limit);
        }
    }
}
#endif
