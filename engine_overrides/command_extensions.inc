// Original adapters for command modes supported by host-owned recordings.
// Vulkan selects geometry processing through the pipeline attached to each draw.
// Vertex, mesh and task+mesh modes are represented by draw opcodes and stages.
NVN_API(nvnCommandBufferSetGeometryProcessingMode) {
    uint32_t mode = (uint32_t)arg_x(c, 1);
    if (mode > 2) rt_fatal("Unsupported geometry processing mode %u", mode);
}
NVN_API(nvnCommandBufferDrawMeshTasks) {
    int first = (int)arg_x(c, 1), count = (int)arg_x(c, 2);
    if (first < 0 || count < 0) rt_fatal("Invalid mesh task range");
    *REC(cmd_of(c), OP_DRAW, p_draw) = (p_draw){.prim=0x40, .first=first, .count=count, .instances=1};
}
NVN_API(nvnCommandBufferDrawMeshTasksIndirect) {
    uint64_t address = arg_x(c, 1);
    if (!address || address % 4) rt_fatal("Invalid indirect mesh argument address");
    *REC(cmd_of(c), OP_DRAW, p_draw) = (p_draw){.prim=0x40, .instances=1, .df_ind=address};
}
NVN_API(nvnCommandBufferSetRecordingMode) {
    // NVN2 modes select device command-memory recording strategies. This backend
    // owns an independent command stream for every buffer and copies it at EndRecording,
    // so all three strategies have the same lifetime and execution semantics here.
    unsigned mode = (unsigned)arg_x(c, 1);
    if (mode > 2) rt_fatal("Unsupported command recording mode %u", mode);
}

NVN_API(nvnCommandBufferSetCopyImageStride) {
    int64_t stride = (int64_t)arg_x(c, 1);
    if (stride < 0) rt_fatal("Negative texture image stride");
    REC(cmd_of(c), OP_DF_IMAGE_STRIDE, p_copy_stride)->stride = stride;
}

// Scheduling hints cannot weaken the Vulkan backend's ordered submissions and
// per-dispatch memory barriers. Keeping the stricter ordering is valid for both
// overlap modes; priority is left to the host driver.
NVN_API(nvnCommandBufferSetComputeOverlapMode) { (void)c; }
NVN_API(nvnCommandBufferSetComputeWorkloadPriority) { (void)c; }
NVN_API(nvnCommandBufferSetGraphicsWorkloadPriority) { (void)c; }

// Full-rate fragment shading is the quality-preserving fallback for variable
// shading rates. The Vulkan pipeline shades every pixel, regardless of palette.
NVN_API(nvnCommandBufferBindShadingRateImage) { (void)c; }
NVN_API(nvnCommandBufferShadingRateImagePalette) { (void)c; }
NVN_API(nvnCommandBufferSetShadingRatePaletteMode) { (void)c; }
// Early stencil culling is optional; the normal depth/stencil test still runs.
NVN_API(nvnCommandBufferSetStencilCullCriteria) { (void)c; }

// The inline data belongs to the recorded command, not the caller's temporary
// buffer. Partial pushes preserve the remaining bytes in the compute bank.
NVN_API(nvnCommandBufferPushComputeConstants) {
    uint64_t slot = arg_x(c, 1), offset = arg_x(c, 2), size = arg_x(c, 3);
    if (slot != 0 || offset > 1024 || size > 1024 - offset || (size && !arg_p(c, 4)))
        rt_fatal("Invalid compute constant range");
    p_df_constants *packet = rec(cmd_of(c), OP_DF_CONSTANTS, sizeof *packet + size);
    packet->slot = (uint32_t)slot; packet->offset = (uint32_t)offset; packet->size = (uint32_t)size;
    memcpy(packet->bytes, arg_p(c, 4), size);
}
