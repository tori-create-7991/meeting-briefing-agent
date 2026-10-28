"""BriefingWriter alone, for `adk eval`.

The eval cases put `briefing_contexts` straight into session state, so the
Workspace fetch step is skipped and no Calendar or Docs access is needed.
"""

import os

from meeting_briefing_agent.agent import DEFAULT_LANGUAGE, DEFAULT_MODEL, build_writer

root_agent = build_writer(
    language=os.getenv("BRIEFING_LANGUAGE", DEFAULT_LANGUAGE),
    model=os.getenv("BRIEFING_MODEL", DEFAULT_MODEL),
)
