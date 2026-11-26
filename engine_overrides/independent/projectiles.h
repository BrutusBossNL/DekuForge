#pragma once

enum { DF_OPT_EXPLOSIVE_SHOTS = 705, DF_BOMB_ARROW = 1, DF_EXPLOSIVE_SEED = 2 };

// Only the held actor has a stable attachment point for the projected effect.
enum { DF_SHOT_HELD = 1, DF_SHOT_FIRED = 2 };

#ifdef DF_PROJECTILE_HOST
enum { DF_TRACKED_SHOTS = 32, DF_BLASTS = 8 };
typedef struct {
    uint64_t actor;
    uint32_t generation, state;
    int armed;
    float position[3];
    int64_t seen;
} DfShot;

static SRWLOCK df_shot_lock = SRWLOCK_INIT;
static DfShot df_shots[DF_TRACKED_SHOTS];
static struct {
    uint64_t component;
    int mode;
    float position[3];
    int64_t seen;
} df_held_aura;
static float df_impacts[DF_BLASTS][3];
static unsigned df_impact_count;

static int df_actor_named(Ctx *c, uint64_t actor, const char *expected) {
    const uint64_t name = actor ? df_pointer(c, actor + 0x20) : 0;
    const size_t len = strlen(expected) + 1;
    if (!hos_mem_region(name, len)) return 0;
    for (size_t i = 0; i < len; ++i)
        if (recomp_load8(c, name + i) != (uint8_t)expected[i]) return 0;
    return 1;
}

static uint64_t df_projectile_call(Ctx *c, uint64_t target, const uint64_t *arguments, unsigned count) {
    A64Fn call = a64_lookup(target);
    if (!call) return 0;
    const Ctx original = *c;
    for (unsigned i = 0; i < count; ++i) c->x[i] = arguments[i];
    call(c);
    const uint64_t result = c->x[0];
    *c = original;
    return result;
}

static int df_bomb_stock(Ctx *c, int take) {
    const uint64_t manager = df_pointer(c, df_pointer(c, OOT_GAMEDATA_SLOT));
    const uint64_t ammo = df_resource_entry(c, manager, 0xdb1bcd4fu, 1007, DF_DATA_COUNT);
    const uint64_t bag = df_resource_entry(c, manager, 0xe753508bu, 972, DF_DATA_COUNT);
    if (!ammo || !bag) return 0;
    const uint32_t stock = recomp_load32(c, ammo), capacity = recomp_load32(c, bag);
    if (!stock || stock > capacity || capacity > 9999) return 0;
    if (oot_item_count(c, "Item_BombBag_Small") <= 0 &&
        oot_item_count(c, "Item_BombBag_Medium") <= 0 &&
        oot_item_count(c, "Item_BombBag_Large") <= 0) return 0;
    if (take) {
        recomp_store32(c, ammo, stock - 1);
        recomp_store32(c, ammo + 4, stock - 1);
    }
    return 1;
}

