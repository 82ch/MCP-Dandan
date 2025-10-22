using System;
using System.Linq;

namespace CursorProcessTree
{
    public static class NetworkEventHandler
    {
        public static void HandleNetworkEvent(string eventType, int pid, dynamic data)
        {
            // 필터 통합 처리
            if (!ETWFilter.ShouldHandleNetworkEvent(eventType, pid, data))
                return;

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

            string dest = $"{daddr}:{dport}";

            // --- 태그 상속 처리 ---
            int effectivePid = pid;
            System.Collections.Concurrent.ConcurrentDictionary<string, McpTagManager.TagState> pidTagMap = null;

            while (effectivePid > 0)
            {
                if (McpTagManager.tagStates.TryGetValue(effectivePid, out pidTagMap) && pidTagMap.Count > 0)
                    break;
                effectivePid = ProcessTracker.GetParentPid(effectivePid);
            }

            string chosenTag = null;

            if (pidTagMap != null && pidTagMap.Count > 0)
            {
                var activeTags = pidTagMap
                    .Where(kv => kv.Value.EffectiveDepth > 0)
                    .Select(kv => kv.Key)
                    .ToList();

                if (activeTags.Count > 0)
                {
                    if (McpTagManager.activeRemoteByPidTag.TryGetValue(effectivePid, out var remoteMap))
                    {
                        foreach (var t in activeTags)
                        {
                            if (remoteMap.TryGetValue(t, out var bound) &&
                                string.Equals(bound, dest, StringComparison.OrdinalIgnoreCase))
                            {
                                chosenTag = t;
                                break;
                            }
                        }
                    }

                    if (chosenTag == null && activeTags.Count == 1)
                    {
                        chosenTag = activeTags[0];
                        var map = McpTagManager.activeRemoteByPidTag.GetOrAdd(
                            effectivePid,
                            _ => new System.Collections.Concurrent.ConcurrentDictionary<string, string>()
                        );
                        map[chosenTag] = dest;
                    }
                }
            }

            // --- Fallback: 태그가 전혀 없을 경우 ---
            if (string.IsNullOrEmpty(chosenTag))
                chosenTag = "unlabeled";

            // 연결 정보는 실제 네트워크 pid 기준으로 저장
            ProcessTracker.pidConnections[pid] = dest;

            int indent = ProcessTracker.GetIndentLevel(pid);
            string spaces = new string(' ', indent * 2);

            // tag가 unlabeled면 출력문에서만 제거
            string tagText = string.Equals(chosenTag, "unlabeled", StringComparison.OrdinalIgnoreCase)
                ? ""
                : $" [tag={chosenTag}]";

            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine(
                $"{spaces}{eventType} PID={pid} {saddr}:{sport} -> {daddr}:{dport}, Size={size}{tagText}"
            );
            Console.ResetColor();

            ProcessTracker.LogLine(
                $"{eventType} PID={pid} {saddr}:{sport} -> {daddr}:{dport}, Size={size}{tagText}"
            );
        }
    }
}
