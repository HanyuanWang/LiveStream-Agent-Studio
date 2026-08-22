using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

[assembly: AssemblyTitle("LiveAgent Studio")]
[assembly: AssemblyDescription("Local AI workspace for livestream commerce teams")]
[assembly: AssemblyCompany("LiveAgent Studio Contributors")]
[assembly: AssemblyProduct("LiveAgent Studio")]
[assembly: AssemblyCopyright("Copyright © 2026 LiveAgent Studio Contributors")]
[assembly: AssemblyVersion("0.2.0.0")]
[assembly: AssemblyFileVersion("0.2.0.0")]

internal static class LiveAgentStudioLauncher
{
    [STAThread]
    private static void Main()
    {
        Application.EnableVisualStyles();
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string script = Path.Combine(root, "liveagent-studio", "01_启动_LiveAgent_Studio.ps1");
        if (!File.Exists(script))
        {
            MessageBox.Show("启动文件不完整，请重新下载 Windows 发布包。", "LiveAgent Studio", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }

        try
        {
            var start = new ProcessStartInfo
            {
                FileName = "powershell.exe",
                Arguments = "-NoProfile -ExecutionPolicy Bypass -File \"" + script + "\"",
                WorkingDirectory = Path.GetDirectoryName(script),
                UseShellExecute = false,
                CreateNoWindow = true,
                WindowStyle = ProcessWindowStyle.Hidden
            };
            using (Process process = Process.Start(start))
            {
                process.WaitForExit();
                if (process.ExitCode != 0)
                {
                    MessageBox.Show("启动没有完成。请打开 docs\\常见问题.md 查看处理方法。", "LiveAgent Studio", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                }
            }
        }
        catch (Exception error)
        {
            MessageBox.Show("无法启动 LiveAgent Studio：\n" + error.Message, "LiveAgent Studio", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
