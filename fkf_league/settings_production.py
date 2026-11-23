"""
Backwards-compatible production entrypoint.

``fkf_league.settings`` is now fully environment-driven and secure by default,
so this module only guarantees DEBUG is off. Prefer pointing
DJANGO_SETTINGS_MODULE at ``fkf_league.settings`` directly.
"""

import os

os.environ["DJANGO_DEBUG"] = "0"

from .settings import *  # noqa: E402,F401,F403
