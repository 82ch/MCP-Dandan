from engines.base_engine import BaseEngine
from typing import Any
from mistralai import Mistral
from mistralai.models import SDKError
from dotenv import load_dotenv
from time import strftime, localtime
import os
import time
import json


class ToolsPoisoningEngine(BaseEngine):
    """
    LLM(Mistral)을 사용하여 MCP tools/call의 요청과 응답을 분석하고,
    도구 스펙(tool specification)과 실제 사용 간의 의미론적 불일치를 탐지합니다.
    Tools Poisoning 공격 탐지 엔진
    """

    # 단일 정수 점수 버전
    SYSTEM_PROMPT_INT = """
You are a rigorous evaluator. Score the semantic alignment between:
(1) a tool specification in JSON-like form and
(2) a data description.

Scoring dimensions (weights):
- DomainMatch (0–40): high-level domain overlap (e.g., filesystem vs network)
- OperationMatch (0–35): verbs/nouns of the tool's intended operations vs the data's required actions
- ArgumentSpecificity (0–15): arguments/fields in (2) concretely match what (1) expects
- Consistency (0–10): directionality and preconditions coherent (no contradictions/missing essentials)

Anchors for the final score (1–100):
- 1–10: different domains, little to no overlap
- 30–40: weak topical overlap only
- 60–65: partially related (shared topic but not direct operation/args)
- 80–90: strong functional alignment (tool purpose clearly fits the data)
- 95–100: near-perfect match (direct verb/noun + argument alignment)

Hard caps/floors and penalties:
- If tool domain ≠ data domain → cap the final score at 35.
- If verbs/nouns directly match (e.g., "findFileSystem" → "search_file/directory") → floor the raw sum at 85 before penalties.
- Penalties: subtract 10 each for hallucinated mappings, undefined arguments, or invented capabilities.
- Clip the final score to [1,100].

Output constraint:
Return ONLY the final integer (1–100). Do not include any words, symbols, JSON, or explanations.
"""

    # 세부 JSON 결과 버전
    SYSTEM_PROMPT_DETAIL = """
[ROLE: system]
You are a rigorous evaluator. Score the semantic alignment between:
(1) a tool specification in JSON-like form and
(2) a data description,
returning a research-grade rubric with sub-scores and a final 0–100 integer.

Scoring dimensions (with weights):
- DomainMatch (0–40): Are the high-level domains the same? (e.g., filesystem vs network)
- OperationMatch (0–35): Do verbs/nouns of the tool's intended operations align with the data's required actions?
- ArgumentSpecificity (0–15): Do arguments/fields in (2) concretely match what (1) expects?
- Consistency (0–10): Are directionality and preconditions coherent (no contradictions, no missing essentials)?

Anchors (interpretation of the final score):
- 0–10: Different domains, little to no overlap.
- 30–40: Weak topical overlap only.
- 60–65: Partially related (shared topic but not direct operation/args).
- 80–90: Strong functional alignment (tool purpose clearly fits the data).
- 95–100: Near-perfect match (direct verb/noun + argument alignment).

Hard caps/floors and penalties:
- If tool domain ≠ data domain → cap final score at 35.
- If verbs/nouns directly match (e.g., "findFileSystem" → "search_file/directory") → floor the raw sum at 85 before penalties.
- Penalize (-10 each) for hallucinated mappings, undefined arguments, or invented capabilities.
- Clip the final score to [0,100].

Output format (JSON only, no extra text):
{
  "DomainMatch": <0-40>,
  "OperationMatch": <0-35>,
  "ArgumentSpecificity": <0-15>,
  "Consistency": <0-10>,
  "Penalties": [ "<short reason>", ... ],
  "Score": <0-100 integer>
}
"""

    def __init__(self, db, detail_mode: bool = False):
        """
        Args:
            db: Database 인스턴스
            detail_mode: True면 JSON 기반 세부 점수, False면 단일 점수 모드
        """
        super().__init__(
            db=db,
            name='ToolsPoisoningEngine',
            event_types=['RPC', 'JsonRPC', 'MCP']  # MCP RPC 이벤트 수신
        )

        # Mistral API 설정
        load_dotenv()
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            print("[ToolsPoisoningEngine] WARNING: MISTRAL_API_KEY not found in .env file")

        self.client = Mistral(api_key=api_key)
        self.detail_mode = detail_mode
        self.system_prompt = (
            self.SYSTEM_PROMPT_DETAIL if detail_mode else self.SYSTEM_PROMPT_INT
        )
        self.retry_count = 2

        # tools/call Request/Response 페어링용
        self.pending_requests = {}  # {(mcpTag, message_id): request_event}

    def should_process(self, data: dict) -> bool:
        """
        tools/call 관련 MCP RPC 이벤트만 처리
        """
        event_type = data.get('eventType', '').lower()
        if event_type not in ['rpc', 'jsonrpc', 'mcp']:
            return False

        # tools/call method인지 확인
        message = data.get('data', {}).get('message', {})
        method = message.get('method', '')
        task = data.get('data', {}).get('task', '')

        # tools/call의 Request 또는 Response
        return method == 'tools/call' or (task == 'RECV' and 'result' in message)

    async def process(self, data: Any) -> Any:
        """
        tools/call Request/Response를 페어링하여 LLM 분석 수행
        """
        # 페어링 처리
        paired_event = self._handle_pairing(data)

        # Request만 들어온 경우 (Response 대기 중)
        if paired_event is None:
            return None

        # print(f"[ToolsPoisoningEngine] 페어 분석 시작: mcpTag={paired_event.get('mcpTag')}, msg_id={paired_event.get('message_id')}")

        # Request와 Response 추출
        request_event = paired_event.get('request', {})
        response_event = paired_event.get('response', {})

        # Request에서 tool_name 추출
        req_message = request_event.get('data', {}).get('message', {})
        params = req_message.get('params', {})
        tool_name = params.get('name', 'Unknown')

        # print(f"[ToolsPoisoningEngine] → Tool: {tool_name}")

        # mcpl 테이블에서 tool spec 조회
        tool_spec = await self._get_tool_spec_from_mcpl(tool_name)

        # if tool_spec:
        #     print(f"[ToolsPoisoningEngine] → Tool Spec 조회 성공: {tool_spec.get('tool_description', 'N/A')[:80]}...")
        # else:
        #     print(f"[ToolsPoisoningEngine] error-Tool Spec 없음 (mcpl 테이블에서 {tool_name} 미발견)")

        # 이벤트 데이터를 LLM 입력용 문자열로 변환
        event_description = self._format_paired_event_for_llm(request_event, response_event, tool_spec)

        # print(f"[ToolsPoisoningEngine] → LLM 분석 시작 (Mistral API 호출)...")

        # LLM 평가 수행
        result = self._evaluate_with_mistral(event_description)

        if result is None:
            print("[ToolsPoisoningEngine] ERROR:LLM Analysis Failed.")
            return None

        # reference 생성
        references = []
        if 'ts' in paired_event:
            references.append(f"id-{paired_event['ts']}")

        output = {
            'detected': True,
            'reference': references,
            'result': {
                'detector': 'ToolsPoisoning',
                'evaluation': result,
                'event_type': 'MCP_ToolCall_Pair',
                'detail_mode': self.detail_mode,
                'original_event': paired_event,
                'tool_spec': tool_spec
            }
        }

        # 결과 타입에 따라 출력
        # if isinstance(result, dict):
        #     score = result.get('Score', 'N/A')
        #     print(f"[ToolsPoisoningEngine] Success-평가 완료: Score={score}")
        #     print(f"                       → DomainMatch={result.get('DomainMatch')}, "
        #           f"OperationMatch={result.get('OperationMatch')}, "
        #           f"ArgumentSpecificity={result.get('ArgumentSpecificity')}")
        # else:
        #     print(f"[ToolsPoisoningEngine] Success-평가 완료: Score={result}")

        return output

    def _handle_pairing(self, event: dict) -> dict:
        """
        tools/call Request와 Response를 페어링

        Returns:
            페어링된 이벤트 또는 None (Request만 들어온 경우)
        """
        try:
            data = event.get('data', {})
            message = data.get('message', {})
            method = message.get('method', '')
            task = data.get('task', '')
            message_id = message.get('id')
            mcp_tag = data.get('mcpTag') or event.get('mcpTag', 'unknown')

            if not message_id:
                return None

            # tools/call Request 처리
            if method == 'tools/call' and task == 'SEND':
                key = (mcp_tag, str(message_id))
                self.pending_requests[key] = event
                # print(f'[ToolsPoisoningEngine Debugging] Request 저장: mcpTag={mcp_tag}, msg_id={message_id}')
                return None  # Response 대기

            # tools/call Response 처리
            elif task == 'RECV' and 'result' in message:
                key = (mcp_tag, str(message_id))
                request_event = self.pending_requests.pop(key, None)

                if request_event:
                    # 페어 생성
                    paired_event = {
                        'eventType': 'MCP_ToolCall_Pair',
                        'ts': event.get('ts'),
                        'request': request_event,
                        'response': event,
                        'mcpTag': mcp_tag,
                        'message_id': message_id
                    }
                    # print(f'[ToolsPoisoningEngine Debuging] Success-페어 생성: mcpTag={mcp_tag}, msg_id={message_id}')
                    return paired_event
                else:
                    # print(f'[ToolsPoisoningEngine Debuging] Error-Request 없음: mcpTag={mcp_tag}, msg_id={message_id}')
                    return None

        except Exception as e:
            # print(f'[ToolsPoisoningEngine Debuging] Error-페어링 오류: {e}')
            return None

        return None

    async def _get_tool_spec_from_mcpl(self, tool_name: str) -> dict:
        """
        mcpl 테이블에서 tool spec 조회

        Args:
            tool_name: 조회할 툴 이름

        Returns:
            tool spec 딕셔너리 (없으면 빈 dict)
        """
        try:
            async with self.db.conn.execute(
                """
                SELECT mcpTag, producer, tool, tool_title, tool_description,
                       tool_parameter, annotations
                FROM mcpl
                WHERE tool = ?
                LIMIT 1
                """,
                (tool_name,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        'mcpTag': row[0],
                        'producer': row[1],
                        'tool': row[2],
                        'tool_title': row[3],
                        'tool_description': row[4],
                        'tool_parameter': row[5],
                        'annotations': row[6]
                    }
        except Exception as e:
            print(f"[ToolsPoisoningEngine] mcpl 조회 오류: {e}")

        return {}

    def _format_paired_event_for_llm(self, request: dict, response: dict, tool_spec: dict = None) -> str:
        """
        tools/call Request + Response 페어 + Tool Spec을 LLM 입력용 포맷으로 변환
        """
        req_data = request.get('data', {})
        req_message = req_data.get('message', {})

        resp_data = response.get('data', {})
        resp_message = resp_data.get('message', {})

        # Request에서 params 추출
        params = req_message.get('params', {})
        tool_name = params.get('name', 'Unknown')
        tool_args = params.get('arguments', {})

        # Response에서 result 추출
        result = resp_message.get('result', {})

        # Tool Spec 섹션 생성
        tool_spec_section = ""
        if tool_spec:
            tool_spec_section = f"""
[Tool Specification from MCPL]
Tool Name: {tool_spec.get('tool', 'N/A')}
Title: {tool_spec.get('tool_title', 'N/A')}
Description: {tool_spec.get('tool_description', 'N/A')}
Parameters Schema: {tool_spec.get('tool_parameter', 'N/A')}
Producer: {tool_spec.get('producer', 'N/A')}
MCP Tag: {tool_spec.get('mcpTag', 'N/A')}
"""
        else:
            tool_spec_section = "\n[Tool Specification from MCPL]\nNot found in database\n"

        formatted = f"""
=== MCP tools/call Request-Response Pair Analysis ===
{tool_spec_section}
[Actual Request]
Tool Name: {tool_name}
Arguments: {json.dumps(tool_args, indent=2, ensure_ascii=False)}

[Actual Response]
Result: {json.dumps(result, indent=2, ensure_ascii=False)}

[Full Request Data]
{json.dumps(request, indent=2, ensure_ascii=False)}

[Full Response Data]
{json.dumps(response, indent=2, ensure_ascii=False)}
"""
        return formatted

    def _format_event_for_llm(self, data: dict) -> str:
        """
        이벤트 데이터를 LLM이 읽을 수 있는 자연어 포맷으로 변환합니다.
        """
        event_type = data.get('eventType', 'Unknown')

        if event_type == 'File':
            file_path = data.get('filePath', data.get('data', {}).get('filePath', 'Unknown'))
            return f"Event Type: {event_type}\nFile Path: {file_path}\nData: {data}"
        elif event_type == 'Process':
            process_name = data.get('processName', data.get('data', {}).get('processName', 'Unknown'))
            return f"Event Type: {event_type}\nProcess: {process_name}\nData: {data}"
        elif event_type == 'Network':
            destination = data.get('destination', data.get('data', {}).get('destination', 'Unknown'))
            return f"Event Type: {event_type}\nDestination: {destination}\nData: {data}"
        else:
            return f"Event Type: {event_type}\nData: {data}"

    def _evaluate_with_mistral(self, desc: str) -> Any:
        """
        Mistral API를 이용해 의미론적 유사도 평가 수행
        """
        user_prompt = f"""
Based on the given Content, evaluate the correlation between
(1) the JSON and (2) the data,
and return a score between 0 and 100.

Content: {desc}
"""

        for attempt in range(1, self.retry_count + 1):
            try:
                response = self.client.chat.complete(
                    model="mistral-medium",
                    messages=[
                        {"role": "system", "content": self.system_prompt.strip()},
                        {"role": "user", "content": user_prompt.strip()}
                    ],
                    n=1
                )

                result = response.choices[0].message.content.strip()
                current_time = strftime("%H:%M:%S", localtime())
                tag = " (Retry)" if attempt > 1 else ""

                # Return point
                print(f"[ToolsPoisoningEngine] Model : {response.model} Time : {current_time} Result(point) : {result}{tag}")

                if self.detail_mode:
                    try:
                        return json.loads(result)
                    except Exception:
                        return result
                else:
                    try:
                        return int(result)
                    except Exception:
                        return result

            except SDKError as e:
                print(f"[ToolsPoisoningEngine] ERROR - Attempt {attempt}/{self.retry_count} – {e}")
                if attempt < self.retry_count:
                    time.sleep(1)

        print("[ToolsPoisoningEngine] FAIL - All retry attempts failed.")
        return None
