"""Check optimizer liveness with synthetic multi-result instruction graphs."""
import argparse
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assembly", type=Path, required=True)
    parser.add_argument("--dotnet", default="dotnet")
    args = parser.parse_args()
    folder = Path(__file__).resolve().parents[1] / "build/validation-optimizer"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "Check.csproj").write_text('''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework></PropertyGroup>
</Project>
''')
    # Reflection lets this standalone check exercise the actual internal IR
    # without changing the translator's visibility or production assembly.
    (folder / "Program.cs").write_text(r'''
using System;
using System.Reflection;
var asm = Assembly.LoadFrom(System.IO.Path.GetFullPath(args[0]));
Type T(string name) => asm.GetType("Ryujinx.Graphics.Shader." + name, true);
var operand = T("IntermediateRepresentation.Operand");
var operation = T("IntermediateRepresentation.Operation");
var instruction = T("IntermediateRepresentation.Instruction");
var nodeType = T("IntermediateRepresentation.INode");
var helper = T("IntermediateRepresentation.OperandHelper");
object Local() => helper.GetMethod("Local").Invoke(null, null);
object Constant(int n) => helper.GetMethod("Const").Invoke(null, new object[]{n});
Array Operands(params object[] items) {
    var array = Array.CreateInstance(operand, items.Length);
    for(int i=0;i<items.Length;i++) array.SetValue(items[i],i);
    return array;
}
object Op(string name, object[] dest, params object[] sources) =>
    Activator.CreateInstance(operation, new object[]{Enum.Parse(instruction,name),0,Operands(dest),Operands(sources)});
object Get(object obj,string name) => obj.GetType().GetProperty(name).GetValue(obj);
int Uses(object obj) => (int)Get(Get(obj,"UseOps"),"Count");
void Check(bool liveSibling, bool sideEffects) {
    var block = Activator.CreateInstance(T("IntermediateRepresentation.BasicBlock"));
    var list = Get(block,"Operations");
    object Add(object op) => list.GetType().GetMethod("AddLast",new[]{nodeType}).Invoke(list,new[]{op});
    var coordinate=Local(); var x=Local(); var y=Local(); var dead=Local();
    Add(Op("Copy",new[]{coordinate},Constant(7)));
    var producer=Op(sideEffects ? "AtomicAdd" : "ImageLoad",new[]{x,y},coordinate);
    Add(producer);
    var removed=Add(Op("Copy",new[]{dead},x));
    if(liveSibling) Add(Op("Copy",new[]{Local()},y));
    T("Translation.Optimizations.Optimizer").GetMethod("RemoveNode").Invoke(null,new[]{block,removed});
    int expected = liveSibling || sideEffects ? 1 : 0;
    if(Uses(coordinate)!=expected || Uses(x)!=0 || Uses(y)!=(liveSibling ? 1 : 0))
        throw new Exception($"Invalid liveness: sibling={liveSibling}, sideEffects={sideEffects}, coordinate uses={Uses(coordinate)}, expected={expected}");
}
Check(true,false);
Check(false,false);
Check(false,true);
Console.WriteLine("Live sibling inputs and side-effect inputs survive; fully dead inputs are released.");
''')
    environment = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT="1",
                       DOTNET_GENERATE_ASPNET_CERTIFICATE="false",
                       DOTNET_CLI_HOME=str(folder))
    subprocess.run([args.dotnet, "run", "--project", str(folder / "Check.csproj"),
                    "--configuration", "Release", "--", str(args.assembly.resolve())],
                   check=True, env=environment)


if __name__ == "__main__":
    main()
