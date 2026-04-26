#!/usr/bin/env python3
"""
DingTalk auto collector

Given a person's name, this tool automatically:
  1. searches DingTalk users and fetches the userId
  2. searches documents and wiki content created or edited by that person
  3. fetches bitables when available
  4. collects messages with the browser approach because the API does not support historical message retrieval
  5. writes a unified output format for the create-colleague analysis flow

DingTalk limitation:
  The DingTalk Open API does not provide an endpoint for historical messages,
  so the messages step automatically uses Playwright browser collection.

Prerequisites:
  pip3 install requests playwright
  playwright install chromium
  python3 dingtalk_auto_collector.py --setup

Usage:
  python3 dingtalk_auto_collector.py --name "Zhang San" --output-dir ./knowledge/zhangsan
  python3 dingtalk_auto_collector.py --name "Zhang San" --skip-messages   # skip message collection
  python3 dingtalk_auto_collector.py --name "Zhang San" --doc-limit 20
"""

from __future__ import annotations

import json
import sys
import time
import argparse
import platform
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

try:
    import requests
except ImportError:
    print("Error: install the dependency first: pip3 install requests", file=sys.stderr)
    sys.exit(1)


CONFIG_PATH = Path.home() / ".colleague-skill" / "dingtalk_config.json"
API_BASE = "https://api.dingtalk.com"


# ─── configuration ────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print("Configuration not found; run: python3 dingtalk_auto_collector.py --setup", file=sys.stderr)
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False))


def setup_config() -> None:
    print("=== DingTalk auto collection configuration ===\n")
    print("Go to https://open-dev.dingtalk.com, create an internal enterprise app, and enable these scopes:\n")
    print("  Contacts:")
    print("    qyapi_get_member_detail     Query user details")
    print("    Contact.User.mobile         Read user mobile numbers (optional)")
    print()
    print("  Message scopes (optional; only for sending messages; historical messages require the browser approach):")
    print("    qyapi_robot_sendmsg         Send messages with a bot")
    print()
    print("  Documents:")
    print("    Doc.WorkSpace.READ          Read workspaces")
    print("    Doc.File.READ               Read files")
    print()
    print("  bitable:")
    print("    Bitable.Record.READ         Read records")
    print()

    app_key = input("AppKey (ding_xxx): ").strip()
    app_secret = input("AppSecret: ").strip()

    config = {"app_key": app_key, "app_secret": app_secret}
    save_config(config)
    print(f"\n✅ Configuration saved to {CONFIG_PATH}")
    print("\nNote: message collection requires Playwright. Confirm it is installed:")
    print("  pip3 install playwright && playwright install chromium")


# ─── Token ───────────────────────────────────────────────────────────────────

_token_cache: dict = {}


def get_access_token(config: dict) -> str:
    """Fetch a DingTalk access_token with caching."""
    now = time.time()
    if _token_cache.get("token") and _token_cache.get("expire", 0) > now + 60:
        return _token_cache["token"]

    resp = requests.post(
        f"{API_BASE}/v1.0/oauth2/accessToken",
        json={"appKey": config["app_key"], "appSecret": config["app_secret"]},
        timeout=10,
    )
    data = resp.json()

    if "accessToken" not in data:
        print(f"fetch token failed: {data}", file=sys.stderr)
        sys.exit(1)

    token = data["accessToken"]
    _token_cache["token"] = token
    _token_cache["expire"] = now + data.get("expireIn", 7200)
    return token


def api_get(path: str, params: dict, config: dict) -> dict:
    token = get_access_token(config)
    resp = requests.get(
        f"{API_BASE}{path}",
        params=params,
        headers={"x-acs-dingtalk-access-token": token},
        timeout=15,
    )
    return resp.json()


def api_post(path: str, body: dict, config: dict) -> dict:
    token = get_access_token(config)
    resp = requests.post(
        f"{API_BASE}{path}",
        json=body,
        headers={"x-acs-dingtalk-access-token": token},
        timeout=15,
    )
    return resp.json()


# ─── user search ─────────────────────────────────────────────────────────────────

