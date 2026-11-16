// NVN point-sprite varyings have no mesh output: derive them from PointCoord.
// This adapter accepts only direct float vec4 inputs and scalar component access.
static int df_mesh_is_points(const uint32_t *code, uint64_t words) {
    for (uint64_t i=5; i<words;) {
        uint32_t n=code[i]>>16, op=code[i]&65535;
        if (!n || n>words-i) return 0;
        if (op==16 && n>=3 && code[i+2]==27) return 1;
        i+=n;
    }
    return 0;
}

static uint32_t *df_fragment_point_inputs(const uint32_t *code, uint64_t words,
                                         uint32_t missing, uint64_t *out_words) {
    if (!missing || words<5 || code[3]>1048576) return NULL;
    uint32_t bound=code[3], entry=0, vector=0, scalar=0, targets=0;
    uint32_t *types=calloc(bound,sizeof(uint32_t)), *pointee=calloc(bound,sizeof(uint32_t));
    uint8_t *selected=calloc(bound,1);
    if (!types || !pointee || !selected) rt_fatal("point interface: allocation failed");
    for (uint64_t i=5;i<words;) {
        uint32_t n=code[i]>>16, op=code[i]&65535;
        if (!n || n>words-i) rt_fatal("point interface: malformed module");
        if (op==15 && n>=4) { if(entry) rt_fatal("point interface: multiple entries"); entry=code[i+2]; }
        if (op==32 && n==4 && code[i+1]<bound) pointee[code[i+1]]=code[i+3];
        if (op==59 && n>=4 && code[i+2]<bound && code[i+3]==1) types[code[i+2]]=code[i+1];
        if (op==71 && n==4 && code[i+1]<bound && code[i+2]==30 && code[i+3]<32 && (missing&(1u<<code[i+3])))
            selected[code[i+1]]=1;
        i+=n;
    }
    for (uint32_t id=0;id<bound;++id) if(selected[id]) {
        if(!types[id]) {selected[id]=0;continue;}
        uint32_t type=types[id]<bound?pointee[types[id]]:0;
        if(!type || (vector && vector!=type)) rt_fatal("point interface: unsupported varying type");
        vector=type; ++targets;
    }
    if(!targets) {free(types);free(pointee);free(selected);return NULL;}
    for(uint64_t i=5;i<words;i+=code[i]>>16)
        if((code[i]&65535)==23 && code[i]>>16==4 && code[i+1]==vector && code[i+3]==4) scalar=code[i+2];
    int float32=0;
    for(uint64_t i=5;i<words;i+=code[i]>>16)
        if((code[i]&65535)==22 && code[i]>>16==3 && code[i+1]==scalar && code[i+2]==32) float32=1;
    if(!float32) rt_fatal("point interface: expected float32 vec4 input");
    // New type/constant/variable IDs, then function-local result IDs.
    uint32_t private_vector=bound, private_scalar=bound+1, vec2=bound+2, input_vec2=bound+3,
             point=bound+4, zero=bound+5, one=bound+6, loaded=bound+7, x=bound+8, y=bound+9, value=bound+10;
    uint32_t *out=malloc((words+128+targets*3)*sizeof(uint32_t));
    if(!out) rt_fatal("point interface: output allocation failed");
    memcpy(out,code,5*sizeof(uint32_t)); out[3]=bound+11;
    uint64_t at=5;
    int annotation=0, globals=0, in_entry=0, saw_label=0, initialized=0, private_defined=0;
#define DF_SPV(...) do { const uint32_t row[]={__VA_ARGS__}; memcpy(out+at,row,sizeof row);at+=sizeof row/4; } while(0)
    for(uint64_t i=5;i<words;) {
        uint32_t n=code[i]>>16, op=code[i]&65535;
        if(!annotation && op>=19 && op<=39) {
            DF_SPV((4u<<16)|71,point,11,16); annotation=1; // BuiltIn PointCoord.
        }
        if(!globals && op==54) {
            DF_SPV((4u<<16)|32,private_scalar,6,scalar);
            DF_SPV((4u<<16)|23,vec2,scalar,2);
            DF_SPV((4u<<16)|32,input_vec2,1,vec2);
            DF_SPV((4u<<16)|59,input_vec2,point,1);
            DF_SPV((4u<<16)|43,scalar,zero,0);
            DF_SPV((4u<<16)|43,scalar,one,0x3f800000);
            globals=1;
        }
        if(op==54) in_entry=code[i+2]==entry;
        if(in_entry && saw_label && !initialized && op!=59) {
            DF_SPV((4u<<16)|61,vec2,loaded,point);
            DF_SPV((5u<<16)|81,scalar,x,loaded,0);
            DF_SPV((5u<<16)|81,scalar,y,loaded,1);
            DF_SPV((7u<<16)|80,vector,value,x,y,zero,one);
            for(uint32_t id=0;id<bound;++id) if(selected[id]) DF_SPV((3u<<16)|62,id,value);
            initialized=1;
        }
        if(in_entry && op==248) saw_label=1;
        if(op==15) {
            uint32_t first=3;
            while(first<n) { uint32_t v=code[i+first++]; if(!(v&255)||!(v&0xff00)||!(v&0xff0000)||!(v&0xff000000))break; }
            uint64_t begin=at;
            memcpy(out+at,code+i,first*sizeof(uint32_t));at+=first;
            for(uint32_t j=first;j<n;++j) if(code[1]>=0x10400 || code[i+j]>=bound || !selected[code[i+j]]) out[at++]=code[i+j];
            out[at++]=point;out[begin]=(uint32_t)(at-begin)<<16|15;
        } else if(op==71 && n>=3 && code[i+1]<bound && selected[code[i+1]]) {
            // Location/interpolation decorations no longer describe an Input.
        } else if(op==59 && n>=4 && code[i+2]<bound && selected[code[i+2]]) {
            // Emit its Private pointer type before the variable that needs it.
            if(!private_defined) {DF_SPV((4u<<16)|32,private_vector,6,vector);private_defined=1;}
            DF_SPV((4u<<16)|59,private_vector,code[i+2],6);
        } else {
            memcpy(out+at,code+i,n*sizeof(uint32_t));
            if((op==65||op==66) && n>=5 && code[i+3]<bound && selected[code[i+3]]) {
                if(n!=5)rt_fatal("point interface: unsupported input access chain");
                out[at+1]=private_scalar;
            }
            at+=n;
        }
        i+=n;
    }
#undef DF_SPV
    if(!initialized)rt_fatal("point interface: missing entry block");
    free(types);free(pointee);free(selected);*out_words=at;return out;
}
