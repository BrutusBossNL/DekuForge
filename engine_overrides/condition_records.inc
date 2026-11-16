#include "df_condition_records.h"
#include "platform/platform.h"
static DfCounterLedger df_conditions;
static PlatMutex df_conditions_lock = PLAT_MUTEX_INIT;
void df_condition_frame_end(void) {
    plat_mutex_lock(&df_conditions_lock);
    df_conditions.epoch++;
    plat_mutex_unlock(&df_conditions_lock);
}
static uint64_t df_condition_report(uint64_t address, int samples) {
    plat_mutex_lock(&df_conditions_lock);
    uint64_t serial=df_counter_report(&df_conditions,address,samples);
    plat_mutex_unlock(&df_conditions_lock);
    if (!serial) rt_fatal("Replay counter ledger exhausted");
    return serial;
}
static uint64_t df_condition_serial(uint64_t address) {
    if (!address) return 0;
    plat_mutex_lock(&df_conditions_lock);
    DfCounterRecord *record=df_counter_find(&df_conditions,address,0);
    uint64_t serial=record ? record->serial : 0;
    plat_mutex_unlock(&df_conditions_lock);
    return serial;
}
static int df_condition_read(uint64_t address, uint64_t *value) {
    plat_mutex_lock(&df_conditions_lock);
    int result=df_counter_read(&df_conditions,address,value);
    plat_mutex_unlock(&df_conditions_lock);
    return result;
}
static void df_condition_publish(uint64_t address, uint64_t value, uint64_t serial) {
    uint8_t output[16];
    uint64_t timestamp=(uint64_t)((unsigned __int128)kern_now_ns()*12/625);
    plat_mutex_lock(&df_conditions_lock);
    if (df_counter_complete(&df_conditions,address,serial,value,timestamp,output))
        memcpy((void *)(uintptr_t)address,output,sizeof output);
    plat_mutex_unlock(&df_conditions_lock);
}
static void df_condition_fill(uint64_t address, uint64_t size, uint32_t value) {
    plat_mutex_lock(&df_conditions_lock);
    df_counter_fill(&df_conditions,address,size,value);
    plat_mutex_unlock(&df_conditions_lock);
}
