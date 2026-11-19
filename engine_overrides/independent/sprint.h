#pragma once

enum { DF_OPT_L3_SPRINT = 701 };

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
