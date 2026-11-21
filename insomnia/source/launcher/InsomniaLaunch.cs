using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;

internal static class InsomniaLaunch
{
    private static string Quote(string value)
    {
        var quoted = new StringBuilder("\"");
        int slashes = 0;
        foreach (char ch in value)
        {
            if (ch == '\\') { slashes++; continue; }
            quoted.Append('\\', ch == '"' ? slashes * 2 + 1 : slashes);
            quoted.Append(ch); slashes = 0;
        }
        return quoted.Append('\\', slashes * 2).Append('"').ToString();
    }

    [STAThread]
    private static int Main(string[] args)
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string log = Path.Combine(root, "insomnia_launch.log");
        try
        {
            if (Process.GetProcessesByName("hl").Length != 0) return 2;
            string delta = Path.Combine(root, "cstrike", "delta.lst");
            string text = File.ReadAllText(delta);
            Match block = Regex.Match(text, @"(?ms)^entity_state_t[^\r\n]*\r?\n\{.*?^\}");
            if (!block.Success) throw new InvalidDataException("Missing entity delta descriptor");
            Regex body = new Regex(@"(DEFINE_DELTA\(\s*body,\s*DT_INTEGER,\s*)(8|32)(,)");
            if (body.Matches(block.Value).Count != 1) throw new InvalidDataException("Unexpected body descriptor");
            string patched = body.Replace(block.Value, "${1}32$3");
            if (patched != block.Value)
                File.WriteAllText(delta, text.Substring(0, block.Index) + patched + text.Substring(block.Index + block.Length));
            // This distribution regenerates delta.lst and clears the read-only
            // attribute at startup. A read handle also prevents replacement.
            using (var guard = new FileStream(delta, FileMode.Open, FileAccess.Read, FileShare.Read))
            {
                string command = args.Length == 0
                    ? "-game cstrike -console -nofbo +sv_lan 1 +mp_consistency 0 +cl_lw 0 +maxplayers 16"
                    : string.Join(" ", Array.ConvertAll(args, Quote));
                var start = new ProcessStartInfo(Path.Combine(root, "hl.exe"), command)
                { WorkingDirectory = root, UseShellExecute = false };
                using (Process game = Process.Start(start))
                {
                    File.AppendAllText(log, DateTime.Now.ToString("s") + " body32 guard held; game " + game.Id + Environment.NewLine);
                    game.WaitForExit();
                    return game.ExitCode;
                }
            }
        }
        catch (Exception error)
        {
            File.AppendAllText(log, DateTime.Now.ToString("s") + " " + error.Message + Environment.NewLine);
            return 1;
        }
    }
}
