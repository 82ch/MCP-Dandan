from engine.base_engine import BaseEngine
from queue import Queue
from typing import Any
from mistralai import Mistral
from mistralai.models import SDKError
from dotenv import load_dotenv
from time import strftime, localtime
import os
import time


class SemanticGapEngine(BaseEngine):
    """
    LLM(Mistral)을 사용하여 이벤트 데이터의 의미론적 분석하여,
    도구 스펙과 데이터 간의 semantic alignment를 평가
    """

    # int Result
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

    # Detail(JSON Result)
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

    def __init__(self, input_queue: Queue, log_queue: Queue, detail_mode: bool = False):

        super().__init__(
            input_queue=input_queue,
            log_queue=log_queue,
            name='SemanticGapEngine',
            event_types=None  # 모든 이벤트 처리
        )

        # Mistral API 설정
        load_dotenv()
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            print("[SemanticGapEngine] WARNING: MISTRAL_API_KEY not found in .env file")
        self.client = Mistral(api_key=api_key)

        # 모드 설정
        self.detail_mode = detail_mode
        self.system_prompt = self.SYSTEM_PROMPT_DETAIL if detail_mode else self.SYSTEM_PROMPT_INT
        self.retry_count = 2

    def process(self, data: Any) -> Any:
        print(f"[SemanticGapEngine] 입력 데이터: {data}")

        # 이벤트 데이터를 문자열로 변환
        event_description = self._format_event_for_llm(data)

        # LLM 평가 수행
        result = self._evaluate_with_mistral(event_description)

        if result is None:
            print(f"[SemanticGapEngine] Analysis failed for event.")
            return None

        # reference 생성
        references = []
        if 'ts' in data:
            references.append(f"id-{data['ts']}")

        output = {
            'detected': True,
            'reference': references,
            'result': {
                'detector': 'SemanticGap',
                'evaluation': result,
                'event_type': data.get('eventType', 'Unknown'),
                'detail_mode': self.detail_mode,
                'original_event': data
            }
        }

        print(f"[SemanticGapEngine] 평가 완료: {result}")
        return output

    def _format_event_for_llm(self, data: dict) -> str:
     
        event_type = data.get('eventType', 'Unknown')

        # 이벤트 타입별로 중요한 정보 추출
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
            # 기본 포맷
            return f"Event Type: {event_type}\nData: {data}"

    def _evaluate_with_mistral(self, desc: str) -> Any:

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

                print(f"[SemanticGapEngine] {response.model} {current_time} {result}{tag}")

                # detail_mode이면 JSON 파싱 시도
                if self.detail_mode:
                    try:
                        import json
                        return json.loads(result)
                    except:
                        # JSON 파싱 실패시 문자열 그대로 반환
                        return result
                else:
                    # int 모드면 숫자만 반환
                    try:
                        return int(result)
                    except:
                        # 숫자 변환 실패시 문자열 그대로 반환
                        return result

            except SDKError as e:
                print(f"[SemanticGapEngine] ERROR - Attempt {attempt}/{self.retry_count} – {e}")
                if attempt < self.retry_count:
                    time.sleep(1)

        print(f"[SemanticGapEngine] FAIL - All retry attempts failed.")
        return None
