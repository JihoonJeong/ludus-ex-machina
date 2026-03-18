"""Ollama adapter for LxM — supports local and cloud (ollama.com) API."""

import json
import os
import urllib.request
import urllib.error

from lxm.adapters.base import AgentAdapter


class OllamaAdapter(AgentAdapter):
    """Adapter for calling Ollama models via HTTP API.

    Works with both local Ollama and Ollama Cloud (ollama.com).

    Local:
        endpoint: http://localhost:11434 (default)
        auth: none

    Cloud:
        endpoint: https://ollama.com
        auth: Bearer token (OLLAMA_API_KEY env var or connection.api_key)

    Usage:
        # Local
        --adapter ollama --model gemma3:4b

        # Cloud (set OLLAMA_API_KEY env var)
        --adapter ollama --model llama4:scout
        (with connection.endpoint = "https://ollama.com" in agent config)
    """

    def __init__(self, agent_config: dict):
        super().__init__(agent_config)
        self._model = agent_config.get("model", "llama3.1:8b")
        connection = agent_config.get("connection", {})
        self._endpoint = (
            connection.get("endpoint")
            or os.environ.get("OLLAMA_HOST")
            or "http://localhost:11434"
        )
        self._api_key = connection.get("api_key") or os.environ.get("OLLAMA_API_KEY")

    def invoke(self, match_dir: str, prompt: str) -> dict:
        url = f"{self._endpoint}/api/generate"
        payload = json.dumps({
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 4096,
            },
        }).encode()

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        req = urllib.request.Request(url, data=payload, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read())
                # Some models (qwen3) put output in "thinking" field instead of "response"
                text = data.get("response", "")
                if not text.strip() and data.get("thinking"):
                    text = data["thinking"]
                return {
                    "stdout": text,
                    "stderr": "",
                    "exit_code": 0,
                    "timed_out": False,
                }
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode()[:500]
            except Exception:
                pass
            return {
                "stdout": "",
                "stderr": f"Ollama HTTP {e.code}: {e.reason}. {body}",
                "exit_code": -1,
                "timed_out": False,
            }
        except urllib.error.URLError as e:
            return {
                "stdout": "",
                "stderr": f"Ollama connection error: {e}",
                "exit_code": -1,
                "timed_out": False,
            }
        except TimeoutError:
            return {
                "stdout": "",
                "stderr": "Ollama request timed out",
                "exit_code": -1,
                "timed_out": True,
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Ollama error: {e}",
                "exit_code": -1,
                "timed_out": False,
            }
