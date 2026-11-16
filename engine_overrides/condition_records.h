// Original replay-order counter ledger. The caller serializes access.
#ifndef DF_CONDITION_RECORDS_H
#define DF_CONDITION_RECORDS_H
#include <stdint.h>
#include <string.h>
#ifndef DF_COUNTER_CAPACITY
#define DF_COUNTER_CAPACITY 65536u
#endif
_Static_assert(DF_COUNTER_CAPACITY && !(DF_COUNTER_CAPACITY & (DF_COUNTER_CAPACITY-1)), "Counter capacity must be a power of two");
typedef struct {
    uint64_t address, epoch, serial;
    uint8_t bytes[16], overlay[16];
    uint16_t valid, overlay_mask;
    uint8_t pending;
} DfCounterRecord;
typedef struct {
    DfCounterRecord records[DF_COUNTER_CAPACITY];
    uint64_t epoch, serial;
    uint32_t used, slots[DF_COUNTER_CAPACITY];
} DfCounterLedger;

static DfCounterRecord *df_counter_find(DfCounterLedger *ledger, uint64_t address, int insert) {
    if (!address) return NULL;
    unsigned at = (unsigned)((address >> 4) * UINT64_C(11400714819323198485)) & (DF_COUNTER_CAPACITY-1);
    DfCounterRecord *reusable = NULL;
    for (unsigned n=0; n<DF_COUNTER_CAPACITY; n++, at=(at+1)&(DF_COUNTER_CAPACITY-1)) {
        DfCounterRecord *record = &ledger->records[at];
        if (record->address == address) return record;
        if (!record->address) { if (!reusable) reusable=record; break; }
        if (!reusable && !record->pending && record->epoch != ledger->epoch) reusable=record;
    }
    if (!insert || !reusable) return NULL;
    if (!reusable->address) ledger->slots[ledger->used++]=(uint32_t)(reusable-ledger->records);
    memset(reusable,0,sizeof *reusable);
    reusable->address=address;
    return reusable;
}

static uint64_t df_counter_report(DfCounterLedger *ledger, uint64_t address, int samples) {
    DfCounterRecord *record=df_counter_find(ledger,address,1);
    if (!record) return 0;
    record->epoch=ledger->epoch;
    record->serial=++ledger->serial;
    record->pending=1;
    record->valid=samples ? 0 : 0xff;
    record->overlay_mask=0;
    memset(record->bytes,0,sizeof record->bytes);
    return record->serial;
}

// A late callback cannot replace a newer report or a later buffer fill.
static int df_counter_complete(DfCounterLedger *ledger, uint64_t address, uint64_t serial,
                               uint64_t value, uint64_t timestamp, uint8_t output[16]) {
    DfCounterRecord *record=df_counter_find(ledger,address,0);
    if (!record || record->serial != serial) return 0;
    memcpy(output,&value,8);
    memcpy(output+8,&timestamp,8);
    for (unsigned i=0;i<16;i++)
        if (record->overlay_mask & (1u<<i)) output[i]=record->overlay[i];
    memcpy(record->bytes,output,16);
    record->valid=0xffff;
    record->pending=0;
    return 1;
}

// 0: use guest memory; 1: replay value; 2: result not yet available (render).
static int df_counter_read(DfCounterLedger *ledger, uint64_t address, uint64_t *value) {
    DfCounterRecord *record=df_counter_find(ledger,address,0);
    if (!record || (record->epoch != ledger->epoch && !record->pending)) return 0;
    if ((record->valid & 0xff) != 0xff) return 2;
    memcpy(value,record->bytes,8);
    return 1;
}

static void df_counter_fill(DfCounterLedger *ledger, uint64_t address, uint64_t size, uint32_t value) {
    if (!size || address > UINT64_MAX-size) return;
    for (unsigned i=0;i<ledger->used;i++) {
        DfCounterRecord *record=&ledger->records[ledger->slots[i]];
        if (!record->address || record->address > UINT64_MAX-16 ||
            record->address >= address+size || address >= record->address+16) continue;
        record->epoch=ledger->epoch;
        for (unsigned b=0;b<16;b++) {
            uint64_t byte=record->address+b;
            if (byte<address || byte-address>=size) continue;
            uint8_t fill=(uint8_t)(value >> (8*((byte-address)&3)));
            record->bytes[b]=record->overlay[b]=fill;
            record->valid |= (uint16_t)(1u<<b);
            record->overlay_mask |= (uint16_t)(1u<<b);
        }
    }
}
#endif
