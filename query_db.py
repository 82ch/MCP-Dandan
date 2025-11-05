import asyncio
import json
from database import Database
from datetime import datetime
from collections import Counter, defaultdict


async def main():
    # 데이터베이스 연결
    db = Database()
    await db.connect()

    print("=" * 80)
    print("82ch MCP Observer - Database Query Tool")
    print("=" * 80)
    print()

    # 통계 조회
    print("전체 통계:")
    print("-" * 80)
    stats = await db.get_event_statistics()
    print(f"총 이벤트 수: {stats.get('total_events', 0):,}")
    print(f"탐지된 이벤트 수: {stats.get('detected_events', 0):,}")
    print()

    print("이벤트 타입별 통계:")
    by_type = stats.get("by_type", {})
    for event_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
        print(f"  {event_type:20s}: {count:,}")
    print()

    # Remote MCP 해시 → 서버 이름 매핑
    remote_server_map = {}
    async with db.conn.execute(
        """
        SELECT mcpTag, data
        FROM raw_events
        WHERE producer = 'remote' AND event_type = 'MCP'
        """
    ) as cursor:
        rows = await cursor.fetchall()
        for mcp_tag, data_str in rows:
            if not mcp_tag or not data_str:
                continue
            try:
                data = json.loads(data_str)
                msg = data.get("message", {})
                result = msg.get("result", {})
                server_info = result.get("serverInfo", {})
                name = server_info.get("name")
                if name:
                    remote_server_map[mcp_tag] = name
            except Exception:
                continue

    # 최근 이벤트 조회
    print("최근 이벤트 (10개):")
    print("-" * 80)
    recent = await db.get_recent_events(limit=10)
    for event in recent:
        ts = event["ts"]
        try:
            unix_timestamp = (ts / 10000000) - 62135596800
            dt = datetime.fromtimestamp(unix_timestamp)
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        except (OSError, ValueError):
            time_str = f"ts={ts}"

        mcp_tag = event.get("mcpTag", "-")
        producer = event["producer"]
        event_type = event["event_type"]

        # Remote MCP만 이름 치환
        if producer == "remote" and event_type == "MCP" and mcp_tag in remote_server_map:
            mcp_tag = remote_server_map[mcp_tag]

        print(
            f"[{event['id']:4d}] {time_str} | "
            f"{event_type:15s} | {producer:8s} | {mcp_tag}"
        )
    print()

    # Semantic Gap 결과
    print("Semantic Gap 결과:")
    print("-" * 80)
    try:
        high_scores = await db.get_high_semantic_gap_results(threshold=70, limit=10)
        if high_scores:
            for result in high_scores:
                score = result.get("final_score", 0)
                event_type = result.get("event_type", "Unknown")
                print(f"점수: {score:3d} | 타입: {event_type}")
        else:
            print("  (결과 없음)")
    except Exception as e:
        print(f"Semantic Gap 결과 조회 실패: {e}")
    print()

    # RPC Request-Response 통계
    print("RPC Request-Response 통계:")
    print("-" * 80)
    
    # initialize 응답에서 서버 정보 추출
    pid_to_server = {}
    async with db.conn.execute(
        """
        SELECT raw_req.pid, rpc_resp.result
        FROM rpc_events rpc_req
        JOIN raw_events raw_req ON rpc_req.raw_event_id = raw_req.id
        JOIN rpc_events rpc_resp
            ON rpc_req.message_id = rpc_resp.message_id
            AND rpc_resp.direction = 'Response'
        WHERE rpc_req.method = 'initialize'
          AND rpc_req.direction = 'Request'
          AND rpc_resp.result IS NOT NULL
        """
    ) as cursor:
        rows = await cursor.fetchall()
        for pid, result_str in rows:
            if result_str:
                try:
                    result = json.loads(result_str)
                    server_info = result.get('serverInfo', {})
                    server_name = server_info.get('name', 'Unknown')
                    if pid:
                        pid_to_server[pid] = server_name
                except json.JSONDecodeError:
                    pass

    # message_id → 서버 이름 매핑
    message_id_to_server = {}
    async with db.conn.execute(
        """
        WITH init_servers AS (
            SELECT 
                raw_req.pid,
                json_extract(rpc_resp.result, '$.serverInfo.name') AS server_name,
                rpc_req.message_id AS init_msg_id
            FROM rpc_events rpc_req
            JOIN raw_events raw_req ON rpc_req.raw_event_id = raw_req.id
            JOIN rpc_events rpc_resp
                ON rpc_req.message_id = rpc_resp.message_id
               AND rpc_resp.direction = 'Response'
            WHERE rpc_req.method = 'initialize'
              AND rpc_req.direction = 'Request'
              AND rpc_resp.result IS NOT NULL
        )
        SELECT 
            rpc_req.message_id,
            init_servers.server_name,
            init_servers.pid
        FROM rpc_events rpc_req
        JOIN raw_events raw_req ON rpc_req.raw_event_id = raw_req.id
        LEFT JOIN init_servers ON raw_req.pid = init_servers.pid
        WHERE rpc_req.method = 'tools/list'
          AND rpc_req.direction = 'Request'
        """
    ) as cursor:
        rows = await cursor.fetchall()
        for message_id, server_name, pid in rows:
            if server_name:
                message_id_to_server[message_id] = server_name

    # tools/list 응답 기반 동적 시그니처 학습
    tool_to_server_counts = defaultdict(Counter)
    async with db.conn.execute(
        """
        SELECT
            r_resp.result,
            COALESCE(raw_resp.mcpTag,
                     json_extract(r_resp.result, '$.serverInfo.name'),
                     'Unknown') AS server_name
        FROM rpc_events r_req
        JOIN rpc_events r_resp
             ON r_req.message_id = r_resp.message_id
            AND r_req.direction = 'Request'
            AND r_resp.direction = 'Response'
        LEFT JOIN raw_events raw_resp
             ON r_resp.raw_event_id = raw_resp.id
        WHERE r_req.method = 'tools/list'
          AND r_resp.result IS NOT NULL
        """
    ) as cursor:
        rows = await cursor.fetchall()
        for result_json_str, server_name in rows:
            try:
                r = json.loads(result_json_str) if result_json_str else {}
                tools = r.get("tools", []) or []
                for t in tools:
                    name = t.get("name")
                    if name:
                        tool_to_server_counts[name][server_name or "Unknown"] += 1
            except json.JSONDecodeError:
                continue

    # 동적 도구 기반 서버 식별 함수
    def identify_server_by_tools(tools: list) -> str:
        if not tools:
            return "Unknown"
        names = {t.get("name") for t in (tools or []) if isinstance(t, dict) and t.get("name")}
        if not names:
            return "Unknown"
        total = Counter()
        for n in names:
            total.update(tool_to_server_counts.get(n, {}))
        if not total:
            return "Unknown"
        best_server, _ = max(total.items(), key=lambda kv: (kv[1], kv[0] or ""))
        return best_server or "Unknown"

    # Request 통계 출력
    async with db.conn.execute(
        """
        SELECT method, COUNT(*) AS count
        FROM rpc_events
        WHERE direction = 'Request' AND method IS NOT NULL
        GROUP BY method
        ORDER BY count DESC
        LIMIT 10
        """
    ) as cursor:
        request_rows = await cursor.fetchall()

    if request_rows:
        for method, count in request_rows:
            print(f"\n📤 {method} ({count:,} requests)")
            async with db.conn.execute(
                """
                SELECT r_resp.result,
                       r_req.params,
                       raw_resp.producer,
                       raw_resp.event_type,
                       raw_resp.mcpTag
                FROM rpc_events r_req
                LEFT JOIN rpc_events r_resp
                    ON r_req.message_id = r_resp.message_id
                   AND r_resp.direction = 'Response'
                LEFT JOIN raw_events raw_resp
                    ON r_resp.raw_event_id = raw_resp.id
                WHERE r_req.method = ?
                  AND r_req.direction = 'Request'
                  AND r_resp.result IS NOT NULL
                GROUP BY LENGTH(r_resp.result)
                ORDER BY LENGTH(r_resp.result) DESC
                LIMIT 10
                """,
                (method,),
            ) as detail_cursor:
                details = await detail_cursor.fetchall()

                if not details:
                    print("  └─ No matching response found")
                    continue

                for idx, detail in enumerate(details):
                    result_json = json.loads(detail[0]) if detail[0] else None
                    params_json = json.loads(detail[1]) if detail[1] else {}
                    producer = detail[2]
                    event_type = detail[3]
                    mcp_tag = detail[4] or "Unknown"

                    if idx == 0 and params_json:
                        print("  └─ Params:")
                        print(json.dumps(params_json, ensure_ascii=False, indent=2))

                    if result_json:
                        prefix = "  └─" if idx == 0 else "  ├─"

                        # Remote MCP만 이름 치환
                        server_name = mcp_tag
                        if producer == "remote" and event_type == "MCP":
                            if mcp_tag in remote_server_map:
                                server_name = remote_server_map[mcp_tag]

                        if "tools" in result_json:
                            tools = result_json["tools"]
                            if tools:
                                print(f"{prefix} Response [{server_name}]: {len(tools)} tools")
                                for tool in tools[:5]:
                                    print(f"      • {tool.get('name', 'unknown')}")
                                if len(tools) > 5:
                                    print(f"      • ... and {len(tools) - 5} more")
                            else:
                                print(f"{prefix} Response [{server_name}]: No tools available")
                        elif "resources" in result_json:
                            resources = result_json["resources"]
                            if resources:
                                print(f"{prefix} Response [{server_name}]: {len(resources)} resources")
                                for resource in resources[:3]:
                                    print(f"      • {resource.get('name', 'unknown')}")
                            else:
                                print(f"{prefix} Response [{server_name}]: No resources available")
                        elif "prompts" in result_json:
                            prompts = result_json["prompts"]
                            if prompts:
                                print(f"{prefix} Response [{server_name}]: {len(prompts)} prompts")
                                for prompt in prompts[:3]:
                                    print(f"      • {prompt.get('name', 'unknown')}")
                            else:
                                print(f"{prefix} Response [{server_name}]: No prompts available")
                        elif "protocolVersion" in result_json:
                            server_info = result_json.get("serverInfo", {})
                            version = server_info.get("version", "")
                            print(f"{prefix} Response [{server_name}]: v{version}")
                        else:
                            print(f"{prefix} Response [{server_name}]: {list(result_json.keys())}")
    else:
        print("  (결과 없음)")
    print()

    # 파일 작업 통계
    print("파일 작업 통계:")
    print("-" * 80)
    async with db.conn.execute(
        """
        SELECT operation, COUNT(*) AS cnt
        FROM file_events
        GROUP BY operation
        ORDER BY cnt DESC
        """
    ) as cursor:
        rows = await cursor.fetchall()
        if rows:
            for op, count in rows:
                print(f"  {op:20s}: {count:,}")
        else:
            print("  (결과 없음)")
    print()

    # 엔진별 탐지 통계
    print("엔진별 탐지 통계:")
    print("-" * 80)
    async with db.conn.execute(
        """
        SELECT engine_name,
               COUNT(*) AS total,
               SUM(CASE WHEN detected = 1 THEN 1 ELSE 0 END) AS detected_count
        FROM engine_results
        GROUP BY engine_name
        """
    ) as cursor:
        rows = await cursor.fetchall()
        if rows:
            for row in rows:
                engine_name, total, detected = row
                detection_rate = (detected / total * 100) if total > 0 else 0
                print(f"  {engine_name:20s}: {detected:4d}/{total:4d} ({detection_rate:.1f}%)")
        else:
            print("  (결과 없음)")
    print()

    await db.close()

    print("=" * 80)
    print("조회 완료!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
