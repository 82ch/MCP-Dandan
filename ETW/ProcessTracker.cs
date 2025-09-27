using System.Collections.Concurrent;

namespace ETW
{
    public static class ProcessTracker
    {
        public static ConcurrentDictionary<ulong, string> KeyToPath = new();
        public static ConcurrentDictionary<int, string> TrackedPids = new();
        public static ConcurrentDictionary<int, string> ProcCmdline = new();
        public static string TargetProcName = "";

        public static ConcurrentDictionary<string, long> LogFileOffsets = new();
        public static ConcurrentDictionary<string, string> IpNameCache = new();
        public static ConcurrentDictionary<int, string> LastResolvedHostByPid = new();

        // Claude 메인 PID
        public static int RootPid = -1;
    }
}
