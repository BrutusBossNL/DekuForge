// Original NVN2 program-builder adapter to the existing host shader pipeline.
typedef struct {
    void *device;
    const NVNshaderData *shaders;
    const void *debug_hashes;
    int32_t count;
    uint32_t sample_shading;
} df_program_builder;
_Static_assert(sizeof(df_program_builder) <= 128, "program builder guest storage");
#define DF_PB ((df_program_builder *)arg_p(c, 0))
NVN_API(nvnProgramBuilderSetDefaults) {
    void *device = DF_PB->device;
    memset(DF_PB, 0, sizeof *DF_PB);
    DF_PB->device = device;
}
NVN_API(nvnProgramBuilderSetDevice) { DF_PB->device = arg_p(c, 1); }
NVN_API(nvnProgramBuilderGetDevice) { ret_x(c, (uintptr_t)DF_PB->device); }
NVN_API(nvnProgramBuilderSetShaders) {
    DF_PB->count = (int32_t)arg_x(c, 1);
    DF_PB->shaders = arg_p(c, 2);
}
NVN_API(nvnProgramBuilderGetShaderCount) { ret_x(c, DF_PB->count); }
NVN_API(nvnProgramBuilderGetShaders) { ret_x(c, (uintptr_t)DF_PB->shaders); }
NVN_API(nvnProgramBuilderSetDebugDataHashes) { DF_PB->debug_hashes = arg_p(c, 1); }
NVN_API(nvnProgramBuilderGetDebugDataHashes) { ret_x(c, (uintptr_t)DF_PB->debug_hashes); }
NVN_API(nvnProgramBuilderSetSampleShading) { DF_PB->sample_shading = arg_x(c, 1) != 0; }
NVN_API(nvnProgramBuilderGetSampleShading) { ret_x(c, DF_PB->sample_shading); }
NVN_API(nvnProgramInitializeFromBuilder) {
    NVN_BLOCKING();
    prog_t *program = arg_p(c, 0);
    const df_program_builder *builder = arg_p(c, 1);
    if (builder->sample_shading)
        rt_fatal("NVN2 program sample shading requires pipeline integration");
    if (builder->count < 0 || builder->count > 6 || (builder->count && !builder->shaders)) {
        ret_x(c, 0);
        return;
    }
    memset(program, 0, sizeof *program);
    program->magic = NVN_PROG_MAGIC;
    ret_x(c, prog_set_shaders(program, builder->count, builder->shaders));
}
#undef DF_PB
