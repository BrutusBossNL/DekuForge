// Original local bridge from the shader service to the validated native mesh wrapper.
using System;
using System.Diagnostics;
using System.IO;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

static class MeshDispatch
{
    public static string Translate(JsonObject job, string output)
    {
        string key = (string)job["key"];
        if (key == null || !Regex.IsMatch(key, "\\A[0-9a-f]{64}\\z")) return "Invalid mesh shader key";
        string configPath = Path.Combine(AppContext.BaseDirectory, "DekuForgeMesh.json");
        if (!File.Exists(configPath)) return "Native mesh build tools are not configured";
        var config = JsonNode.Parse(File.ReadAllText(configPath)).AsObject();
        string request = Path.Combine(output, key + ".mesh-job.json");
        Directory.CreateDirectory(output);
        File.WriteAllText(request, job.ToJsonString());
        var start = new ProcessStartInfo((string)config["python"])
        {
            UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardOutput = true, RedirectStandardError = true,
        };
        foreach (string argument in new[] { (string)config["worker"], request, output,
                                           Environment.ProcessPath, (string)config["tools"], (string)config["toolchain"] })
            start.ArgumentList.Add(argument);
        using var process = Process.Start(start);
        var stdout = process.StandardOutput.ReadToEndAsync();
        var stderr = process.StandardError.ReadToEndAsync();
        if (!process.WaitForExit(360000))
        {
            process.Kill(true);
            process.WaitForExit();
            return "Native mesh translation timed out";
        }
        // The parent service uses one reply line per request. Compiler diagnostics
        // must not become replies to subsequent requests on the same connection.
        return process.ExitCode == 0 ? null : (stderr.Result + stdout.Result).ReplaceLineEndings(" ");
    }
}