def find_user(name: str, config: dict) -> Optional[dict]:
    """Search DingTalk users by name."""
    print(f"  search user: {name} ...", file=sys.stderr)

    data = api_post(
        "/v1.0/contact/users/search",
        {"searchText": name, "offset": 0, "size": 10},
        config,
    )

    users = data.get("list", []) or data.get("result", {}).get("list", [])

    if not users:
        # Fallback: search by traversing departments.
        print("  API search returned no results; traversing contacts ...", file=sys.stderr)
        users = search_users_by_dept(name, config)

    if not users:
        print(f"  user not found: {name}", file=sys.stderr)
        return None

    if len(users) == 1:
        u = users[0]
        print(f"  found user: {u.get('name')} ({u.get('deptNameList', [''])[0] if isinstance(u.get('deptNameList'), list) else ''})", file=sys.stderr)
        return u

    print(f"\n  Found {len(users)} results. Please choose:")
    for i, u in enumerate(users):
        dept = u.get("deptNameList", [""])
        dept_str = dept[0] if isinstance(dept, list) and dept else ""
        print(f"    [{i+1}] {u.get('name')}  {dept_str}  {u.get('unionId', '')}")

    choice = input("\n  Select a number (default 1): ").strip() or "1"
    try:
        return users[int(choice) - 1]
    except (ValueError, IndexError):
        return users[0]


def search_users_by_dept(name: str, config: dict, dept_id: int = 1, depth: int = 0) -> list:
    """Recursively traverse departments to search users, with a depth limit of 3."""
    if depth > 3:
        return []

    results = []

    # Fetch the department user list.
    data = api_post(
        "/v1.0/contact/users/simplelist",
        {"deptId": dept_id, "cursor": 0, "size": 100},
        config,
    )
    users = data.get("list", [])
    for u in users:
        if name in u.get("name", ""):
            # Fetch detailed user information.
            detail = api_get(f"/v1.0/contact/users/{u.get('userId')}", {}, config)
            results.append(detail.get("result", u))

    # Fetch child departments.
    sub_data = api_get(
        "/v1.0/contact/departments/listSubDepts",
        {"deptId": dept_id},
        config,
    )
    for sub in sub_data.get("result", []):
        results.extend(search_users_by_dept(name, config, sub.get("deptId"), depth + 1))

    return results


# ─── document collection ───────────────────────────────────────────────────────────────

def list_workspaces(config: dict) -> list:
    """Fetch all workspaces."""
    data = api_get("/v1.0/doc/workspaces", {"maxResults": 50}, config)
    return data.get("workspaceModels", []) or data.get("result", {}).get("workspaceModels", [])


def search_docs_by_user(user_id: str, name: str, doc_limit: int, config: dict) -> list:
    """Search documents created by the user."""
    print(f"  searching documents for {name} ...", file=sys.stderr)

    # Approach 1: global search.
    data = api_post(
        "/v1.0/doc/search",
        {
            "keyword": name,
            "size": doc_limit,
            "offset": 0,
        },
        config,
    )

    docs = []
    items = data.get("docList", []) or data.get("result", {}).get("docList", [])

    for item in items:
        creator_id = item.get("creatorId", "") or item.get("creator", {}).get("userId", "")
        # Keep only documents created by the target user.
        if user_id and creator_id and creator_id != user_id:
            continue
        docs.append({
            "title": item.get("title", "Untitled"),
            "docId": item.get("docId", ""),
            "spaceId": item.get("spaceId", ""),
            "type": item.get("docType", ""),
            "url": item.get("shareUrl", ""),
            "creator": item.get("creatorName", name),
        })

    if not docs:
        # Approach 2: traverse workspaces to find documents.
        print("  search returned no results; traversing workspaces ...", file=sys.stderr)
        workspaces = list_workspaces(config)
        for ws in workspaces[:5]:  # Check at most 5 workspaces.
            ws_id = ws.get("spaceId") or ws.get("workspaceId")
            if not ws_id:
                continue
            files_data = api_get(
                f"/v1.0/doc/workspaces/{ws_id}/files",
                {"maxResults": 20, "orderBy": "modified_time", "order": "DESC"},
                config,
            )
            for f in files_data.get("files", []):
                creator_id = f.get("creatorId", "")
                if user_id and creator_id and creator_id != user_id:
                    continue
                docs.append({
                    "title": f.get("fileName", "Untitled"),
                    "docId": f.get("docId", ""),
                    "spaceId": ws_id,
                    "type": f.get("docType", ""),
                    "url": f.get("shareUrl", ""),
                    "creator": name,
                })

    print(f"  found {len(docs)} documents", file=sys.stderr)
    return docs[:doc_limit]


