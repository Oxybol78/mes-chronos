"""
Fonction serverless Vercel — Proxy Notion
Accessible sur : https://votre-app.vercel.app/api/notion
"""

from http.server import BaseHTTPRequestHandler
import urllib.request
import json
import os
from datetime import date, datetime

NOTION_DB_ID  = "5d07a861-e0a1-4362-8a10-d4ce61acad0c"
CHRISTOPHE_ID = "345ad871-6b2c-4534-b79a-889b6dabec3d"


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        token = os.environ.get("NOTION_TOKEN", "")

        if not token:
            self._json({"error": "NOTION_TOKEN non configuré dans Vercel", "events": []})
            return

        try:
            events = _fetch_events(token)
            self._json({
                "events":      events,
                "last_update": datetime.now().strftime("%H:%M:%S"),
                "error":       None,
            })
        except Exception as e:
            self._json({"error": str(e), "events": []})

    def _json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type",                "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # silence les logs dans Vercel


# ─── Notion API ───────────────────────────────────────────────────────────────

def _fetch_events(token):
    today = date.today().isoformat()
    url   = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query"

    query_body = {
        "filter": {
            "and": [
                {"property": "Chronométreur", "people":   {"contains": CHRISTOPHE_ID}},
                {"property": "Date",          "date":     {"on_or_after": today}},
                {"property": "Statut",        "select":   {"does_not_equal": "Annulé"}},
                {"property": "Statut",        "select":   {"does_not_equal": "Perdu"}},
            ]
        },
        "sorts": [{"property": "Date", "direction": "ascending"}]
    }

    events       = []
    has_more     = True
    start_cursor = None

    while has_more:
        if start_cursor:
            query_body["start_cursor"] = start_cursor

        req = urllib.request.Request(
            url,
            data    = json.dumps(query_body).encode("utf-8"),
            method  = "POST",
            headers = {
                "Authorization":  f"Bearer {token}",
                "Notion-Version": "2022-06-28",
                "Content-Type":   "application/json",
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        for page in data.get("results", []):
            ev = _parse_page(page)
            if ev:
                events.append(ev)

        has_more     = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    return events


def _parse_page(page):
    props = page.get("properties", {})

    title_blocks = props.get("Evènement", {}).get("title", [])
    title = "".join(b.get("plain_text", "") for b in title_blocks).strip()
    if not title:
        return None

    date_obj   = props.get("Date", {}).get("date") or {}
    date_start = (date_obj.get("start") or "")[:10]
    date_end   = (date_obj.get("end")   or "")[:10] or None

    statut = (props.get("Statut", {}).get("select") or {}).get("name", "")

    def ms(key):
        return [x.get("name", "") for x in props.get(key, {}).get("multi_select", [])]

    return {
        "url":        page.get("url", ""),
        "Evènement":  title,
        "dateStart":  date_start or None,
        "dateEnd":    date_end,
        "Statut":     statut,
        "Tags":       ms("Tags"),
        "Techno":     ms("Techno"),
        "Matériel":   ms("Matériel Chrono"),
        "TypeChrono": ms("Type Chrono"),
    }

