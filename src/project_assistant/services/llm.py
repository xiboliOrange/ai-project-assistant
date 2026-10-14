import json
import os
from urllib import request
from urllib.parse import urlparse


class LlmError(Exception):
    pass


def generate_metadata(body: str):
    url = os.getenv("AI_PROJECT_LLM_URL", "")
    model = os.getenv("AI_PROJECT_LLM_MODEL", "")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not model:
        raise LlmError("The LLM service is not configured.")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Summarize the document. Return only a JSON object with a string 'summary' and an array of strings 'keywords'."},
            {"role": "user", "content": body},
        ],
        "temperature": 0,
    }
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("AI_PROJECT_LLM_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    http_request = request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with request.urlopen(http_request, timeout=60) as response:
            raw_response = response.read(1024 * 1024 + 1)
        if len(raw_response) > 1024 * 1024:
            raise ValueError("LLM response too large")
        response_data = json.loads(raw_response)
        content = response_data["choices"][0]["message"]["content"]
        metadata = json.loads(content)
        summary = metadata["summary"]
        keywords = metadata["keywords"]
        if not isinstance(summary, str) or not isinstance(keywords, list) or not all(
            isinstance(keyword, str) for keyword in keywords
        ):
            raise ValueError("Invalid metadata")
        return summary, keywords
    except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
        raise LlmError("The LLM service could not generate metadata.") from error
