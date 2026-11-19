"""Checked guest-code hooks for the independent 1.1.1 game."""

BUILD_ID = 'e0f3ccfaf50065ae4ea01eb5aeb13b1a45da3348'
HOOKS = (
    (0x801839b0, 0xd503237f, 'df_guest_magic'),
    (0x80c1d164, 0xbd416b08, 'df_guest_spin_charge'),
    (0x80afeff8, 0x1e241001, 'df_guest_spin_range'),
    (0x80aff0ac, 0x1e249001, 'df_guest_spin_range'),
    (0x80aff0d8, 0x1e245001, 'df_guest_spin_range'),
    (0x82ecbc30, 0xd503237f, 'df_guest_projectile'),
    (0x82ecb934, 0xb9002693, 'df_guest_seed_transition'),
    (0x80706be0, 0xd503237f, 'df_guest_projectile_frame'),
    (0x802290a8, 0x39517268, 'df_guest_world_master'),
    (0x802291a4, 0xb94017e9, 'df_guest_world_visibility'),
    (0x80229348, 0x1e290d40, 'df_guest_world_style'),
    (0x80227760, 0x39516e69, 'df_guest_world_chests'),
    (0x80223af0, 0x94001a3c, 'df_guest_world_facility_position'),
    (0x802232a8, 0x5e21d800, 'df_guest_world_facility_style'),
)


def install(lifter, image, build_id):
    if build_id != BUILD_ID:
        return
    for address, word, _ in HOOKS:
        if image.word(address) != word:
            raise ValueError(f'Independent cheat hook did not match guest code at {address:#x}')
    for address, _, callback in HOOKS:
        splice = f'{{ extern void {callback}(Ctx *); {callback}(c); }}'
        lifter.after[address] = lifter.after.get(address, '') + '\n' + splice
