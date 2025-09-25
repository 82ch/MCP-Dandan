using System;
using System.Linq;

namespace CursorProcessTree
{
    public static class NetworkEventHandler
    {
        public static void HandleNetworkEvent(string eventType, int pid, dynamic data)
        {
            if (!ProcessTracker.IsChildOfTarget(pid)) return;

            lock (ProcessTracker.mcpPids)
            {
                if (!ProcessTracker.mcpPids.Contains(pid)) return;
            }

            string saddr = "", daddr = "";
            int sport = -1, dport = -1, size = -1;

            try
            {
                saddr = data.saddr?.ToString() ?? "";
                daddr = data.daddr?.ToString() ?? "";
                sport = Convert.ToInt32(data.sport);
                dport = Convert.ToInt32(data.dport);
                size = Convert.ToInt32(data.size);
            }
            catch { }

            if (string.IsNullOrEmpty(daddr) || dport <= 0) return;
            string dest = $"{daddr}:{dport}";

            if (!McpTagManager.tagStates.TryGetValue(pid, out var pidTagMap) || pidTagMap.Count == 0) return;

            var activeTags = pidTagMap.Where(kv => kv.Value.EffectiveDepth > 0)
                                      .Select(kv => kv.Key)
                                      .ToList();
            if (activeTags.Count == 0) return;

            string chosenTag = null;

            if (McpTagManager.activeRemoteByPidTag.TryGetValue(pid, out var remoteMap))
            {
                foreach (var t in activeTags)
                {
                    if (remoteMap.TryGetValue(t, out var bound) && string.Equals(bound, dest, StringComparison.OrdinalIgnoreCase))
                    {
                        chosenTag = t;
                        break;
                    }
                }
            }

            if (chosenTag == null)
            {
                if (activeTags.Count == 1)
                {
                    chosenTag = activeTags[0];
                    var map = McpTagManager.activeRemoteByPidTag.GetOrAdd(pid, _ => new System.Collections.Concurrent.ConcurrentDictionary<string, string>());
                    map[chosenTag] = dest;
                }
                else
                {
                    return;
                }
            }

            if (!pidTagMap.TryGetValue(chosenTag, out var state) || state.EffectiveDepth <= 0)
                return;

            var tagRemoteMap = McpTagManager.activeRemoteByPidTag.GetOrAdd(pid, _ => new System.Collections.Concurrent.ConcurrentDictionary<string, string>());
            if (tagRemoteMap.TryGetValue(chosenTag, out var boundDest))
            {
                if (!string.Equals(boundDest, dest, StringComparison.OrdinalIgnoreCase))
                {
                    return;
                }
            }
            else
            {
                tagRemoteMap[chosenTag] = dest;
            }

            ProcessTracker.pidConnections[pid] = dest;

            int indent = ProcessTracker.GetIndentLevel(pid);
            string spaces = new string(' ', indent * 2);

            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine($"{spaces}{eventType} PID={pid} {saddr}:{sport} -> {daddr}:{dport}, Size={size} [tag={chosenTag}]");
            Console.ResetColor();

            ProcessTracker.LogLine($"{eventType} PID={pid} {saddr}:{sport} -> {daddr}:{dport}, Size={size} [tag={chosenTag}]");
        }
    }
}
