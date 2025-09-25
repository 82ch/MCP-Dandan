using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;

namespace CursorProcessTree
{
    public static class McpTagManager
    {
        public class TagState
        {
            public int UnknownDepth;
            public HashSet<string> ActiveIds = new(StringComparer.OrdinalIgnoreCase);
            public int EffectiveDepth => UnknownDepth + ActiveIds.Count;
        }

        public static readonly ConcurrentDictionary<int, ConcurrentDictionary<string, TagState>> tagStates =
            new();

        public static readonly ConcurrentDictionary<int, ConcurrentDictionary<string, string>> activeRemoteByPidTag =
            new();

        static readonly Regex ReStartAction = new(@"Handling\s+CallTool\s+action\s+for\s+tool\s+'([^']+)'",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);
        static readonly Regex ReCallingWithId = new(@"Calling\s+tool\s+'([^']+)'\s+with\s+toolCallId:\s*([^\s]+)",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);
        static readonly Regex ReSuccess = new(@"Successfully\s+called\s+tool\s+'([^']+)'",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);
        static readonly Regex ReFail = new(@"Failed\s+to\s+call\s+tool\s+'([^']+)'",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);
        static readonly Regex ReSuccessWithId = new(@"Successfully.*toolCallId:\s*([^\s]+)",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);
        static readonly Regex ReFailWithId = new(@"Failed.*toolCallId:\s*([^\s]+)",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        public static void UpdateTagStateFromLog(int pid, string tag, string content)
        {
            var pidMap = tagStates.GetOrAdd(pid, _ => new ConcurrentDictionary<string, TagState>());
            var state = pidMap.GetOrAdd(tag, _ => new TagState());

            int startUnknown = ReStartAction.Matches(content).Count;
            if (startUnknown > 0)
                state.UnknownDepth += startUnknown;

            foreach (Match m in ReCallingWithId.Matches(content))
            {
                var id = m.Groups[2]?.Value;
                if (!string.IsNullOrWhiteSpace(id))
                    state.ActiveIds.Add(id);
            }

            foreach (Match m in ReSuccessWithId.Matches(content))
            {
                var id = m.Groups[1]?.Value;
                if (!string.IsNullOrWhiteSpace(id))
                    state.ActiveIds.Remove(id);
            }
            foreach (Match m in ReFailWithId.Matches(content))
            {
                var id = m.Groups[1]?.Value;
                if (!string.IsNullOrWhiteSpace(id))
                    state.ActiveIds.Remove(id);
            }

            int endGeneric = ReSuccess.Matches(content).Count + ReFail.Matches(content).Count;
            for (int i = 0; i < endGeneric; i++)
            {
                if (state.UnknownDepth > 0) state.UnknownDepth--;
                else if (state.ActiveIds.Count > 0)
                {
                    var any = state.ActiveIds.First();
                    state.ActiveIds.Remove(any);
                }
            }

            if (ReSuccess.IsMatch(content) || ReFail.IsMatch(content))
            {
                state.ActiveIds.Clear();
                state.UnknownDepth = 0;
                if (activeRemoteByPidTag.TryGetValue(pid, out var tagMap))
                {
                    tagMap.TryRemove(tag, out _);
                }
            }

            if (state.EffectiveDepth <= 0)
            {
                if (activeRemoteByPidTag.TryGetValue(pid, out var tagMap))
                {
                    tagMap.TryRemove(tag, out _);
                }
            }
        }
    }
}