static void df_track_projectile(Ctx *c, uint64_t component, int seed_only) {
    int rx_option(int id, int otherwise);
    const int modes = rx_option(DF_OPT_EXPLOSIVE_SHOTS, 0);
    if (!modes || (seed_only && !(modes & DF_EXPLOSIVE_SEED))) return;
    if (!hos_mem_region(component, 0xe0)) return;
    const uint64_t actor = df_pointer(c, component + 0x18);
    if (!actor || !hos_mem_region(actor, 0x328)) return;
    const int seed = (modes & DF_EXPLOSIVE_SEED) && df_actor_named(c, actor, "Item_DekuSeed");
    if (!seed && (seed_only || !(modes & DF_BOMB_ARROW) ||
        (!df_actor_named(c, actor, "Item_Arrow_Normal") && !df_actor_named(c, actor, "NormalArrow")))) return;
    const uint64_t player = df_pointer(c, df_pointer(c, 0x84e571d0ULL) + 0x480);
    const uint64_t ref = df_pointer(c, component + 0x78);
    const uint32_t serial = recomp_load32(c, component + 0x80);
    if (!player || !df_actor_named(c, player, "Player") || !hos_mem_region(ref, 0x4c) ||
        serial == UINT32_MAX || recomp_load32(c, ref + 0x48) != serial ||
        df_pointer(c, ref + 0x40) != player) return;
    int child = 0;
    if (!oot_gamedata_bool(c, 0xcea220d3u, &child) || child != seed ||
        oot_item_count(c, seed ? "Weapon_Range_SlingShot" : "Weapon_Range_Bow") <= 0) return;
    if (!seed) {
        const uint64_t blackboard = df_pointer(c, df_pointer(c, df_pointer(c, actor + 0x270)) + 0x10);
        if (!blackboard) return;
        static _Thread_local uint64_t scratch;
        if (!scratch) scratch = hos_sys_alloc(16, 16);
        recomp_store64(c, scratch, 0x83ded120ULL);
        const uint64_t params[] = {blackboard, scratch};
        const uint64_t type = df_projectile_call(c, 0x80c929b0ULL, params, 2);
        if (!hos_mem_region(type, 4) || recomp_load32(c, type)) return;
    }
    const uint32_t state = recomp_load32(c, component + 0x24);
    const uint32_t generation = recomp_load32(c, actor + 0x18);
    const int64_t now = hos_now_ns();
    AcquireSRWLockExclusive(&df_shot_lock);
    DfShot *shot = NULL;
    unsigned oldest = 0;
    for (unsigned i = 0; i < DF_TRACKED_SHOTS; ++i) {
        if (df_shots[i].actor == actor && df_shots[i].generation == generation) shot = &df_shots[i];
        if (df_shots[i].seen < df_shots[oldest].seen) oldest = i;
    }
    if (!shot) {
        shot = &df_shots[oldest];
        *shot = (DfShot){.actor = actor, .generation = generation};
    }
    if (state == DF_SHOT_FIRED && shot->state != DF_SHOT_FIRED) shot->armed = 1;
    const int visualize = state == DF_SHOT_HELD && df_bomb_stock(c, 0);
    if (visualize || shot->armed)
        for (unsigned i = 0; i < 3; ++i) {
            const uint32_t raw = recomp_load32(c, actor + 0x31c + 4 * i);
            memcpy(shot->position + i, &raw, 4);
        }
    const int valid = isfinite(shot->position[0]) && isfinite(shot->position[1]) && isfinite(shot->position[2]);
    static unsigned seen_aura;
    if (visualize && valid) {
        df_held_aura.component = component;
        df_held_aura.mode = seed ? DF_EXPLOSIVE_SEED : DF_BOMB_ARROW;
        df_held_aura.seen = now;
        memcpy(df_held_aura.position, shot->position, sizeof(shot->position));
        const unsigned bit = 1u << seed;
        if (!(seen_aura & bit)) hos_log("cheats: %s aura active", seed ? "Deku seed" : "bomb arrow");
        seen_aura |= bit;
    } else if (df_held_aura.component == component) {
        df_held_aura.component = 0;
    }
    if ((state == 0 || (seed && state == 4)) && shot->armed) {
        shot->armed = 0;
        if (valid && df_impact_count < DF_BLASTS && df_bomb_stock(c, 1)) {
            memcpy(df_impacts[df_impact_count++], shot->position, sizeof(shot->position));
            hos_log("cheats: %s impact queued", seed ? "explosive Deku seed" : "bomb arrow");
        }
    }
    shot->state = state;
    shot->seen = now;
    ReleaseSRWLockExclusive(&df_shot_lock);
}

