// Original fixed SDR virtual-display adapter. Vulkan owns presentation timing;
// the virtual console display advertises 60 Hz and no variable refresh or HDR.
static void df_display_hdr(Cpu *c) {
    if (arg_p(c, 3) != display || !arg_p(c, 0) || !arg_p(c, 1) || !arg_p(c, 2)) {
        ret_x(c, VI_R_INVALID); return;
    }
    *(uint8_t *)arg_p(c, 0) = 0;
    *(uint32_t *)arg_p(c, 1) = 0;
    *(uint16_t *)arg_p(c, 2) = 0;
    ret_x(c, 0);
}
static void df_display_white(Cpu *c) {
    if (arg_p(c, 1) != display || !arg_p(c, 0)) { ret_x(c, VI_R_INVALID); return; }
    *(uint16_t *)arg_p(c, 0) = 203;
    ret_x(c, 0);
}
static void df_display_refresh(Cpu *c) {
    if (arg_p(c, 2) != display || !arg_p(c, 0) || !arg_p(c, 1)) { ret_x(c, VI_R_INVALID); return; }
    *(uint32_t *)arg_p(c, 0) = 60;
    *(uint8_t *)arg_p(c, 1) = 0;
    ret_x(c, 0);
}
static void df_display_vrr(Cpu *c) {
    if (arg_p(c, 1) != display || !arg_p(c, 0)) { ret_x(c, VI_R_INVALID); return; }
    *(uint8_t *)arg_p(c, 0) = 0;
    ret_x(c, 0);
}
static void df_layer_default_interval(Cpu *c) {
    // No extended interval is active on the fixed virtual display. NVN's window
    // interval and the host presentation settings remain the timing authority.
    ret_x(c, arg_p(c, 0) == layer ? 0 : VI_R_INVALID);
}
static void df_display_capability(Cpu *c) {
    // The application's capability declaration cannot change the virtual mode.
    ret_x(c, arg_p(c, 0) == display ? 0 : VI_R_INVALID);
}
static void df_graphics_init_check(Cpu *c) {
    (void)c;
    if (!nv.initialized) rt_fatal("Graphics allocator was not initialized");
}
HOST_OVERRIDE("_ZN2nn2vi21QueryDisplayHdrStatusEPbPNS0_15HdrOutputFormatEPtPKNS0_7DisplayE", df_display_hdr);
HOST_OVERRIDE("_ZN2nn2vi25QueryDisplayHdrPaperWhiteEPtPKNS0_7DisplayE", df_display_white);
HOST_OVERRIDE("_ZN2nn2vi30QueryDisplayCurrentRefreshRateEPNS0_11RefreshRateEPbPKNS0_7DisplayE", df_display_refresh);
HOST_OVERRIDE("_ZN2nn2vi24QueryDisplayVrrSupportedEPbPKNS0_7DisplayE", df_display_vrr);
HOST_OVERRIDE("_ZN2nn2vi30ClearLayerExtendedSwapIntervalEPNS0_5LayerE", df_layer_default_interval);
HOST_OVERRIDE("_ZN2nn2vi36SetDisplay120HzRefreshRateCapabilityEPNS0_7DisplayEb", df_display_capability);
HOST_OVERRIDE("_ZN2nn2vi23SetDisplayVrrCapabilityEPNS0_7DisplayEb", df_display_capability);
HOST_OVERRIDE("_ZN2nv9InitCheckEv", df_graphics_init_check);
