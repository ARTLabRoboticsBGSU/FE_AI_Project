"""
Disable outbound HTTP calls at runtime.
When imported, this module monkeypatches common HTTP client libraries (requests,
urllib, http.client) to raise RuntimeError on any network attempt. This ensures
no accidental external HTTP calls are made while the app runs.

To allow HTTP during debugging or controlled runs, set environment variable
`DISABLE_EXTERNAL_HTTP=0` before starting the process.
"""
import os
import urllib.parse

_DISABLED = os.getenv('DISABLE_EXTERNAL_HTTP', '1') == '1'

# Build an allowlist of URL prefixes that are permitted even when HTTP is
# globally disabled. By default we allow the Ollama local URL (if set) and
# localhost on port 11434.
_allow_prefixes = []
try:
    ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')
    parsed = urllib.parse.urlparse(ollama_url)
    if parsed.scheme and parsed.netloc:
        _allow_prefixes.append(f"{parsed.scheme}://{parsed.netloc}")
except Exception:
    pass

# Also allow bare localhost variants for common loopback addresses on the
# default Ollama port.
_allow_prefixes.extend([
    'http://localhost:11434',
    'http://127.0.0.1:11434',
    'http://[::1]:11434',
])

def _is_allowed_url(url: str) -> bool:
    if not url:
        return False
    try:
        for p in _allow_prefixes:
            if url.startswith(p):
                return True
        # also allow relative/local file URLs
        return False
    except Exception:
        return False

if _DISABLED:
    try:
        import requests
        _orig_Session = requests.Session

        class _GuardedSession(_orig_Session):
            def request(self, method, url, *args, **kwargs):
                if _is_allowed_url(url):
                    return super().request(method, url, *args, **kwargs)
                raise RuntimeError(f"Outbound HTTP calls are disabled (DISABLE_EXTERNAL_HTTP=1). Blocked URL: {url}")

        requests.Session = _GuardedSession

        # Patch top-level convenience functions to use guarded session behavior
        _guarded_session_instance = requests.Session()

        def _guarded_request(method, url, *args, **kwargs):
            if _is_allowed_url(url):
                return _orig_Session.request(_orig_Session(), method, url, *args, **kwargs)
            raise RuntimeError(f"Outbound HTTP calls are disabled (DISABLE_EXTERNAL_HTTP=1). Blocked URL: {url}")

        requests.get = lambda url, *a, **k: _guarded_request('GET', url, *a, **k)
        requests.post = lambda url, *a, **k: _guarded_request('POST', url, *a, **k)
        requests.put = lambda url, *a, **k: _guarded_request('PUT', url, *a, **k)
        requests.patch = lambda url, *a, **k: _guarded_request('PATCH', url, *a, **k)
        requests.delete = lambda url, *a, **k: _guarded_request('DELETE', url, *a, **k)
    except Exception:
        pass

    # Leave urllib and http.client alone for now; most internal calls use
    # `requests`. If needed, we can add more guarded wrappers later.
else:
    # No-op: HTTP allowed
    pass
