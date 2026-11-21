"""Test matching frontend EVENT_TYPES against backend SecurityEventType (Spec 10.12)."""

import re
from pathlib import Path
from app.domain.entities.security_event import SecurityEventType


def test_frontend_event_types_match_backend():
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    frontend_events_page = repo_root / "frontend" / "src" / "pages" / "SecurityEventsPage.tsx"

    assert frontend_events_page.is_file(), f"File not found: {frontend_events_page}"
    content = frontend_events_page.read_text(encoding="utf-8")

    # Extract EVENT_TYPES = [ ... ]
    match = re.search(r"const EVENT_TYPES = \[\s*([\s\S]*?)\s*\];", content)
    assert match, "EVENT_TYPES array not found in SecurityEventsPage.tsx"

    raw_items = match.group(1)
    frontend_event_types = set(re.findall(r'"([^"]+)"', raw_items))

    backend_event_types = {e.value for e in SecurityEventType}

    # Ensure all backend event types are present in frontend EVENT_TYPES
    missing_in_frontend = backend_event_types - frontend_event_types
    assert not missing_in_frontend, f"Backend SecurityEventTypes missing in frontend: {missing_in_frontend}"
