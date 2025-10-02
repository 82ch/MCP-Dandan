using System;
using System.Collections.Concurrent;
using System.Text.RegularExpressions;

namespace ETW
{
    public static class EtwFilters
    {
        private static readonly string[] NoiseSubstrings =
        {
            @"\prefetch\", @"\resources\app.asar", @"\shadercache\",
            @"\dawnwebgpucache\", @"\dawngraphitecache\", @"\local storage\leveldb\",
            @"\shared dictionary\", @"\temp\", @"\cache\", @"\gpucache\",
            @"\code cache\", @"\spool\drivers\color\",
            @"\.venv\", @"\site-packages\", @"\__pycache__\",
            @"uv.lock", @"uv_cache.json", @"direct_url.json", @"pyvenv.cfg"
        };

        private static readonly Regex NoiseExtRegex = new Regex(
            @"\.(pf|ldb|bdic|ni\.dll\.aux|pyc|pyo|pyd|json|lock|cfg)$",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        private static readonly string[] KeepSubstrings =
        {
            "config.json", "claude_desktop_config.json", "local state",
            "\\logs\\", "\\crashpad\\", "\\sentry\\", "\\preferences", "\\hosts"
        };

        private static readonly ConcurrentDictionary<string, (DateTime ts, int count)> RecentEvents = new();
        private const int DedupWindowMs = 500;

        // 노이즈 판별
        public static bool IsNoisePath(string path, string kind = "", int pid = 0)
        {
            if (string.IsNullOrWhiteSpace(path)) return true;
            string p = path.ToLowerInvariant();

            foreach (var k in KeepSubstrings)
                if (p.Contains(k)) return false;

            if (NoiseExtRegex.IsMatch(p)) return true;
            foreach (var s in NoiseSubstrings)
                if (p.Contains(s)) return true;

            if (string.IsNullOrEmpty(System.IO.Path.GetFileName(p)))
            {
                if (kind.Equals("CLOSE", StringComparison.OrdinalIgnoreCase) ||
                    kind.Equals("READ", StringComparison.OrdinalIgnoreCase) ||
                    kind.Equals("DIRENUM", StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }

            return false;
        }

        // 중복 억제
        public static bool ShouldSuppress(string kind, int pid, string path, out int repeatCount)
        {
            repeatCount = 0;
            string key = $"{pid}:{kind}:{path}";
            var now = DateTime.UtcNow;

            if (RecentEvents.TryGetValue(key, out var last))
            {
                if ((now - last.ts).TotalMilliseconds < DedupWindowMs)
                {
                    RecentEvents[key] = (last.ts, last.count + 1);
                    return true;
                }
                else if (last.count > 0)
                {
                    repeatCount = last.count;
                }
            }

            RecentEvents[key] = (now, 0);
            return false;
        }

        // 최종 통합 함수
        public static bool ShouldIgnore(string kind, int pid, string path, out int repeatCount)
        {
            repeatCount = 0;

            if (IsNoisePath(path, kind, pid))
                return true;

            if (ShouldSuppress(kind, pid, path, out repeatCount))
                return true;

            return false;
        }
    }
}