def fetch_doc_content(doc_id: str, space_id: str, config: dict) -> str:
    """Fetch the text content of a single document."""
    # Approach 1: fetch document content directly.
    data = api_get(
        f"/v1.0/doc/workspaces/{space_id}/files/{doc_id}/content",
        {},
        config,
    )

    content = (
        data.get("content")
        or data.get("result", {}).get("content")
        or data.get("markdown")
        or data.get("result", {}).get("markdown")
        or ""
    )

    if content:
        return content

    # Approach 2: fetch the download link, then download the content.
    dl_data = api_get(
        f"/v1.0/doc/workspaces/{space_id}/files/{doc_id}/download",
        {},
        config,
    )
    dl_url = dl_data.get("downloadUrl") or dl_data.get("result", {}).get("downloadUrl")
    if dl_url:
        try:
            resp = requests.get(dl_url, timeout=15)
            return resp.text
        except Exception:
            pass

    return ""


def collect_docs(user: dict, doc_limit: int, config: dict) -> str:
    """Collect documents for the target user."""
    user_id = user.get("userId", "")
    name = user.get("name", "")

    docs = search_docs_by_user(user_id, name, doc_limit, config)
    if not docs:
        return f"# document content\n\nNo documents related to {name} were found.\n"

    lines = [
        "# document content (DingTalk auto collection)",
        f"target: {name}",
        f"total {len(docs)} documents",
        "",
    ]

    for doc in docs:
        title = doc.get("title", "Untitled")
        doc_id = doc.get("docId", "")
        space_id = doc.get("spaceId", "")
        url = doc.get("url", "")

        if not doc_id or not space_id:
            continue

        print(f"  fetching document: {title} ...", file=sys.stderr)
        content = fetch_doc_content(doc_id, space_id, config)

        if not content or len(content.strip()) < 20:
            print("    content is empty, skipping", file=sys.stderr)
            continue

        lines += [
            "---",
            f"## {title}",
            f"Link: {url}",
            f"Creator: {doc.get('creator', '')}",
            "",
            content.strip(),
            "",
        ]

    return "\n".join(lines)


# ─── bitable ─────────────────────────────────────────────────────────────────

def search_bitables(user_id: str, name: str, config: dict) -> list:
    """Search bitables for the target user."""
    print(f"  searching bitables for {name} ...", file=sys.stderr)

    data = api_post(
        "/v1.0/doc/search",
        {"keyword": name, "size": 20, "offset": 0, "docTypes": ["bitable"]},
        config,
    )

    tables = []
    for item in data.get("docList", []):
        if item.get("docType") != "bitable":
            continue
        creator_id = item.get("creatorId", "")
        if user_id and creator_id and creator_id != user_id:
            continue
        tables.append(item)

    print(f"  found {len(tables)} bitables", file=sys.stderr)
    return tables


