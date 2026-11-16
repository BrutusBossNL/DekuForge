// Execute the emitted CAS-loop IR against an independent memory/float model.
using System;
using System.Collections.Generic;
using System.Reflection;

var asm = Assembly.LoadFrom(System.IO.Path.GetFullPath(args[0]));
Type T(string name) => asm.GetType("Ryujinx.Graphics.Shader." + name, true);
object Get(object obj, string name) => obj.GetType().GetProperty(name).GetValue(obj);
object Constant(uint value) => T("IntermediateRepresentation.OperandHelper").GetMethod("Const").Invoke(null,new object[]{unchecked((int)value)});
uint Bits(float f) => BitConverter.SingleToUInt32Bits(f);
float Float(uint u) => BitConverter.UInt32BitsToSingle(u);

void Check(string storage, uint initial, uint increment, uint expected, uint returned, bool collide=false) {
    var context = Activator.CreateInstance(T("Translation.EmitterContext"));
    var result = T("Instructions.InstEmit").GetMethod("EmitFloatAtomicAdd",BindingFlags.NonPublic|BindingFlags.Static)
        .Invoke(null,new object[]{context,Enum.Parse(T("IntermediateRepresentation.StorageKind"),storage),Constant(0),Constant(0),Constant(increment)});
    var ops = (Array)context.GetType().GetMethod("GetOperations").Invoke(context,null);
    var values = new Dictionary<object,uint>();
    var labels = new Dictionary<object,int>();
    string Name(object op) => Get(op,"Inst").ToString();
    object Dest(object op) => Get(op,"Dest");
    for(int i=0;i<ops.Length;i++) if(Name(ops.GetValue(i))=="MarkLabel") labels[Dest(ops.GetValue(i))]=i;
    uint Read(object value) => Get(value,"Type").ToString()=="Constant" ? unchecked((uint)(int)Get(value,"Value")) : values[value];
    uint memory=initial;
    int steps=0, atomics=0;
    for(int pc=0;pc<ops.Length;pc++) {
        if(++steps>1000) throw new Exception("CAS loop did not terminate");
        var op=ops.GetValue(pc);
        object Source(int n) => op.GetType().GetMethod("GetSource").Invoke(op,new object[]{n});
        uint S(int n) => Read(Source(n));
        string name=Name(op);
        uint output=0;
        if(name=="MarkLabel") continue;
        if(name=="BranchIfTrue") { if(S(0)!=0) pc=labels[Dest(op)]; continue; }
        if(name=="AtomicCompareAndSwap") {
            atomics++;
            if(collide && atomics==2) memory=Bits(Float(memory)+2f);
            output=memory;
            if(memory==S(2)) memory=S(3);
        }
        else if(name=="BitwiseAnd") output=S(0)&S(1);
        else if(name=="CompareEqual") output=S(0)==S(1) ? uint.MaxValue : 0;
        else if(name=="CompareNotEqual") output=S(0)!=S(1) ? uint.MaxValue : 0;
        else if(name=="ConditionalSelect") output=S(0)!=0 ? S(1) : S(2);
        else if(name.Contains("FP32") && name.Contains("Add")) output=Bits(Float(S(0))+Float(S(1)));
        else throw new Exception("Unexpected IR operation: "+name);
        values[Dest(op)]=output;
    }
    if(memory!=expected || Read(result)!=returned || (collide && atomics<4))
        throw new Exception($"{storage}: result {memory:x8}/{Read(result):x8}, expected {expected:x8}/{returned:x8}, atomics {atomics}");
}
Check("GlobalMemory",Bits(3),Bits(1.5f),Bits(4.5f),Bits(3));
Check("GlobalMemory",Bits(3),Bits(1.5f),Bits(6.5f),Bits(5),true);
Check("GlobalMemory",0x80000001,0x80000001,0x80000000,0x80000001);
Check("GlobalMemory",0x00800001,0x80800000,0,0x00800001);
Check("SharedMemory",1,1,2,1);
// IEEE NaN arithmetic's payload is host-defined; the important contract here
// is bitwise CAS comparison and termination, including a NaN original value.
uint nan=0x7fc00123;
Check("GlobalMemory",nan,Bits(1),Bits(Float(nan)+1f),nan);
Console.WriteLine("Six emitted-IR cases pass: sum, contention/retry, signed FTZ, underflow, shared denormals and NaN termination.");
