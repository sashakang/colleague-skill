#!/usr/bin/env python3
"""
Feishu auto collector

Enter a person name to automatically:
  1. Search Feishu users and fetch the user_id
  2. Find group chats shared with the target user and collect their messages
  3. Collect private chat messages (requires user_access_token)
  4. Search documents and Wikis created or edited by the target user
  5. Fetch document content
  6. Fetch bitable content, if any
  7. Output a unified format for direct use in the create-colleague analysis flow

Prerequisite:
  python3 feishu_auto_collector.py --setup   # configure App ID / Secret once

Private-chat collection (requires extra steps):
  1. Enable user permissions for the Feishu app: im:message, im:chat
  2. Fetch the OAuth authorization code:
     Open in a browser: https://open.feishu.cn/open-apis/authen/v1/authorize?app_id={APP_ID}&redirect_uri=http://www.example.com&scope=im:message%20im:chat
     After authorization, copy the code from the address bar
  3. Exchange the token:
     python3 feishu_auto_collector.py --exchange-code {CODE}
  4. Specify the private chat chat_id when collecting:
     python3 feishu_auto_collector.py --name "Example User" --p2p-chat-id oc_xxx

Usage:
  # group-chat collection (existing method)
  python3 feishu_auto_collector.py --name "Example User" --output-dir ./knowledge/example-user
  python3 feishu_auto_collector.py --name "Example User" --msg-limit 1000 --doc-limit 20

  # private-chat collection
  python3 feishu_auto_collector.py --name "Example User" --p2p-chat-id oc_xxx

  # directly specify open_id + private chat (skip user search)
  python3 feishu_auto_collector.py --open-id ou_xxx --p2p-chat-id oc_xxx --name "Example User"

  # exchange user_access_token
  python3 feishu_auto_collector.py --exchange-code {CODE}
"""

from __future__ import annotations

import json
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

try:
    import requests
except ImportError:
    print("Error: Install requests first: pip3 install requests", file=sys.stderr)
    sys.exit(1)


CONFIG_PATH = Path.home() / ".colleague-skill" / "feishu_config.json"
BASE_URL = "https://open.feishu.cn/open-apis"


# ─── configuration ────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print("Configuration not found; run: python3 feishu_auto_collector.py --setup", file=sys.stderr)
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text())


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False))


def setup_config() -> None:
    print("=== Feishu auto collection configuration ===\n")
    print("Go to https://open.feishu.cn, create an enterprise self-built app, and enable these scopes:")
    print()
    print("  Message scopes (app permissions, used for group-chat collection):")
    print("    im:message:readonly          read messages")
    print("    im:chat:readonly             read group chat information")
    print("    im:chat.members:readonly     read group chat members")
    print()
    print("  Message scopes (user permissions, used for private-chat collection):")
    print("    im:message                   read/send messages as the user")
    print("    im:chat                      read the chat list as the user")
    print()
    print("  User scopes:")
    print("    contact:user.base:readonly       read basic user info")
    print("    contact:department.base:readonly  search users by traversing departments (required for name search)")
    print()
    print("  Document scopes:")
    print("    docs:doc:readonly            read documents")
    print("    wiki:wiki:readonly           read wikis")
    print("    drive:drive:readonly         search drive files")
    print()
    print("  Bitable:")
    print("    bitable:app:readonly         read bitable")
    print()
    print("  --- private-chat collection notes ---")
    print("  Private chat messages must be fetched with user_access_token; app identity cannot access private chats.")
    print("  Fetch method: OAuth authorization. Authorization link format:")
    print("    https://open.feishu.cn/open-apis/authen/v1/authorize?app_id={APP_ID}&redirect_uri={REDIRECT}&scope=im:message%20im:chat")
    print("  After authorization, take the code from the callback URL and exchange the token with --exchange-code.")
    print()

    app_id = input("App ID (cli_xxx): ").strip()
    app_secret = input("App Secret: ").strip()

    config = {"app_id": app_id, "app_secret": app_secret}

    print("\nConfigure user_access_token? (used for private chat message collection, optional)")
    user_token = input("user_access_token (leave empty to skip): ").strip()
    if user_token:
        config["user_access_token"] = user_token
    p2p_chat_id = input("private chat chat_id (leave empty to skip): ").strip()
    if p2p_chat_id:
        config["p2p_chat_id"] = p2p_chat_id

    save_config(config)
    print(f"\n✅ Configuration saved to {CONFIG_PATH}")


