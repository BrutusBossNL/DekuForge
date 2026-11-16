// Rewrite a sorted raw-address map for one staged physical buffer interval.
// Every virtual alias of that interval is split and redirected consistently.
static int df_counter_address_map(uint64_t (*out)[4], const uint64_t (*in)[4],
    size_t capacity, uint64_t source, uint64_t bytes, uint64_t target) {
    if (capacity < 2 || !bytes || source > UINT64_MAX-bytes || target > UINT64_MAX-bytes) return 0;
    memset(out,0,capacity*sizeof *out);
    for(size_t i=1;i<capacity;i++) out[i][0]=UINT64_MAX;
    size_t used=1;
    uint64_t previous=0;
    for(size_t i=1;i<capacity && in[i][0]!=UINT64_MAX;i++) {
        uint64_t lo=in[i][0],hi=in[i][1],physical=lo+in[i][2];
        if(hi<=lo || lo<previous || physical>UINT64_MAX-(hi-lo)) return 0;
        previous=hi;
        uint64_t end=physical+(hi-lo);
        uint64_t first=physical>source ? physical : source;
        uint64_t last=end<source+bytes ? end : source+bytes;
        uint64_t boundaries[4]={lo,hi,hi,hi},delta[3]={in[i][2],in[i][2],in[i][2]};
        unsigned parts=1;
        if(first<last) {
            boundaries[1]=lo+(first-physical);
            boundaries[2]=lo+(last-physical);
            boundaries[3]=hi;
            delta[1]=target+(first-source)-boundaries[1];
            parts=3;
        }
        for(unsigned part=0;part<parts;part++) {
            if(boundaries[part]==boundaries[part+1]) continue;
            if(used==capacity) return 0;
            out[used][0]=boundaries[part];out[used][1]=boundaries[part+1];
            out[used][2]=delta[part];out[used++][3]=in[i][3];
        }
    }
    return 1;
}
