// -*- mode:c++ -*-

// Copyright (c) 2020 Metempsy Technology Consulting
// All rights reserved
//
// The license below extends only to copyright in the software and shall
// not be construed as granting a license to any other intellectual
// property including but not limited to intellectual property relating
// to a hardware implementation of the functionality of the software
// licensed hereunder.  You may use the software subject to the license
// terms below provided that you ensure that this notice is replicated
// unmodified and in its entirety in all distributions of the software,
// modified or unmodified, in source code or in binary form.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are
// met: redistributions of source code must retain the above copyright
// notice, this list of conditions and the following disclaimer;
// redistributions in binary form must reproduce the above copyright
// notice, this list of conditions and the following disclaimer in the
// documentation and/or other materials provided with the distribution;
// neither the name of the copyright holders nor the names of its
// contributors may be used to endorse or promote products derived from
// this software without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
// "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
// LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
// A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
// OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
// SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
// LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
// DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
// THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

// Adapted by DekuForge from gem5 9d368896ce119c17e1289dcbb18f33624724b843: portable C, explicit nibble extraction.
#pragma once
#include <stdint.h>
static inline uint8_t df_qarma_cell(uint64_t x, unsigned n) { return (uint8_t)((x >> (4*n)) & 15u); }

static inline uint8_t
df_qarma_rotCell(uint8_t incell, int amount)
{
    uint8_t res =  ((incell << amount) | (incell >> (4-amount)))& 0xF;
    return res;
}

static inline uint8_t
df_qarma_tweakCellInvRot(uint8_t incell)
{
    uint8_t outcell = 0x0;
    outcell = incell << 1;
    uint8_t t = 0x1 & (incell ^ (incell>>3));
    outcell |= t;
    return outcell & 0xF;
}

static inline uint8_t
df_qarma_tweakCellRot(uint8_t incell)
{
    uint8_t outcell = 0x0;
    outcell = incell >> 1;
    uint8_t t = 0x1 & (incell ^ (incell>>1));
    outcell |= t<<3;
    return outcell & 0xF;
}

static inline uint64_t
df_qarma_tweakInvShuffle(uint64_t indata)
{
    uint64_t outdata = 0x0;
    outdata |= ((uint64_t)(df_qarma_tweakCellInvRot(df_qarma_cell(indata, 12))) & 15u) << 0;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 13)) & 15u) << 4;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 5)) & 15u) << 8;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 6)) & 15u) << 12;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 0)) & 15u) << 16;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 1)) & 15u) << 20;
    outdata |= ((uint64_t)(df_qarma_tweakCellInvRot(df_qarma_cell(indata, 2))) & 15u) << 24;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 3)) & 15u) << 28;
    outdata |= ((uint64_t)(df_qarma_tweakCellInvRot(df_qarma_cell(indata, 7))) & 15u) << 32;
    outdata |= ((uint64_t)(df_qarma_tweakCellInvRot(df_qarma_cell(indata, 15))) & 15u) << 36;
    outdata |= ((uint64_t)(df_qarma_tweakCellInvRot(df_qarma_cell(indata, 14))) & 15u) << 40;
    outdata |= ((uint64_t)(df_qarma_tweakCellInvRot(df_qarma_cell(indata, 4))) & 15u) << 44;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 8)) & 15u) << 48;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 9)) & 15u) << 52;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 10)) & 15u) << 56;
    outdata |= ((uint64_t)(df_qarma_tweakCellInvRot(df_qarma_cell(indata, 11))) & 15u) << 60;
    return outdata;
}

static inline uint64_t
df_qarma_tweakShuffle(uint64_t indata)
{
    uint64_t outdata = 0x0;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 4)) & 15u) << 0;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 5)) & 15u) << 4;
    outdata |= ((uint64_t)(df_qarma_tweakCellRot(df_qarma_cell(indata, 6))) & 15u) << 8;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 7)) & 15u) << 12;
    outdata |= ((uint64_t)(df_qarma_tweakCellRot(df_qarma_cell(indata, 11))) & 15u) << 16;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 2)) & 15u) << 20;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 3)) & 15u) << 24;
    outdata |= ((uint64_t)(df_qarma_tweakCellRot(df_qarma_cell(indata, 8))) & 15u) << 28;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 12)) & 15u) << 32;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 13)) & 15u) << 36;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 14)) & 15u) << 40;
    outdata |= ((uint64_t)(df_qarma_tweakCellRot(df_qarma_cell(indata, 15))) & 15u) << 44;
    outdata |= ((uint64_t)(df_qarma_tweakCellRot(df_qarma_cell(indata, 0))) & 15u) << 48;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 1)) & 15u) << 52;
    outdata |= ((uint64_t)(df_qarma_tweakCellRot(df_qarma_cell(indata, 10))) & 15u) << 56;
    outdata |= ((uint64_t)(df_qarma_tweakCellRot(df_qarma_cell(indata, 9))) & 15u) << 60;
    return outdata;
}


