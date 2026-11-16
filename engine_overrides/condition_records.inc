#include "df_condition_records.h"
#include "platform/platform.h"
static DfCounterLedger df_conditions;
static PlatMutex df_conditions_lock = PLAT_MUTEX_INIT;
// Replay-thread diagnostics only; completion callbacks do not touch these counters.
static uint64_t df_condition_stats[3][2], df_condition_reads[3];
static int df_condition_trace_on(void) {
    static int initialized;
    static uint64_t first;
    if (!initialized) {
        const char *setting=getenv("DEKUFORGE_TRACE_CONDITION_FRAME");
        first=setting ? strtoull(setting,NULL,10) : 0;
        initialized=1;
    }
    return first && df_conditions.epoch>=first && df_conditions.epoch-first<16;
}
void df_condition_work(unsigned kind, int skipped) {
    if (kind<3 && df_condition_trace_on()) df_condition_stats[kind][!!skipped]++;
}
void df_condition_frame_end(void) {
    if (df_condition_trace_on()) {
        rt_log("Condition frame %llu: draw %llu/%llu colour-clear %llu/%llu depth-clear %llu/%llu (run/skip), reads guest/known/pending %llu/%llu/%llu",
            (unsigned long long)df_conditions.epoch,
            (unsigned long long)df_condition_stats[0][0],(unsigned long long)df_condition_stats[0][1],
            (unsigned long long)df_condition_stats[1][0],(unsigned long long)df_condition_stats[1][1],
            (unsigned long long)df_condition_stats[2][0],(unsigned long long)df_condition_stats[2][1],
            (unsigned long long)df_condition_reads[0],(unsigned long long)df_condition_reads[1],(unsigned long long)df_condition_reads[2]);
        memset(df_condition_stats,0,sizeof df_condition_stats);
        memset(df_condition_reads,0,sizeof df_condition_reads);
    }
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
    if (df_condition_trace_on()) df_condition_reads[result]++;
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
