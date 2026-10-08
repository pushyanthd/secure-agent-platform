"""Private HTTP child: parent bounds total wall time and pipes, including slow streams."""

import http.client
import json
import sys
from urllib.parse import urlsplit

from agentguard.model import ModelConfig

MAX_BODY = 65536
PATHS = {"/props", "/apply-template", "/tokenize", "/v1/chat/completions"}


def main() -> None:
    try:
        request = json.loads(sys.stdin.buffer.read(131073))
        config = ModelConfig(endpoint=request["endpoint"])
        path = request["path"]
        if path not in PATHS:
            raise ValueError
        endpoint = urlsplit(config.endpoint)
        assert endpoint.hostname is not None
        connection = http.client.HTTPConnection(endpoint.hostname, endpoint.port, timeout=300)
        try:
            # http.client neither follows redirects nor uses environment proxy settings.
            body = request["body"]
            connection.request(
                "GET" if body is None else "POST",
                path,
                body=None if body is None else json.dumps(body).encode(),
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            if response.status != 200:
                error = "MODEL_UNAVAILABLE" if response.status >= 500 else "MODEL_HTTP_REJECTED"
                print(json.dumps({"error": error}))
                return
            raw = response.read(MAX_BODY + 1)
            if len(raw) > MAX_BODY:
                print(json.dumps({"error": "MODEL_RESPONSE_TOO_LARGE"}))
                return
            print(json.dumps({"body": raw.decode("utf-8")}))
        finally:
            connection.close()
    except (OSError, http.client.HTTPException):
        print(json.dumps({"error": "MODEL_UNAVAILABLE"}))
    except (ValueError, KeyError, TypeError):
        print(json.dumps({"error": "INVALID_MODEL_RESPONSE"}))


if __name__ == "__main__":
    main()