static inline uint64_t
df_qarma_PACCellInvShuffle(uint64_t indata)
{
    uint64_t outdata = 0x0;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 3)) & 15u) << 0;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 6)) & 15u) << 4;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 12)) & 15u) << 8;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 9)) & 15u) << 12;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 14)) & 15u) << 16;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 11)) & 15u) << 20;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 1)) & 15u) << 24;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 4)) & 15u) << 28;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 8)) & 15u) << 32;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 13)) & 15u) << 36;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 7)) & 15u) << 40;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 2)) & 15u) << 44;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 5)) & 15u) << 48;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 0)) & 15u) << 52;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 10)) & 15u) << 56;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 15)) & 15u) << 60;
    return outdata;
}

static inline uint64_t
df_qarma_PACCellShuffle(uint64_t indata)
{
    uint64_t outdata = 0x0;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 13)) & 15u) << 0;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 6)) & 15u) << 4;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 11)) & 15u) << 8;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 0)) & 15u) << 12;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 7)) & 15u) << 16;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 12)) & 15u) << 20;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 1)) & 15u) << 24;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 10)) & 15u) << 28;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 8)) & 15u) << 32;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 3)) & 15u) << 36;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 14)) & 15u) << 40;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 5)) & 15u) << 44;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 2)) & 15u) << 48;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 9)) & 15u) << 52;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 4)) & 15u) << 56;
    outdata |= ((uint64_t)(df_qarma_cell(indata, 15)) & 15u) << 60;
    return outdata;
}


static inline uint64_t
df_qarma_PACInvSub(uint64_t tInput)
{
    // This is a 4-bit substitution from the PRINCE-family cipher
    uint64_t t_output = 0x0;
    for (int i=15; i>=0; i--) {
        t_output = t_output << 4;
        uint8_t b = (tInput >> i*4 ) & 0xF;
        switch ( b ) {
            case 0x0:
                t_output |= 0x5;
                break;
            case 0x1:
                t_output |= 0xe;
                break;
            case 0x2:
                t_output |= 0xd;
                break;
            case 0x3:
                t_output |= 0x8;
                break;
            case 0x4:
                t_output |= 0xa;
                break;
            case 0x5:
                t_output |= 0xb;
                break;
            case 0x6:
                t_output |= 0x1;
                break;
            case 0x7:
                t_output |= 0x9;
                break;
            case 0x8:
                t_output |= 0x2;
                break;
            case 0x9:
                t_output |= 0x6;
                break;
            case 0xa:
                t_output |= 0xf;
                break;
            case 0xb:
                t_output |= 0x0;
                break;
            case 0xc:
                t_output |= 0x4;
                break;
            case 0xd:
                t_output |= 0xc;
                break;
            case 0xe:
                t_output |= 0x7;
                break;
            case 0xf:
                t_output |= 0x3;
                break;
            default:
                //unreachable
                break;
        }
    }
    return t_output;
}

static inline uint64_t
df_qarma_PACSub(uint64_t tInput){
    // This is a 4-bit substitution from the PRINCE-family cipher
    uint64_t t_output = 0x0;
    for (int i=15; i>=0; i--) {
        t_output = t_output << 4;
        uint8_t b = (tInput >> i*4 ) & 0xF;
        switch ( b ) {
            case 0x0:
                t_output |= 0xb;
                break;
            case 0x1:
                t_output |= 0x6;
                break;
            case 0x2:
                t_output |= 0x8;
                break;
            case 0x3:
                t_output |= 0xf;
                break;
            case 0x4:
                t_output |= 0xc;
                break;
            case 0x5:
                t_output |= 0x0;
                break;
            case 0x6:
                t_output |= 0x9;
                break;
            case 0x7:
                t_output |= 0xe;
                break;
            case 0x8:
                t_output |= 0x3;
                break;
            case 0x9:
                t_output |= 0x7;
                break;
            case 0xa:
                t_output |= 0x4;
                break;
            case 0xb:
                t_output |= 0x5;
                break;
            case 0xc:
                t_output |= 0xd;
                break;
            case 0xd:
                t_output |= 0x2;
                break;
            case 0xe:
                t_output |= 0x1;
                break;
            case 0xf:
                t_output |= 0xa;
                break;
            default:
                //unreachable
                break;
        }
    }
    return t_output;
}