def fetch_bitable_content(base_id: str, config: dict) -> str:
    """Fetch bitable content."""
    # Fetch all sheets.
    sheets_data = api_get(
        f"/v1.0/bitable/bases/{base_id}/sheets",
        {},
        config,
    )
    sheets = sheets_data.get("sheets", []) or sheets_data.get("result", {}).get("sheets", [])

    if not sheets:
        return "(bitable is empty or access is denied)\n"

    lines = []
    for sheet in sheets:
        sheet_id = sheet.get("sheetId") or sheet.get("id")
        sheet_name = sheet.get("name", sheet_id)

        # Fetch fields.
        fields_data = api_get(
            f"/v1.0/bitable/bases/{base_id}/sheets/{sheet_id}/fields",
            {"maxResults": 100},
            config,
        )
        fields = [f.get("name", "") for f in fields_data.get("fields", [])]

        # Fetch records.
        records_data = api_get(
            f"/v1.0/bitable/bases/{base_id}/sheets/{sheet_id}/records",
            {"maxResults": 200},
            config,
        )
        records = records_data.get("records", []) or records_data.get("result", {}).get("records", [])

        lines.append(f"### Table: {sheet_name}")
        lines.append("")

        if fields:
            lines.append("| " + " | ".join(fields) + " |")
            lines.append("| " + " | ".join(["---"] * len(fields)) + " |")

        for rec in records:
            row_data = rec.get("fields", {})
            row = []
            for f in fields:
                val = row_data.get(f, "")
                if isinstance(val, list):
                    val = " ".join(
                        v.get("text", str(v)) if isinstance(v, dict) else str(v)
                        for v in val
                    )
                row.append(str(val).replace("|", "&#124;").replace("\n", " "))
            lines.append("| " + " | ".join(row) + " |")

        lines.append("")

    return "\n".join(lines)


def collect_bitables(user: dict, config: dict) -> str:
    """Collect bitables for the target user."""
    user_id = user.get("userId", "")
    name = user.get("name", "")

    tables = search_bitables(user_id, name, config)
    if not tables:
        return f"# bitable\n\nNo bitables for {name} were found.\n"

    lines = [
        "# bitable (DingTalk auto collection)",
        f"target: {name}",
        f"total {len(tables)} bitables",
        "",
    ]

    for t in tables:
        title = t.get("title", "Untitled")
        doc_id = t.get("docId", "")
        print(f"  fetching bitable: {title} ...", file=sys.stderr)

        content = fetch_bitable_content(doc_id, config)
        lines += [
            "---",
            f"## {title}",
            "",
            content,
        ]

    return "\n".join(lines)


# ─── messages (browser approach) ───────────────────────────────────────────────────────

