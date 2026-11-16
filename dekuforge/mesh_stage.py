"""Bounded NVN2 task/mesh metadata for the independent Vulkan shader path.

ABI reference: nxnative dm/gfx/tools/dmsh_meshstage.py (MIT). This describes
stage memory; a translated compute kernel still needs native stage wrapping.
"""
import struct
import re


def outputs(header):
    if len(header) < 0x80:
        raise ValueError("Truncated mesh shader header")
    result = [("point_size", 0)] if header[0x35] & 8 else []
    result += [("position", component) for component in range(4) if header[0x35] & (16 << component)]
    for location in range(32):
        mask = (header[0x36 + location // 2] >> (4 * (location % 2))) & 15
        result.extend((location, c) for c in range(4) if mask & (1 << c))
    return result


def metadata(control, code):
    if len(control) < 0xd8 or control[:8] != struct.pack("<II", 0x98761234, 0xc9):
        raise ValueError("Invalid NVN2 control")
    kind = {6: "task", 7: "mesh"}.get(control[0x56])
    if not kind:
        raise ValueError("Not a task or mesh stage")
    instruction_end = struct.unpack_from("<I", control, 0x38)[0]
    constants, total = struct.unpack_from("<II", control, 0x40)
    if not 0x80 < instruction_end <= constants <= total <= len(code) or total > 16 << 20:
        raise ValueError("Invalid task/mesh code extent")
    threads = struct.unpack_from("<H", control, 0x58)[0]
    # The high byte holds 256-byte data units; the adjacent byte is flags.
    # Task payloads also carry a 32-byte header, outside the encoded data size.
    payload = control[0x5b] * 256
    if kind == "task" or control[0x5e]:
        payload = max(payload, 256) + 32
    if threads < 1 or threads > 1024 or payload > 16384:
        raise ValueError("Unsupported task/mesh workgroup or payload size")
    output = 16 + ((payload + 15) & ~15)
    info = {"kind": kind, "threads": threads, "payload": payload,
            "instructions": instruction_end, "constants": constants, "total": total}
    if kind == "task":
        primitive = output + payload
        shared = output + ((payload + 3) & ~3)
    else:
        vertices, primitives = struct.unpack_from("<HH", control, 0x60)
        topology = control[0x5f] or 3
        if not 1 <= vertices <= 256 or not 1 <= primitives <= 512 or topology not in (1, 2, 3):
            raise ValueError("Unsupported mesh output limits")
        vertex = outputs(code[:0x80])
        primitive_at = struct.unpack_from("<I", control, 0x64)[0] if control[0x68] & 0x80 else 0
        if primitive_at and not 0x80 <= primitive_at <= total - 0x80:
            raise ValueError("Primitive shader header is outside its code section")
        ph = code[primitive_at:primitive_at + 0x80] if primitive_at else bytes(0x80)
        primitive_outputs = [(n, c) for n, c in outputs(ph) if isinstance(n, int)]
        system = ph[0x34] | ((ph[0x35] & 15) << 8)
        system_count = system.bit_count()
        vb, pb = (vertices + 31) // 32, (primitives + 31) // 32
        primitive = output + max(vb * len(vertex) + pb * (system_count + len(primitive_outputs)), 1) * 128
        shared = primitive + ((4 + topology * pb * 32 + 3) & ~3)
        info.update(vertices=vertices, primitives=primitives, topology=topology, vertex=vertex,
                    primitive=primitive_outputs, primitive_system=system, task=bool(control[0x5e]))
    if shared > 65536:
        raise ValueError("Mesh stage memory exceeds the validation limit")
    info.update(stage_memory=[0, 16, output, primitive], shared=shared)
    return info


def vulkan_stage(kernel, info, checks_binding=None):
    """Wrap a validated compute kernel's stage memory in VK_EXT_mesh_shader IO."""
    arrays = re.findall(r"shared\s+uint\s+(\w+)\[(\d+)\];", kernel)
    if len(arrays) != 1 or int(arrays[0][1]) * 4 != info["shared"]:
        raise ValueError("Expected exactly the declared shared stage memory")
    if kernel.count("void main()") != 1:
        raise ValueError("Shader kernel entry is ambiguous")
    shared = arrays[0][0]
    source = kernel.replace("#version 450", "#version 460\n#extension GL_EXT_mesh_shader : require\n#extension GL_EXT_buffer_reference : require\n#extension GL_EXT_buffer_reference_uvec2 : require", 1)
    source = source.replace("void main()", "void df_stage_body()", 1)
    out = info["stage_memory"][2] // 4
    primitive = info["stage_memory"][3]
    words, threads = info["shared"] // 4, info["threads"]
    payload_words = max(1, (info["payload"] + 3) // 4)
    prefix = "layout(buffer_reference, std430, buffer_reference_align=4) readonly buffer DfIndirect { uint first; };\n"
    prefix += "layout(push_constant) uniform DfMeshDraw { uint first; uint count; uvec2 address; } df_draw;\n"
    prefix += "uint df_first() { return any(notEqual(df_draw.address,uvec2(0))) ? DfIndirect(df_draw.address).first : df_draw.first; }\n"
    if checks_binding is not None:
        prefix += f"layout(set=0,binding={checks_binding},std430) buffer DfMeshChecks {{ uint words[]; }} df_checks;\n"
        prefix += """void df_output_fault(uint kind, uint value, uint limit) {
    if (atomicCompSwap(df_checks.words[0],0u,1u)==0u) {
        df_checks.words[1]=kind; df_checks.words[2]=value; df_checks.words[3]=limit;
        df_checks.words[4]=gl_WorkGroupID.x; df_checks.words[6]=gl_LocalInvocationIndex;
        DF_CHECK_ID
        memoryBarrierBuffer(); atomicExchange(df_checks.words[0],2u);
    }
}
"""
        prefix = prefix.replace("DF_CHECK_ID", f"df_checks.words[8]={info.get('diagnostic_tag', 0)}u; df_checks.words[9]={6 if info['kind']=='task' else 7}u;")
    if info["kind"] == "task" or info.get("task"):
        prefix += f"struct DfPayload {{ uint words[{payload_words}]; }};\ntaskPayloadSharedEXT DfPayload df_payload;\n"
    body = ["void main() {", "uint lid = gl_LocalInvocationIndex;",
            f"for (uint i=lid; i<{words}u; i+={threads}u) {shared}[i]=0u;", "barrier();"]
    if info["kind"] == "task":
        if info["payload"] < 8:
            raise ValueError("Task output requires a launch-count word")
        body += [f"if(lid==0u) {shared}[0]=df_first()+gl_WorkGroupID.x;", "barrier();", "df_stage_body();", "barrier();",
                 f"for(uint i=lid;i<{payload_words}u;i+={threads}u) df_payload.words[i]={shared}[{out}u+i];",
                 "barrier();"]
        if checks_binding is not None:
            body += [f"uint launches={shared}[{out+1}];",
                     "if(lid==0u) atomicMax(df_checks.words[5],launches);",
                     "if(launches>df_checks.words[7]) { if(lid==0u) df_output_fault(1u,launches,df_checks.words[7]); launches=0u; }",
                     "EmitMeshTasksEXT(launches,1u,1u);"]
        else:
            body += [f"EmitMeshTasksEXT({shared}[{out+1}],1u,1u);"]
        body += ["}"]
        return source + "\n" + prefix + "\n".join(body)
    vertices, primitives, topology = info["vertices"], info["primitives"], info["topology"]
    topology_name = {1: "points", 2: "lines", 3: "triangles"}[topology]
    prefix += f"layout({topology_name}, max_vertices={vertices}, max_primitives={primitives}) out;\n"
    # Depth-only and colour passes must agree on the position, as native vertex
    # stages already require. Keep that contract when wrapping a mesh kernel.
    prefix += "out gl_MeshPerVertexEXT { invariant vec4 gl_Position; float gl_PointSize; } gl_MeshVerticesEXT[];\n"
    generic = sorted({n for n, c in info["vertex"] if isinstance(n, int)})
    per_primitive = sorted({n for n, c in info["primitive"]})
    if set(generic) & set(per_primitive):
        raise ValueError("Overlapping vertex and primitive attribute locations")
    for n in generic:
        prefix += f"layout(location={n}) out vec4 df_attr_{n}[];\n"
    for n in per_primitive:
        prefix += f"layout(location={n}) perprimitiveEXT out vec4 df_prim_{n}[];\n"
    if info.get("task"):
        body += [f"for(uint i=lid;i<{payload_words}u;i+={threads}u) {shared}[4u+i]=df_payload.words[i];", "barrier();",
                 f"if(lid==0u) {{ {shared}[0]=gl_WorkGroupID.x; {shared}[4]=gl_WorkGroupID.x; }}"]
    else:
        body += [f"if(lid==0u) {shared}[0]=df_first()+gl_WorkGroupID.x;"]
    body += ["barrier();", "df_stage_body();", "barrier();"]
    if checks_binding is not None:
        body += [f"uint actual_primitives=({shared}[{primitive//4}]>>24u)&255u;",
                 f"if(lid==0u && actual_primitives>{primitives}u) df_output_fault(2u,actual_primitives,{primitives}u);"]
    body += [
             f"uint np=min(({shared}[{primitive//4}]>>24u)&255u,{primitives}u);",
             f"SetMeshOutputsEXT({vertices}u,np);", f"for(uint v=lid;v<{vertices}u;v+={threads}u) {{",
             f"uint base={out}u+(v/32u)*{len(info['vertex'])*32}u+(v%32u);"]
    def vector(components, location):
        parts = []
        for c in range(4):
            pair = (location, c)
            index = next((i for i, item in enumerate(components) if tuple(item) == pair), None)
            parts.append(f"uintBitsToFloat({shared}[base+{index*32}u])" if index is not None else "1.0" if c == 3 else "0.0")
        return "vec4(" + ",".join(parts) + ")"
    body += ["vec4 df_position=" + vector(info["vertex"], "position") + ";",
             "gl_MeshVerticesEXT[v].gl_Position=df_position;"]
    if checks_binding is not None:
        body += ["if(v==0u && np>0u && df_checks.words[19]!=0u) {",
                 "uint sample_index=atomicAdd(df_checks.words[18],1u);",
                 "if(sample_index<512u) { uint at=20u+sample_index*8u;",
                 f"df_checks.words[at]={info.get('diagnostic_tag', 0)}u;",
                 "df_checks.words[at+1u]=gl_WorkGroupID.x;",
                 "df_checks.words[at+2u]=df_first(); df_checks.words[at+3u]=np;",
                 "uvec4 bits=floatBitsToUint(df_position);",
                 "df_checks.words[at+4u]=bits.x; df_checks.words[at+5u]=bits.y;",
                 "df_checks.words[at+6u]=bits.z; df_checks.words[at+7u]=bits.w;", "}", "}"]
        body += ["if(v==0u && df_checks.words[17]!=0u) {",
                 "atomicMax(df_checks.words[11],np);",
                 "if(np>0u && atomicCompSwap(df_checks.words[10],0u,1u)==0u) {",
                 "uvec4 bits=floatBitsToUint(df_position);",
                 "df_checks.words[12]=bits.x; df_checks.words[13]=bits.y;",
                 "df_checks.words[14]=bits.z; df_checks.words[15]=bits.w;",
                 f"df_checks.words[16]={info.get('diagnostic_tag', 0)}u;",
                 "memoryBarrierBuffer(); atomicExchange(df_checks.words[10],2u);", "}", "}"]
    for n in generic:
        body += [f"df_attr_{n}[v]=" + vector(info["vertex"], n) + ";"]
    if any(n == "point_size" for n, c in info["vertex"]):
        index = next(i for i, (n, c) in enumerate(info["vertex"]) if n == "point_size")
        body += [f"gl_MeshVerticesEXT[v].gl_PointSize=uintBitsToFloat({shared}[base+{index*32}u]);"]
    system_count = info["primitive_system"].bit_count()
    start = out + ((vertices+31)//32)*len(info["vertex"])*32
    body += ["}", f"for(uint p=lid;p<np;p+={threads}u) {{",
             f"uint base={start}u+(p/32u)*{(system_count+len(info['primitive']))*32}u+(p%32u);"]
    system_locations = [i for i in range(12) if info["primitive_system"] & (1 << i)]
    for bit, member in ((8, "gl_PrimitiveID"), (9, "gl_Layer"), (10, "gl_ViewportIndex")):
        if bit in system_locations:
            body += [f"gl_MeshPrimitivesEXT[p].{member}=int({shared}[base+{system_locations.index(bit)*32}u]);"]
    body += [f"base+={system_count*32}u;"]
    for n in per_primitive:
        body += [f"df_prim_{n}[p]=" + vector(info["primitive"], n) + ";"]
    indices = []
    for component in range(topology):
        body += [f"uint a{component}={primitive+4}u+p*{topology}u+{component}u;",
                 f"uint i{component}=({shared}[a{component}/4u]>>((a{component}%4u)*8u))&255u;"]
        if checks_binding is not None:
            body += [f"if(i{component}>={vertices}u) {{ df_output_fault(3u,i{component},{vertices}u); i{component}=0u; }}"]
        indices.append(f"i{component}")
    index_builtin = {1: "gl_PrimitivePointIndicesEXT", 2: "gl_PrimitiveLineIndicesEXT", 3: "gl_PrimitiveTriangleIndicesEXT"}[topology]
    value = indices[0] if topology == 1 else f"uvec{topology}(" + ",".join(indices) + ")"
    body += [f"{index_builtin}[p]={value};", "}", "}"]
    return source + "\n" + prefix + "\n".join(body)