static inline uint64_t
df_qarma_PACMult(uint64_t tInput)
{
    uint64_t t_output = 0;

    for (int i=0;i<=3; i++) {
        uint8_t b8  = (tInput >> (4*(i+8)))  & 0xF;
        uint8_t b4  = (tInput >> (4*(i+4)))  & 0xF;
        uint8_t b12 = (tInput >> (4*(i+12))) & 0xF;
        uint8_t b0  = (tInput >> (4*(i)))    & 0xF;

        uint64_t t0 = df_qarma_rotCell(b8, 1) ^ df_qarma_rotCell(b4, 2);
        t0 = t0 ^ df_qarma_rotCell(b0, 1);

        uint64_t t1 = df_qarma_rotCell(b12, 1) ^ df_qarma_rotCell(b4, 1);
        t1 = t1 ^ df_qarma_rotCell(b0, 2);

        uint64_t t2 = df_qarma_rotCell(b12, 2) ^ df_qarma_rotCell(b8, 1);
        t2 = t2 ^ df_qarma_rotCell(b0, 1);

        uint64_t t3 = df_qarma_rotCell(b12, 1) ^ df_qarma_rotCell(b8, 2);
        t3 = t3 ^ df_qarma_rotCell(b4, 1);

        t_output |= (t3 << (4*i));
        t_output |= (t2 << (4*(i+4)));
        t_output |= (t1 << (4*(i+8)));
        t_output |= (t0 << (4*(i+12)));
    }
    return t_output;
}

static inline uint64_t
df_qarma_computePAC(uint64_t data, uint64_t modifier, uint64_t key0, uint64_t key1)
{
    uint64_t workingval;
    uint64_t runningmod;
    uint64_t roundkey;
    uint64_t modk0;
    uint64_t RC[5];
    RC[0] = (uint64_t) 0x0000000000000000;
    RC[1] = (uint64_t) 0x13198A2E03707344;
    RC[2] = (uint64_t) 0xA4093822299F31D0;
    RC[3] = (uint64_t) 0x082EFA98EC4E6C89;
    RC[4] = (uint64_t) 0x452821E638D01377;

    const uint64_t alpha = 0xC0AC29B7C97C50DD;
    //modk0 = key0<0>:key0<63:2>:

    modk0 = (key0 & 0x1) << 63;
    modk0 = modk0 | ((key0 & ~0x3) >> 1);
    modk0 = modk0 | ((df_qarma_cell(key0, 15)>>3) ^ ((df_qarma_cell(key0, 0) & 0x2)>>1));

    runningmod = modifier;
    workingval = data^key0;
    for (int i=0; i<=4; i++) {
        roundkey = key1 ^ runningmod;
        workingval = workingval ^ roundkey;
        workingval = workingval ^ RC[i];

        if (i > 0) {
            workingval = df_qarma_PACCellShuffle(workingval);
            workingval = df_qarma_PACMult(workingval);
        }
        workingval = df_qarma_PACSub(workingval);
        runningmod = df_qarma_tweakShuffle(runningmod);
    }
    roundkey = modk0 ^ runningmod;
    workingval = workingval ^ roundkey;

    workingval = df_qarma_PACCellShuffle(workingval);
    workingval = df_qarma_PACMult(workingval);
    workingval = df_qarma_PACSub(workingval);
    workingval = df_qarma_PACCellShuffle(workingval);
    workingval = df_qarma_PACMult(workingval);
    workingval = key1 ^ workingval;

    workingval = df_qarma_PACCellInvShuffle(workingval);
    workingval = df_qarma_PACInvSub(workingval);
    workingval = df_qarma_PACMult(workingval);
    workingval = df_qarma_PACCellInvShuffle(workingval);
    workingval = workingval ^ key0;
    workingval = workingval ^ runningmod;

    for (int i=0; i<=4; i++) {
        workingval = df_qarma_PACInvSub(workingval);
        if (i < 4) {
            workingval = df_qarma_PACMult(workingval);
            workingval = df_qarma_PACCellInvShuffle(workingval);
        }
        runningmod = df_qarma_tweakInvShuffle(runningmod);
        roundkey = key1 ^ runningmod;
        workingval = workingval ^ RC[4-i];
        workingval = workingval ^ roundkey;
        workingval = workingval ^ alpha;
    }
    workingval = workingval ^ modk0;
    return workingval;
}
