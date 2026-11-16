// Program-owned control copies keep short NVN2 records away from legacy readers.
typedef struct DfProgramControls {
    uint64_t serial;
    uint8_t *blocks;
    struct DfProgramControls *next;
} DfProgramControls;
static DfProgramControls *df_controls;
static PlatMutex df_controls_lock = PLAT_MUTEX_INIT;

static void df_controls_free(uint64_t serial) {
    if (!serial) return;
    plat_mutex_lock(&df_controls_lock);
    DfProgramControls **link = &df_controls;
    while (*link && (*link)->serial != serial) link = &(*link)->next;
    DfProgramControls *record = *link;
    if (record) *link = record->next;
    plat_mutex_unlock(&df_controls_lock);
    if (record) { free(record->blocks); free(record); }
}

static void df_controls_bind(prog_t *program) {
    DfProgramControls *record = NULL;
    for (uint32_t index = 0; index < program->nstage; ++index) {
        const uint8_t *control = program->sd[index].control;
        if (!df_control_ampere(control)) continue;
        if (!record) {
            record = calloc(1, sizeof *record);
            if (record) record->blocks = calloc(6, 0x880);
            if (!record || !record->blocks) rt_fatal("NVN2: cannot allocate program controls");
            record->serial = program->serial;
        }
        const uint8_t *code = (const uint8_t *)(uintptr_t)program->sd[index].data;
        uint8_t *normalized = record->blocks + index * 0x880;
        if (df_nvn2_normalize(normalized, control, 0xd8, code, df_control_word(control, 0x44)) != 1)
            rt_fatal("NVN2: invalid shader control or code extent");
        program->sd[index].control = normalized;
    }
    if (record) {
        plat_mutex_lock(&df_controls_lock);
        record->next = df_controls;
        df_controls = record;
        plat_mutex_unlock(&df_controls_lock);
    }
}
