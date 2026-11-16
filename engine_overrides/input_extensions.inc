// Public SDK entry points use the same host devices as the internal API.
static void df_sensor_states(Cpu *c) {
    ret_x(c, six_fill(arg_p(c, 0), (int)arg_x(c, 1), arg_p(c, 2), "GetSixAxisSensorStates"));
}
static void df_sensor_state(Cpu *c) {
    six_fill(arg_p(c, 0), 1, arg_p(c, 1), "GetSixAxisSensorState");
}
static void df_gyro_mode(Cpu *c) {
    // Bias calibration is performed by the host motion pipeline, independently
    // of the console's requested zero-drift filter strength.
    six_axis_ours(arg_p(c, 0), "SetGyroscopeZeroDriftMode");
    need_handle(arg_p(c, 1), "SetGyroscopeZeroDriftMode");
}
static void df_no_optional_sensor(Cpu *c) { ret_x(c, 0); }
static void df_mouse_types(Cpu *c) {
    if (arg_p(c, 0)) *(uint32_t *)arg_p(c, 0) = 0;
}
static void df_vibration_mounted(Cpu *c) {
    ret_x(c, vibration_side(arg_p(c, 0), "IsOunceVibrationDeviceMounted") >= 0);
}
HOST_OVERRIDE("_ZN2nn3hid18StartSixAxisSensorERKNS0_19SixAxisSensorHandleE", ov_six_start);
HOST_OVERRIDE("_ZN2nn3hid17StopSixAxisSensorERKNS0_19SixAxisSensorHandleE", ov_six_stop);
HOST_OVERRIDE("_ZN2nn3hid22GetSixAxisSensorStatesEPNS0_18SixAxisSensorStateEiRKNS0_19SixAxisSensorHandleE", df_sensor_states);
HOST_OVERRIDE("_ZN2nn3hid21GetSixAxisSensorStateEPNS0_18SixAxisSensorStateERKNS0_19SixAxisSensorHandleE", df_sensor_state);
HOST_OVERRIDE("_ZN2nn3hid25SetGyroscopeZeroDriftModeERKNS0_19SixAxisSensorHandleERKNS0_22GyroscopeZeroDriftModeE", df_gyro_mode);
HOST_OVERRIDE("_ZN2nn3hid25InitializeVibrationDeviceERKNS0_21VibrationDeviceHandleE", ov_vib_init);
HOST_OVERRIDE("_ZN2nn3hid18SendVibrationValueERKNS0_21VibrationDeviceHandleERKNS0_14VibrationValueE", ov_vib_send);
HOST_OVERRIDE("_ZN2nn3hid29IsOunceVibrationDeviceMountedERKNS0_21VibrationDeviceHandleE", df_vibration_mounted);
HOST_OVERRIDE("_ZN2nn3hid22GetSensorFusionHandlesEPNS0_18SensorFusionHandleEiRKjNS_4util10BitFlagSetILi32ENS0_12NpadStyleTagEEE", df_no_optional_sensor);
HOST_OVERRIDE("_ZN2nn3hid20FinalizeSensorFusionEv", df_no_optional_sensor);
HOST_OVERRIDE("_ZN2nn3hid16GetNmouseHandlesEPNS0_12NmouseHandleEij", df_no_optional_sensor);
HOST_OVERRIDE("_ZN2nn3hid16GetNmouseTypeSetEPNS_4util10BitFlagSetILi32ENS0_10NmouseTypeEEENS0_12NmouseHandleE", df_mouse_types);
HOST_OVERRIDE("_ZN2nn3hid14FinalizeNmouseEv", df_no_optional_sensor);
