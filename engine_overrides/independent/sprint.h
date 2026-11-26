#pragma once
#include <stdint.h>

enum { DF_OPT_L3_SPRINT = 701, DF_OPT_AIR_JUMP = 706 };

typedef struct {
    int pressed;
    int active;
} DfSprint;

/* Releasing L3 rearms the click. Releasing the movement stick cancels a
 * latched sprint, so resuming movement requires a new click. */
static inline int df_sprint(DfSprint *state, int toggle, int pressed, int can_sprint) {
    const int clicked = pressed && !state->pressed;
    state->pressed = pressed;
    if (!can_sprint || !toggle) state->active = 0;
    else if (clicked) state->active = !state->active;
    return can_sprint && (toggle ? state->active : pressed);
}

#ifdef DF_SPRINT_HOST
static void df_apply_guest_sprint(Ctx *c, unsigned flags) {
    int hos_dekuforge_direct_sprint(void);
    int hos_oot_player_free(void);
    if (!hos_dekuforge_direct_sprint() || !hos_oot_player_free()) return;
    const uint64_t state = c->x[19];
    if (!hos_mem_region(state, 0x20)) return;
    const uint64_t actor = recomp_load64(c, state + 0x18);
    if (hos_mem_region(actor, 24) && hos_oot_is_player(c, actor))
        c->x[flags] |= UINT64_C(1) << 4;
}

// Apply the dash flag at its movement and camera consumers. The pad still
// delivers the ordinary roll button independently.
void df_guest_sprint_movement(Ctx *c) { df_apply_guest_sprint(c, 10); }
void df_guest_sprint_stance(Ctx *c) { df_apply_guest_sprint(c, 8); }
#endif
