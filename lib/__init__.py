# lib package initializer
# Import the HTTP-disabling helper early so any import from `lib` will
# install the runtime guard that prevents outbound HTTP when
# DISABLE_EXTERNAL_HTTP=1 (default).
try:
    from . import disable_http  # noqa: F401
except Exception:
    pass