def get_default_chrome_profile() -> str:
    system = platform.system()
    if system == "Darwin":
        return str(Path.home() / "Library/Application Support/Google/Chrome/Default")
    elif system == "Linux":
        return str(Path.home() / ".config/google-chrome/Default")
    elif system == "Windows":
        import os
        return str(Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data/Default")
    return str(Path.home() / ".config/google-chrome/Default")


def short_ui_hash(text: str) -> str:
    """Return a compact hash for matching localized browser labels."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def collect_messages_browser(
    name: str,
    msg_limit: int,
    chrome_profile: Optional[str],
    headless: bool,
) -> str:
    """Collect DingTalk web messages through a Playwright browser."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return (
            "# messages\n\n"
            "⚠️  Playwright is not installed, so messages cannot be collected.\n"
            "Run: pip3 install playwright && playwright install chromium\n"
        )

    import re

    profile = chrome_profile or get_default_chrome_profile()
    print(f"  starting browser collection for DingTalk messages ({'headless' if headless else 'headed'})...", file=sys.stderr)

    messages = []

    with sync_playwright() as p:
        try:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=profile,
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
                ignore_default_args=["--enable-automation"],
                viewport={"width": 1280, "height": 900},
            )
        except Exception as e:
            return f"# messages\n\n⚠️  Could not start browser: {e}\n"

        page = ctx.new_page()

        # Open DingTalk Web.
        page.goto("https://im.dingtalk.com", wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)

        # Check login state.
        if "login" in page.url.lower() or page.query_selector(".login-wrap"):
            if headless:
                ctx.close()
                return (
                    "# messages\n\n"
                    "⚠️  Login was not detected. Re-run with --show-browser and log in to DingTalk in the opened window.\n"
                )
            print("  Log in to DingTalk in the browser, then press Enter to continue...", file=sys.stderr)
            input()

        # Search messages for the target contact.
        try:
            # Click the search box.
            search_clicked = False
            search_selectors = [
                '.search-input',
                '[data-testid="search"]',
                '.im-search',
            ]
            for sel in search_selectors:
                el = page.query_selector(sel)
                if el:
                    el.click()
                    time.sleep(0.5)
                    page.keyboard.type(name)
                    time.sleep(2)
                    search_clicked = True
                    break

            if not search_clicked:
                localized_search_hash = "44ce7ae909bbb28b"
                candidates = page.query_selector_all(
                    'input, textarea, [contenteditable="true"], [role="searchbox"], '
                    '[placeholder], [aria-label], [title]'
                )
                for el in candidates:
                    labels = el.evaluate("""
                        node => [
                            node.getAttribute('placeholder'),
                            node.getAttribute('aria-label'),
                            node.getAttribute('title'),
                            node.innerText,
                            node.textContent
                        ].filter(Boolean).map(value => value.trim()).filter(Boolean)
                    """)
                    if any(short_ui_hash(label) == localized_search_hash for label in labels):
                        el.click()
                        time.sleep(0.5)
                        page.keyboard.type(name)
                        time.sleep(2)
                        search_clicked = True
                        break

            # Click the first result.
            result_selectors = [
                '.search-result-item',
                '.contact-item',
                '.result-item',
            ]
            for sel in result_selectors:
                result = page.query_selector(sel)
                if result:
                    result.click()
                    time.sleep(2)
                    break
        except Exception as e:
            print(f"  automatic navigation failed: {e}", file=sys.stderr)
            if not headless:
                print(f"  Manually open the conversation with {name}, then press Enter to continue...", file=sys.stderr)
                input()

        # Scroll upward to load historical messages.
        print("  loading message history ...", file=sys.stderr)
        for _ in range(15):
            page.keyboard.press("Control+Home")
            time.sleep(1)
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(0.8)

        time.sleep(2)

        # Extract messages.
        raw_messages = page.evaluate(f"""
            () => {{
                const target = "{name}";
                const results = [];
                const selectors = [
                    '.message-item-content-container',
                    '.im-message-item',
                    '[data-message-id]',
                    '.msg-wrap',
                ];

                let items = [];
                for (const sel of selectors) {{
                    items = document.querySelectorAll(sel);
                    if (items.length > 0) break;
                }}

                items.forEach(item => {{
                    const senderEl = item.querySelector('.sender-name, .nick-name, .name');
                    const contentEl = item.querySelector(
                        '.message-text, .text-content, .msg-content, .im-richtext'
                    );
                    const timeEl = item.querySelector('.message-time, .time, .msg-time');

                    const sender = senderEl ? senderEl.innerText.trim() : '';
                    const content = contentEl ? contentEl.innerText.trim() : '';
                    const time = timeEl ? timeEl.innerText.trim() : '';

                    if (!content) return;
                    if (target && !sender.includes(target)) return;
                    if (/^\[[^\]]+\]$/.test(content)) return;

                    results.push({{ sender, content, time }});
                }});

                return results.slice(-{msg_limit});
            }}
        """)

        ctx.close()
        messages = raw_messages or []

    if not messages:
        return (
            "# messages\n\n"
            f"⚠️  Could not automatically extract messages for {name}.\n"
            "Possible causes: the DingTalk Web DOM changed, or the conversation was not found.\n"
            "Consider manually taking screenshots of the chat history and uploading them.\n"
        )

    long_msgs = [m for m in messages if len(m.get("content", "")) > 50]
    short_msgs = [m for m in messages if len(m.get("content", "")) <= 50]

    lines = [
        "# messages (DingTalk browser collection)",
        f"target: {name}",
        f"total {len(messages)} items",
        "Note: DingTalk API does not support historical message retrieval; this content was collected through the browser.",
        "",
        "---",
        "",
        "## long messages (opinions/decisions/technical)",
        "",
    ]
    for m in long_msgs:
        lines.append(f"[{m.get('time', '')}] {m.get('content', '')}")
        lines.append("")

    lines += ["---", "", "## daily messages (style reference)", ""]
    for m in short_msgs[:300]:
        lines.append(f"[{m.get('time', '')}] {m.get('content', '')}")

    return "\n".join(lines)


# ─── main flow ───────────────────────────────────────────────────────────────────