# ─── Token ───────────────────────────────────────────────────────────────────

_token_cache: dict = {}


def get_tenant_token(config: dict) -> str:
    """Fetch tenant_access_token with cache; it expires in about 2 hours."""
    now = time.time()
    if _token_cache.get("token") and _token_cache.get("expire", 0) > now + 60:
        return _token_cache["token"]

    resp = requests.post(
        f"{BASE_URL}/auth/v3/tenant_access_token/internal",
        json={"app_id": config["app_id"], "app_secret": config["app_secret"]},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        print(f"fetch token failed: {data}", file=sys.stderr)
        sys.exit(1)

    token = data["tenant_access_token"]
    _token_cache["token"] = token
    _token_cache["expire"] = now + data.get("expire", 7200)
    return token


def api_get(path: str, params: dict, config: dict, use_user_token: bool = False) -> dict:
    if use_user_token and config.get("user_access_token"):
        token = config["user_access_token"]
    else:
        token = get_tenant_token(config)
    resp = requests.get(
        f"{BASE_URL}{path}",
        params=params,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    return resp.json()


def api_post(path: str, body: dict, config: dict, use_user_token: bool = False) -> dict:
    if use_user_token and config.get("user_access_token"):
        token = config["user_access_token"]
    else:
        token = get_tenant_token(config)
    resp = requests.post(
        f"{BASE_URL}{path}",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    return resp.json()


def exchange_code_for_token(code: str, config: dict) -> dict:
    """Exchange an OAuth authorization code for user_access_token."""
    app_token = get_tenant_token(config)
    resp = requests.post(
        f"{BASE_URL}/authen/v1/oidc/access_token",
        headers={"Authorization": f"Bearer {app_token}"},
        json={"grant_type": "authorization_code", "code": code},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        print(f"exchange token failed: {data}", file=sys.stderr)
        return {}
    return data.get("data", {})


# ─── user search ─────────────────────────────────────────────────────────────────

def _find_user_by_contact(name: str, config: dict) -> Optional[dict]:
    """Find a user by email or mobile number with tenant_access_token."""
    # Determine the input type.
    emails, mobiles = [], []
    if "@" in name:
        emails = [name]
    elif name.replace("+", "").replace("-", "").isdigit():
        mobiles = [name]
    else:
        return None  # Not an email or mobile number; skip this lookup.

    body = {}
    if emails:
        body["emails"] = emails
    if mobiles:
        body["mobiles"] = mobiles

    data = api_post("/contact/v3/users/batch_get_id", body, config)
    if data.get("code") != 0:
        print(f"  Email/mobile lookup failed (code={data.get('code')}): {data.get('msg')}", file=sys.stderr)
        return None

    user_list = data.get("data", {}).get("user_list", [])
    for item in user_list:
        user_id = item.get("user_id")
        if user_id:
            # Fetch user details.
            detail = api_get(f"/contact/v3/users/{user_id}", {"user_id_type": "user_id"}, config)
            if detail.get("code") == 0:
                user_data = detail.get("data", {}).get("user", {})
                print(f"  found user: {user_data.get('name', user_id)}", file=sys.stderr)
                return user_data
            # If details cannot be fetched, return the basic information.
            return {"user_id": user_id, "open_id": item.get("open_id", ""), "name": name}

    return None


def _find_user_by_department(name: str, config: dict) -> Optional[dict]:
    """Search users by traversing departments with tenant_access_token."""
    print(f"  Searching for {name} by traversing departments ...", file=sys.stderr)

    # Recursively fetch all department IDs.
    dept_ids = ["0"]  # 0 = root department
    queue = ["0"]
    while queue:
        parent_id = queue.pop(0)
        data = api_get(
            f"/contact/v3/departments/{parent_id}/children",
            {"page_size": 50, "fetch_child": False},
            config,
        )
        if data.get("code") != 0:
            if parent_id == "0":
                print(f"  Department traversal failed (code={data.get('code')}): {data.get('msg')}", file=sys.stderr)
                print("  Confirm that contact:department.base:readonly is enabled", file=sys.stderr)
                return None
            continue

        children = data.get("data", {}).get("items", [])
        for child in children:
            child_id = child.get("department_id", "")
            if child_id:
                dept_ids.append(child_id)
                queue.append(child_id)

    print(f"  Found {len(dept_ids)} departments; searching users ...", file=sys.stderr)

    # Search users in each department.
    matches = []
    for dept_id in dept_ids:
        page_token = None
        while True:
            params = {"department_id": dept_id, "page_size": 50}
            if page_token:
                params["page_token"] = page_token

            data = api_get("/contact/v3/users/find_by_department", params, config)
            if data.get("code") != 0:
                break

            users = data.get("data", {}).get("items", [])
            for u in users:
                uname = u.get("name", "")
                en_name = u.get("en_name", "")
                if name in uname or name in en_name or uname == name or en_name == name:
                    matches.append(u)

            if not data.get("data", {}).get("has_more"):
                break
            page_token = data.get("data", {}).get("page_token")

        if len(matches) >= 10:
            break  # Enough matches.

    return _select_user(matches, name)


def _select_user(users: list, name: str) -> Optional[dict]:
    """Select a user from a candidate list."""
    if not users:
        print(f"  user not found: {name}", file=sys.stderr)
        return None

    # Deduplicate by user_id.
    seen = set()
    deduped = []
    for u in users:
        uid = u.get("user_id", u.get("open_id", id(u)))
        if uid not in seen:
            seen.add(uid)
            deduped.append(u)
    users = deduped

    if len(users) == 1:
        u = users[0]
        dept_ids = u.get("department_ids", [])
        print(f"  found user: {u.get('name')} (department: {dept_ids[0] if dept_ids else ''})", file=sys.stderr)
        return u

    # Multiple results; ask the user to choose.
    print(f"\n  Found {len(users)} results. Please choose:")
    for i, u in enumerate(users):
        dept_ids = u.get("department_ids", [])
        dept_str = dept_ids[0] if dept_ids else ""
        en = u.get("en_name", "")
        label = f"{u.get('name', '')} ({en})" if en else u.get("name", "")
        print(f"    [{i+1}] {label}  dept={dept_str}  uid={u.get('user_id', '')}")

    choice = input("\n  Select number (default 1): ").strip() or "1"
    try:
        idx = int(choice) - 1
        return users[idx]
    except (ValueError, IndexError):
        return users[0]


def find_user(name: str, config: dict) -> Optional[dict]:
    """Search Feishu users.

    Strategy:
      1. If the input is an email or mobile number, call batch_get_id directly.
      2. Otherwise, traverse departments to search by name.
      3. If department traversal fails, suggest searching by email or mobile number.
    """
    print(f"  search user: {name} ...", file=sys.stderr)

    # Method 1: direct lookup by email or mobile number.
    user = _find_user_by_contact(name, config)
    if user:
        return user

    # Method 2: department traversal.
    user = _find_user_by_department(name, config)
    if user:
        return user

    # All lookup methods failed.
    print(f"\n  ❌ Could not find user {name}", file=sys.stderr)
    print("  Suggestions:", file=sys.stderr)
    print("    1. Confirm that contact:department.base:readonly is enabled", file=sys.stderr)
    print("    2. Search by email instead: --name user@company.com", file=sys.stderr)
    print("    3. Search by mobile number instead: --name +8613800138000", file=sys.stderr)
    return None


# ─── messages ─────────────────────────────────────────────────────────────────

def is_bracketed_placeholder(text: str) -> bool:
    """Return whether text looks like a localized attachment/system placeholder."""
    stripped = text.strip()
    return len(stripped) >= 3 and stripped.startswith("[") and stripped.endswith("]")


def get_chats_with_user(user_open_id: str, config: dict) -> list:
    """Find group chats that contain both the bot and the target user."""
    print("  Fetching group chat list ...", file=sys.stderr)

    chats = []
    page_token = None

    while True:
        params = {"page_size": 100}
        if page_token:
            params["page_token"] = page_token

        data = api_get("/im/v1/chats", params, config)
        if data.get("code") != 0:
            print(f"  fetch group chat failed: {data.get('msg')}", file=sys.stderr)
            break

        items = data.get("data", {}).get("items", [])
        chats.extend(items)

        if not data.get("data", {}).get("has_more"):
            break
        page_token = data.get("data", {}).get("page_token")

    print(f"  Found {len(chats)} group chats; checking members ...", file=sys.stderr)

    # Keep only groups that contain the target user.
    result = []
    for chat in chats:
        chat_id = chat.get("chat_id")
        if not chat_id:
            continue

        members_data = api_get(
            f"/im/v1/chats/{chat_id}/members",
            {"page_size": 100},
            config,
        )
        members = members_data.get("data", {}).get("items", [])
        for m in members:
            if m.get("member_id") == user_open_id or m.get("open_id") == user_open_id:
                result.append(chat)
                print(f"    ✓ {chat.get('name', chat_id)}", file=sys.stderr)
                break

    return result


def fetch_messages_from_chat(
    chat_id: str,
    user_open_id: str,
    limit: int,
    config: dict,
) -> list:
    """Fetch messages from the target user in a specified group chat."""
    messages = []
    page_token = None

    while len(messages) < limit:
        params = {
            "container_id_type": "chat",
            "container_id": chat_id,
            "page_size": 50,
            "sort_type": "ByCreateTimeDesc",
        }
        if page_token:
            params["page_token"] = page_token

        data = api_get("/im/v1/messages", params, config)
        if data.get("code") != 0:
            break

        items = data.get("data", {}).get("items", [])
        if not items:
            break

        for item in items:
            sender = item.get("sender", {})
            sender_id = sender.get("id") or sender.get("open_id", "")
            if sender_id != user_open_id:
                continue

            # Parse message content.
            content_raw = item.get("body", {}).get("content", "")
            try:
                content_obj = json.loads(content_raw)
                # Rich text message.
                if isinstance(content_obj, dict):
                    text_parts = []
                    for line in content_obj.get("content", []):
                        for seg in line:
                            if seg.get("tag") in ("text", "a"):
                                text_parts.append(seg.get("text", ""))
                    content = " ".join(text_parts)
                else:
                    content = str(content_obj)
            except Exception:
                content = content_raw

            content = content.strip()
            if not content or is_bracketed_placeholder(content):
                continue

            ts = item.get("create_time", "")
            if ts:
                try:
                    ts = datetime.fromtimestamp(int(ts) / 1000).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass

            messages.append({"content": content, "time": ts})

        if not data.get("data", {}).get("has_more"):
            break
        page_token = data.get("data", {}).get("page_token")

    return messages[:limit]


def fetch_p2p_messages(
    chat_id: str,
    user_open_id: str,
    limit: int,
    config: dict,
) -> list:
    """Fetch all messages from a private chat with user_access_token."""
    messages = []
    page_token = None

    while len(messages) < limit:
        params = {
            "container_id_type": "chat",
            "container_id": chat_id,
            "page_size": 50,
            "sort_type": "ByCreateTimeDesc",
        }
        if page_token:
            params["page_token"] = page_token

        data = api_get("/im/v1/messages", params, config, use_user_token=True)
        if data.get("code") != 0:
            print(f"  Failed to fetch private chat messages (code={data.get('code')}): {data.get('msg')}", file=sys.stderr)
            break

        items = data.get("data", {}).get("items", [])
        if not items:
            break

        for item in items:
            sender = item.get("sender", {})
            sender_id = sender.get("id") or sender.get("open_id", "")

            # Parse message content.
            content_raw = item.get("body", {}).get("content", "")
            try:
                content_obj = json.loads(content_raw)
                if isinstance(content_obj, dict):
                    # Plain text message.
                    if "text" in content_obj:
                        content = content_obj["text"]
                    else:
                        # Rich text message.
                        text_parts = []
                        for line in content_obj.get("content", []):
                            for seg in line:
                                if seg.get("tag") in ("text", "a"):
                                    text_parts.append(seg.get("text", ""))
                        content = " ".join(text_parts)
                else:
                    content = str(content_obj)
            except Exception:
                content = content_raw

            content = content.strip()
            if not content or is_bracketed_placeholder(content):
                continue

            ts = item.get("create_time", "")
            if ts:
                try:
                    ts = datetime.fromtimestamp(int(ts) / 1000).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass

            is_target = (sender_id == user_open_id)
            messages.append({
                "content": content,
                "time": ts,
                "sender_id": sender_id,
                "is_target": is_target,
            })

        if not data.get("data", {}).get("has_more"):
            break
        page_token = data.get("data", {}).get("page_token")

    return messages[:limit]


def collect_messages(
    user: dict,
    msg_limit: int,
    config: dict,
) -> str:
    """Collect all messages for the target user (group chat + private chat)."""
    user_open_id = user.get("open_id") or user.get("user_id", "")
    name = user.get("name", "")

    all_messages = []
    chat_sources = []

    # -- private-chat collection (requires user_access_token + p2p_chat_id) --
    p2p_chat_id = config.get("p2p_chat_id", "")
    user_token = config.get("user_access_token", "")

    if user_token and p2p_chat_id:
        print(f"  📱 Collecting private chat messages (chat_id: {p2p_chat_id})...", file=sys.stderr)
        p2p_msgs = fetch_p2p_messages(p2p_chat_id, user_open_id, msg_limit, config)
        for m in p2p_msgs:
            m["chat"] = "private chat"
        all_messages.extend(p2p_msgs)
        chat_sources.append(f"private chat ({len(p2p_msgs)} items)")
        print(f"    fetched {len(p2p_msgs)} private chat messages", file=sys.stderr)
    elif user_token and not p2p_chat_id:
        print("  ⚠️  user_access_token is set but p2p_chat_id is not configured; skipping private-chat collection", file=sys.stderr)
        print("     Add p2p_chat_id to the configuration; it can be fetched from the send message API response", file=sys.stderr)

    # -- group-chat collection (uses tenant_access_token) --
    remaining = msg_limit - len(all_messages)
    if remaining > 0:
        chats = get_chats_with_user(user_open_id, config)
        if chats:
            per_chat_limit = max(100, remaining // len(chats))
            for chat in chats:
                chat_id = chat.get("chat_id")
                chat_name = chat.get("name", chat_id)
                print(f"  Fetching messages from \"{chat_name}\" ...", file=sys.stderr)

                msgs = fetch_messages_from_chat(chat_id, user_open_id, per_chat_limit, config)
                for m in msgs:
                    m["chat"] = chat_name
                all_messages.extend(msgs)
                chat_sources.append(f"{chat_name} ({len(msgs)} items)")
                print(f"    fetched {len(msgs)} items", file=sys.stderr)

    if not all_messages:
        tips = f"# messages\n\nNo messages found for {name}.\n\n"
        tips += "Possible reasons:\n"
        tips += "  - group-chat collection: the bot has not been added to the relevant group chats\n"
        tips += "  - private-chat collection: user_access_token or p2p_chat_id is not configured\n"
        tips += "\nPrivate-chat collection configuration:\n"
        tips += "  1. Enable im:message and im:chat user permissions in the Feishu developer console\n"
        tips += "  2. Fetch user_access_token through OAuth authorization (--exchange-code)\n"
        tips += "  3. Configure p2p_chat_id (private chat conversation ID)\n"
        return tips

    # Categorized output.
    # Private chat messages include both sides, so mark the speaker.
    target_msgs = [m for m in all_messages if m.get("is_target", True)]
    other_msgs = [m for m in all_messages if not m.get("is_target", True)]

    long_msgs = [m for m in target_msgs if len(m.get("content", "")) > 50]
    short_msgs = [m for m in target_msgs if len(m.get("content", "")) <= 50]

    lines = [
        f"# Feishu messages (auto collection)",
        f"target: {name}",
        f"sources: {', '.join(chat_sources)}",
        f"total {len(all_messages)} messages (target user {len(target_msgs)} items, other party {len(other_msgs)} items)",
        "",
        "---",
        "",
        "## long messages (opinions/decisions/technical)",
        "",
    ]
    for m in long_msgs:
        lines.append(f"[{m.get('time', '')}][{m.get('chat', '')}] {m['content']}")
        lines.append("")

    lines += ["---", "", "## daily messages (style reference)", ""]
    for m in short_msgs[:300]:
        lines.append(f"[{m.get('time', '')}] {m['content']}")

    # Private chat conversation context keeps both sides for context.
    p2p_msgs = [m for m in all_messages if m.get("chat") == "private chat"]
    if p2p_msgs:
        lines += ["", "---", "", "## private chat conversation context (includes both sides)", ""]
        # Ascending time order.
        p2p_sorted = sorted(p2p_msgs, key=lambda x: x.get("time", ""))
        for m in p2p_sorted[:500]:
            who = f"[{name}]" if m.get("is_target") else "[other party]"
            lines.append(f"[{m.get('time', '')}] {who} {m['content']}")

    return "\n".join(lines)


# ─── document collection ─────────────────────────────────────────────────────────────

def search_docs_by_user(user_open_id: str, name: str, doc_limit: int, config: dict) -> list:
    """Search documents created or edited by the target user."""
    print(f"  Searching documents for {name} ...", file=sys.stderr)

    data = api_post(
        "/search/v2/message",
        {
            "query": name,
            "search_type": "docs",
            "docs_options": {
                "creator_ids": [user_open_id],
            },
            "page_size": doc_limit,
        },
        config,
    )

    if data.get("code") != 0:
        # Fallback: keyword search.
        print("  Creator search failed; falling back to keyword search ...", file=sys.stderr)
        data = api_post(
            "/search/v2/message",
            {
                "query": name,
                "search_type": "docs",
                "page_size": doc_limit,
            },
            config,
        )

    docs = []
    for item in data.get("data", {}).get("results", []):
        doc_info = item.get("docs_info", {})
        if doc_info:
            docs.append({
                "title": doc_info.get("title", ""),
                "url": doc_info.get("url", ""),
                "type": doc_info.get("docs_type", ""),
                "creator": doc_info.get("creator", {}).get("name", ""),
            })

    print(f"  Found {len(docs)} documents", file=sys.stderr)
    return docs


def fetch_doc_content(doc_token: str, doc_type: str, config: dict) -> str:
    """Fetch content for a single document."""
    if doc_type in ("doc", "docx"):
        data = api_get(f"/docx/v1/documents/{doc_token}/raw_content", {}, config)
        return data.get("data", {}).get("content", "")

    elif doc_type == "wiki":
        # Fetch wiki node information first.
        node_data = api_get(f"/wiki/v2/spaces/get_node", {"token": doc_token}, config)
        obj_token = node_data.get("data", {}).get("node", {}).get("obj_token", doc_token)
        obj_type = node_data.get("data", {}).get("node", {}).get("obj_type", "docx")
        return fetch_doc_content(obj_token, obj_type, config)

    return ""


def collect_docs(user: dict, doc_limit: int, config: dict) -> str:
    """Collect documents for the target user."""
    import re
    user_open_id = user.get("open_id") or user.get("user_id", "")
    name = user.get("name", "")

    docs = search_docs_by_user(user_open_id, name, doc_limit, config)
    if not docs:
        return f"# document content\n\nNo documents found for {name}\n"

    lines = [
        f"# document content (auto collection)",
        f"target: {name}",
        f"total {len(docs)} documents",
        "",
    ]

    for doc in docs:
        url = doc.get("url", "")
        title = doc.get("title", "Untitled")
        doc_type = doc.get("type", "")

        print(f"  Fetching document: {title} ...", file=sys.stderr)

        # Extract token from URL.
        token_match = re.search(r"/(?:wiki|docx|docs|sheets|base)/([A-Za-z0-9]+)", url)
        if not token_match:
            continue
        doc_token = token_match.group(1)

        content = fetch_doc_content(doc_token, doc_type or "docx", config)
        if not content or len(content.strip()) < 20:
            print("    content is empty; skip", file=sys.stderr)
            continue

        lines += [
            f"---",
            f"## {title}",
            f"Link: {url}",
            f"Creator: {doc.get('creator', '')}",
            "",
            content.strip(),
            "",
        ]

    return "\n".join(lines)


# ─── bitable ─────────────────────────────────────────────────────────────────

def collect_bitable(app_token: str, config: dict) -> str:
    """Fetch bitable content."""
    # Fetch all tables.
    data = api_get(f"/bitable/v1/apps/{app_token}/tables", {"page_size": 100}, config)
    tables = data.get("data", {}).get("items", [])

    if not tables:
        return "(bitable is empty)\n"

    lines = []
    for table in tables:
        table_id = table.get("table_id")
        table_name = table.get("name", table_id)

        # Fetch fields.
        fields_data = api_get(
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            {"page_size": 100},
            config,
        )
        fields = [f.get("field_name", "") for f in fields_data.get("data", {}).get("items", [])]

        # Fetch records.
        records_data = api_get(
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            {"page_size": 100},
            config,
        )
        records = records_data.get("data", {}).get("items", [])

        lines.append(f"### Table: {table_name}")
        lines.append("")
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


# ─── main flow ───────────────────────────────────────────────────────────────────

def collect_all(
    name: str,
    output_dir: Path,
    msg_limit: int,
    doc_limit: int,
    config: dict,
) -> dict:
    """Collect all available data for a colleague and write it to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {}

    print(f"\n🔍 start collection: {name}\n", file=sys.stderr)

    # Step 1: search user
    user = find_user(name, config)
    if not user:
        print(f"❌ user not found {name}; check that the name is correct", file=sys.stderr)
        sys.exit(1)

    # Step 2: collect messages
    print(f"\n📨 Collecting messages (limit {msg_limit} items)...", file=sys.stderr)
    try:
        msg_content = collect_messages(user, msg_limit, config)
        msg_path = output_dir / "messages.txt"
        msg_path.write_text(msg_content, encoding="utf-8")
        results["messages"] = str(msg_path)
        print(f"  ✅ messages → {msg_path}", file=sys.stderr)
    except Exception as e:
        print(f"  ⚠️  message collection failed: {e}", file=sys.stderr)

    # Step 3: collect documents
    print(f"\n📄 Collecting documents (limit {doc_limit})...", file=sys.stderr)
    try:
        doc_content = collect_docs(user, doc_limit, config)
        doc_path = output_dir / "docs.txt"
        doc_path.write_text(doc_content, encoding="utf-8")
        results["docs"] = str(doc_path)
        print(f"  ✅ document content → {doc_path}", file=sys.stderr)
    except Exception as e:
        print(f"  ⚠️  document collection failed: {e}", file=sys.stderr)

    # Write summary.
    summary = {
        "name": name,
        "user_id": user.get("user_id", ""),
        "open_id": user.get("open_id", ""),
        "department": user.get("department_path", []),
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "files": results,
    }
    (output_dir / "collection_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2)
    )

    print(f"\n✅ collection complete, output directory: {output_dir}", file=sys.stderr)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Feishu data auto collector")
    parser.add_argument("--setup", action="store_true", help="Initialize configuration")
    parser.add_argument("--name", help="person name")
    parser.add_argument("--output-dir", default=None, help="output directory (default ./knowledge/{name})")
    parser.add_argument("--msg-limit", type=int, default=1000, help="maximum messages to collect (default 1000)")
    parser.add_argument("--doc-limit", type=int, default=20, help="maximum documents to collect (default 20)")
    parser.add_argument("--exchange-code", metavar="CODE", help="exchange an OAuth authorization code for user_access_token and save it to configuration")
    parser.add_argument("--user-token", metavar="TOKEN", help="directly specify user_access_token (override the config file)")
    parser.add_argument("--p2p-chat-id", metavar="CHAT_ID", help="private chat conversation ID (override the config file)")
    parser.add_argument("--open-id", metavar="OPEN_ID", help="directly specify the target user's open_id (skip user search)")

    args = parser.parse_args()

    if args.setup:
        setup_config()
        return

    config = load_config()

    # exchange user_access_token
    if args.exchange_code:
        token_data = exchange_code_for_token(args.exchange_code, config)
        if token_data:
            config["user_access_token"] = token_data["access_token"]
            config["refresh_token"] = token_data.get("refresh_token", "")
            save_config(config)
            print(f"✅ user_access_token saved (scope: {token_data.get('scope', '')})")
            print(f"   token: {token_data['access_token'][:20]}...")
        else:
            print("❌ exchange failed; check whether the code is valid")
        return

    if not args.name and not args.open_id:
        parser.error("provide --name or --open-id")

    # CLI arguments override configuration
    if args.user_token:
        config["user_access_token"] = args.user_token
    if args.p2p_chat_id:
        config["p2p_chat_id"] = args.p2p_chat_id

    output_dir = Path(args.output_dir) if args.output_dir else Path(f"./knowledge/{args.name or 'target'}")

    # if open_id is provided, skip user search
    if args.open_id:
        user = {"open_id": args.open_id, "name": args.name or "target"}
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n🔍 Using specified open_id: {args.open_id}\n", file=sys.stderr)

        # Only collect messages.
        print(f"📨 Collecting messages (limit {args.msg_limit} items)...", file=sys.stderr)
        msg_content = collect_messages(user, args.msg_limit, config)
        msg_path = output_dir / "messages.txt"
        msg_path.write_text(msg_content, encoding="utf-8")
        print(f"  ✅ messages → {msg_path}", file=sys.stderr)
        return

    collect_all(
        name=args.name,
        output_dir=output_dir,
        msg_limit=args.msg_limit,
        doc_limit=args.doc_limit,
        config=config,
    )


if __name__ == "__main__":
    main()
