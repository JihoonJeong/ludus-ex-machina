"""Ollama local API adapter for LxM."""

import json
import urllib.request
import urllib.error

from lxm.adapters.base import AgentAdapter


class OllamaAdapter(AgentAdapter):
    """Adapter for calling Ollama local models via HTTP API.

    Requires: Ollama running locally or remotely.
    API: POST http://{endpoint}/api/generate
    """

    def __init__(self, agent_config: dict):
        super().__init__(agent_config)
        self._model = agent_config.get("model", "llama3.1:8b")
        connection = agent_config.get("connection", {})
        self._endpoint = connection.get("endpoint", "http://localhost:11434")

    def invoke(self, match_dir: str, prompt: str) -> dict:
        url = f"{self._endpoint}/api/generate"
        payload = json.dumps({
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 2048,
            },
        }).encode()

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read())
                text = data.get("response", "")
                return {
                    "stdout": text,
                    "stderr": "",
                    "exit_code": 0,
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
