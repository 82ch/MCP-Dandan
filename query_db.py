"""
데이터베이스 조회 스크립트
사용법: python query_db.py
"""

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

    # 1. 통계 조회
    print("📊 전체 통계:")
    print("-" * 80)
    stats = await db.get_event_statistics()
    print(f"총 이벤트 수: {stats.get('total_events', 0):,}")
    print(f"탐지된 이벤트 수: {stats.get('detected_events', 0):,}")
    print()

    print("이벤트 타입별 통계:")
    by_type = stats.get('by_type', {})
    for event_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
        print(f"  {event_type:20s}: {count:,}")
    print()

    # 2. 최근 이벤트 조회
    print("📝 최근 이벤트 (10개):")
    print("-" * 80)
    recent = await db.get_recent_events(limit=10)
    for event in recent:
        ts = event['ts']
        try:
            unix_timestamp = (ts / 10000000) - 62135596800
            dt = datetime.fromtimestamp(unix_timestamp)
            time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
        except (OSError, ValueError):
            time_str = f"ts={ts}"

        print(f"[{event['id']:4d}] {time_str} | "
              f"{event['event_type']:15s} | {event['producer']:8s} | {event.get('mcpTag', '-')}")
    print()

    # 3. Semantic Gap 고득점 결과
    print("🎯 Semantic Gap 고득점 결과:")
    print("-" * 80)
    high_scores = await db.get_high_semantic_gap_results(threshold=70, limit=10)
    if high_scores:
        for result in high_scores:
            score = result.get('final_score', 0)
            event_type = result.get('event_type', 'Unknown')
            print(f"점수: {score:3d} | 타입: {event_type}")
    else:
        print("  (결과 없음)")
    print()

    # 4. RPC Request-Response 통계
    print("🔌 RPC Request-Response 통계:")
    print("-" * 80)

    # Step 1. initialize 응답에서 서버 정보 추출 (PID 기반 매핑)
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

    # Step 2. message_id → 서버 이름 매핑 (initialize 기반)
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

    # Step 2.5. tools/list 응답 기반 동적 시그니처 학습
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

    # Step 3. 동적 도구 기반 서버 식별 함수
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

    # Step 4. Request 통계 출력
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
                SELECT 
                    r_resp.result, 
                    r_req.params, 
                    raw_resp.pid,
                    raw_resp.mcpTag,
                    r_req.message_id
                FROM rpc_events r_req
                LEFT JOIN raw_events raw_req
                    ON r_req.raw_event_id = raw_req.id
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
                (method,)
            ) as detail_cursor:
                details = await detail_cursor.fetchall()

                if details:
                    for idx, detail in enumerate(details):
                        result_json = json.loads(detail[0]) if detail[0] else None
                        params_json = json.loads(detail[1]) if detail[1] else {}
                        pid = detail[2]
                        mcp_tag = detail[3] or "Unknown"
                        message_id = detail[4]

                        if idx == 0 and params_json:
                            params_str = json.dumps(params_json, ensure_ascii=False, indent=2)
                            print(f"  └─ Params:\n{params_str}")

                        if result_json:
                            prefix = "  └─" if idx == 0 else "  ├─"
                            server_name = "Unknown"

                            if mcp_tag and mcp_tag != "Unknown":
                                server_name = mcp_tag
                            elif message_id in message_id_to_server:
                                server_name = message_id_to_server[message_id]
                            elif pid in pid_to_server:
                                server_name = pid_to_server[pid]
                            elif 'serverInfo' in result_json:
                                server_name = result_json['serverInfo'].get('name', 'Unknown')
                            elif 'tools' in result_json:
                                server_name = identify_server_by_tools(result_json['tools'])

                            if 'tools' in result_json:
                                tools = result_json['tools']
                                if tools:
                                    print(f"{prefix} Response [{server_name}]: {len(tools)} tools")
                                    for tool in tools[:5]:
                                        print(f"      • {tool.get('name', 'unknown')}")
                                    if len(tools) > 5:
                                        print(f"      • ... and {len(tools) - 5} more")
                                else:
                                    print(f"{prefix} Response [{server_name}]: No tools available")
                            elif 'resources' in result_json:
                                resources = result_json['resources']
                                if resources:
                                    print(f"{prefix} Response [{server_name}]: {len(resources)} resources")
                                    for resource in resources[:3]:
                                        print(f"      • {resource.get('name', 'unknown')}")
                                else:
                                    print(f"{prefix} Response [{server_name}]: No resources available")
                            elif 'prompts' in result_json:
                                prompts = result_json['prompts']
                                if prompts:
                                    print(f"{prefix} Response [{server_name}]: {len(prompts)} prompts")
                                    for prompt in prompts[:3]:
                                        print(f"      • {prompt.get('name', 'unknown')}")
                                else:
                                    print(f"{prefix} Response [{server_name}]: No prompts available")
                            elif method == "tools/call":
                                # tools/call 요청은 호출된 MCP 서버와 툴 이름만 요약 출력
                                params = params_json or {}
                                tool_name = params.get("name", "unknown_tool")
                                args = params.get("arguments", {})
                                arg_summary = ", ".join(f"{k}={v}" for k, v in args.items())
                                print(f"{prefix} Called [{server_name}]: {tool_name}({arg_summary})")
                            elif 'protocolVersion' in result_json:
                                server_info = result_json.get('serverInfo', {})
                                print(f"{prefix} Response [{server_name}]: v{server_info.get('version', '')}")
                            else:
                                print(f"{prefix} Response [{server_name}]: {list(result_json.keys())}")
                else:
                    print(f"  └─ No matching response found")
    else:
        print("  (결과 없음)")
    print()

    # 5. 파일 이벤트 조회
    print("📁 파일 작업 통계:")
    print("-" * 80)
    async with db.conn.execute(
        """
        SELECT operation, COUNT(*) AS count
        FROM file_events
        GROUP BY operation
        ORDER BY count DESC
        """
    ) as cursor:
        rows = await cursor.fetchall()
        if rows:
            for row in rows:
                operation, count = row
                print(f"  {operation:20s}: {count:,}")
        else:
            print("  (결과 없음)")
    print()

    # 6. 엔진별 탐지 통계
    print("🔍 엔진별 탐지 통계:")
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