#ifdef _WIN32
__declspec(dllexport)
#endif
unsigned df_projectile_aura_points(float (*out)[3], unsigned capacity) {
    int rx_option(int id, int otherwise);
    const int modes = rx_option(DF_OPT_EXPLOSIVE_SHOTS, 0);
    if (!capacity || !modes) return 0;
    unsigned count = 0;
    const int64_t now = hos_now_ns();
    AcquireSRWLockShared(&df_shot_lock);
    if (df_held_aura.component && (modes & df_held_aura.mode) &&
        now - df_held_aura.seen < 120000000LL) {
        memcpy(out[0], df_held_aura.position, sizeof(df_held_aura.position));
        count = 1;
    }
    ReleaseSRWLockShared(&df_shot_lock);
    return count;
}

void df_guest_projectile(Ctx *c) {
    df_track_projectile(c, c->x[0], 0);
}

void df_guest_projectile_transition(Ctx *c) {
    const uint64_t component = c->x[20];
    if ((uint32_t)c->x[19] != DF_SHOT_HELD) {
        AcquireSRWLockExclusive(&df_shot_lock);
        if (df_held_aura.component == component) df_held_aura.component = 0;
        ReleaseSRWLockExclusive(&df_shot_lock);
    }
    df_track_projectile(c, component, 1);
}

void df_guest_projectile_frame(Ctx *c) {
    static uint64_t storage;
    static int64_t pending[DF_BLASTS];
    float impacts[DF_BLASTS][3];
    AcquireSRWLockExclusive(&df_shot_lock);
    const unsigned count = df_impact_count;
    memcpy(impacts, df_impacts, count * sizeof(impacts[0]));
    df_impact_count = 0;
    ReleaseSRWLockExclusive(&df_shot_lock);
    if (!count && !storage) return;
    if (!storage) storage = hos_sys_alloc(0x200 * DF_BLASTS, 16);
    const int64_t now = hos_now_ns();
    unsigned next = 0;
    for (unsigned i = 0; i < DF_BLASTS; ++i) {
        const uint64_t handle = storage + 0x200 * i;
        if (pending[i]) {
            const uint64_t request = df_pointer(c, handle);
            const unsigned state = hos_mem_region(request, 4) ? recomp_load32(c, request) & 0xffff : 0;
            if (state == 3) {
                const uint64_t collect[] = {handle, 1, 0};
                const uint64_t bomb = df_projectile_call(c, 0x83acefd0ULL, collect, 3);
                const uint64_t chem = df_pointer(c, df_pointer(c, bomb + 0x270) + 0x198);
                if (df_actor_named(c, bomb, "Item_Bomb") && chem) {
                    const uint64_t explode[] = {chem, 2, UINT64_MAX, 0x7fc00000u, 0};
                    df_projectile_call(c, 0x82dff620ULL, explode, 5);
                    hos_log("cheats: projectile impact detonated");
                }
                pending[i] = 0;
            } else if (!request || state == 4 || now - pending[i] > 5000000000LL) {
                const uint64_t release[] = {handle, 1};
                if (request) df_projectile_call(c, 0x80b4fa30ULL, release, 2);
                pending[i] = 0;
            }
        }
        if (pending[i] || next >= count) continue;
        const uint64_t manager = df_pointer(c, df_pointer(c, 0x84c9f3e0ULL));
        if (!manager) continue;
        const uint64_t name = handle + 0x20, arg = handle + 0x40;
        memset(GP(handle), 0, 0x200);
        float data[15] = {0};
        memcpy(data, impacts[next++], sizeof(impacts[0]));
        data[3] = data[7] = data[11] = data[12] = data[13] = data[14] = 1;
        memcpy(GP(arg), data, sizeof(data));
        HOS_WRITTEN(GP(handle), 0x200);
        recomp_store64(c, name, 0x83d0f69bULL);
        recomp_store64(c, arg + 0x40, 0x83d0f6a4ULL);
        recomp_store8(c, arg + 0x98, 3);
        const uint64_t create[] = {manager, name, arg, handle, 1, 0, 0, 0};
        df_projectile_call(c, 0x80392a70ULL, create, 8);
        if (df_pointer(c, handle)) pending[i] = now;
    }
}
#endif
