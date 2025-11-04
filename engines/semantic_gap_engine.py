from engines.base_engine import BaseEngine
from typing import Any
from mistralai import Mistral
from mistralai.models import SDKError
from dotenv import load_dotenv
from time import strftime, localtime
import os
import time
import json


class SemanticGapEngine(BaseEngine):
    """
    LLM(Mistral)을 사용하여 이벤트 데이터의 의미론적 분석을 수행하고,
    도구 스펙과 이벤트 데이터 간의 semantic alignment를 평가합니다.
    Refactored - No Queue (logger 기반)
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
            name='SemanticGapEngine',
            event_types=None  # 모든 이벤트 처리
        )

        # Mistral API 설정
        load_dotenv()
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            print("[SemanticGapEngine] WARNING: MISTRAL_API_KEY not found in .env file")

        self.client = Mistral(api_key=api_key)
        self.detail_mode = detail_mode
        self.system_prompt = (
            self.SYSTEM_PROMPT_DETAIL if detail_mode else self.SYSTEM_PROMPT_INT
        )
        self.retry_count = 2

    def process(self, data: Any) -> Any:
        """
        LLM을 사용하여 의미론적 유사도 평가를 수행합니다.
        """
        print(f"[SemanticGapEngine] 입력 데이터: {data}")

        # 이벤트 데이터를 LLM 입력용 문자열로 변환
        event_description = self._format_event_for_llm(data)

        # LLM 평가 수행
        result = self._evaluate_with_mistral(event_description)

        if result is None:
            print("[SemanticGapEngine] Analysis failed for event.")
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

                print(f"[SemanticGapEngine] {response.model} {current_time} {result}{tag}")

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
                print(f"[SemanticGapEngine] ERROR - Attempt {attempt}/{self.retry_count} – {e}")
                if attempt < self.retry_count:
                    time.sleep(1)

        print("[SemanticGapEngine] FAIL - All retry attempts failed.")
        return None