def collect_all(
    name: str,
    output_dir: Path,
    msg_limit: int,
    doc_limit: int,
    skip_messages: bool,
    chrome_profile: Optional[str],
    headless: bool,
    config: dict,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {}

    print(f"\n🔍 start collection (DingTalk): {name}\n", file=sys.stderr)

    # Step 1: search user
    user = find_user(name, config)
    if not user:
        print(f"❌ user not found: {name}", file=sys.stderr)
        sys.exit(1)

    print(f"  user ID: {user.get('userId', '')}  department: {user.get('deptNameList', [''])[0] if isinstance(user.get('deptNameList'), list) and user.get('deptNameList') else ''}", file=sys.stderr)

    # Step 2: document
    print(f"\n📄 collecting documents (limit {doc_limit})...", file=sys.stderr)
    try:
        doc_content = collect_docs(user, doc_limit, config)
        doc_path = output_dir / "docs.txt"
        doc_path.write_text(doc_content, encoding="utf-8")
        results["docs"] = str(doc_path)
        print(f"  ✅ document → {doc_path}", file=sys.stderr)
    except Exception as e:
        print(f"  ⚠️  document collection failed: {e}", file=sys.stderr)

    # Step 3: bitable
    print(f"\n📊 collecting bitables ...", file=sys.stderr)
    try:
        bitable_content = collect_bitables(user, config)
        bt_path = output_dir / "bitables.txt"
        bt_path.write_text(bitable_content, encoding="utf-8")
        results["bitables"] = str(bt_path)
        print(f"  ✅ bitable → {bt_path}", file=sys.stderr)
    except Exception as e:
        print(f"  ⚠️  bitable collection failed: {e}", file=sys.stderr)

    # Step 4: messages (browser approach)
    if not skip_messages:
        print(f"\n📨 collecting messages (browser approach, limit {msg_limit} items)...", file=sys.stderr)
        print("  ℹ️  DingTalk API does not support historical message retrieval; switching to the browser approach", file=sys.stderr)
        try:
            msg_content = collect_messages_browser(name, msg_limit, chrome_profile, headless)
            msg_path = output_dir / "messages.txt"
            msg_path.write_text(msg_content, encoding="utf-8")
            results["messages"] = str(msg_path)
            print(f"  ✅ messages → {msg_path}", file=sys.stderr)
        except Exception as e:
            print(f"  ⚠️  message collection failed: {e}", file=sys.stderr)
    else:
        print("\n📨 skipping message collection (--skip-messages)", file=sys.stderr)

    # Write the summary.
    summary = {
        "name": name,
        "user_id": user.get("userId", ""),
        "platform": "dingtalk",
        "department": user.get("deptNameList", []),
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "files": results,
        "notes": "messages are collected through the browser because DingTalk API does not support historical message retrieval",
    }
    (output_dir / "collection_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2)
    )

    print(f"\n✅ collection complete → {output_dir}", file=sys.stderr)
    print(f"   files: {', '.join(results.keys())}", file=sys.stderr)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="DingTalk data auto collector")
    parser.add_argument("--setup", action="store_true", help="Initialize configuration")
    parser.add_argument("--name", help="person name")
    parser.add_argument("--output-dir", default=None, help="output directory")
    parser.add_argument("--msg-limit", type=int, default=500, help="maximum messages to collect (default 500)")
    parser.add_argument("--doc-limit", type=int, default=20, help="maximum documents to collect (default 20)")
    parser.add_argument("--skip-messages", action="store_true", help="skip message collection")
    parser.add_argument("--chrome-profile", default=None, help="Chrome profile path")
    parser.add_argument("--show-browser", action="store_true", help="show the browser window for debugging or first login")

    args = parser.parse_args()

    if args.setup:
        setup_config()
        return

    if not args.name:
        parser.error("provide --name")

    config = load_config()
    output_dir = Path(args.output_dir) if args.output_dir else Path(f"./knowledge/{args.name}")

    collect_all(
        name=args.name,
        output_dir=output_dir,
        msg_limit=args.msg_limit,
        doc_limit=args.doc_limit,
        skip_messages=args.skip_messages,
        chrome_profile=args.chrome_profile,
        headless=not args.show_browser,
        config=config,
    )


if __name__ == "__main__":
    main()
