#!/usr/bin/env python3
"""
Slack auto collector

Enter a colleague's Slack name/username and automatically:
  1. search Slack users and fetch user_id
  2. find channels shared with the Bot and collect messages sent by that user
  3. output a standard format for direct use in the create-colleague analysis flow

Prerequisite:
  python3 slack_auto_collector.py --setup   # configure Bot Token (one time)

Usage:
  python3 slack_auto_collector.py --name "Jane Doe" --output-dir ./knowledge/jane
  python3 slack_auto_collector.py --name "john" --msg-limit 500 --channel-limit 30

Required Bot Token scopes(OAuth & Permissions):
  channels:history      read public channel messages
  channels:read         list public channels
  groups:history        read private channel messages
  groups:read           list private channels
  im:history            read DM messages (optional)
  im:read               list DMs(optional)
  mpim:history          read group DM messages (optional)
  mpim:read             list group DMs(optional)
  users:read            search users

Notes:
  - Free workspaces retain only the most recent 90 days of messages
  - A workspace admin must install the Bot App
"""

from __future__ import annotations

import json
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# ─── Dependency check ──────────────────────────────────────────────────────────────────

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except ImportError:
    print(
        "Error:Install first slack_sdk:pip3 install slack-sdk",
        file=sys.stderr,
    )
    sys.exit(1)

# ─── Constants ──────────────────────────────────────────────────────────────────────

CONFIG_PATH = Path.home() / ".colleague-skill" / "slack_config.json"

# Slack channel types (collection scope)
CHANNEL_TYPES = "public_channel,private_channel,mpim,im"

# rate limit retry configuration
MAX_RETRIES = 5
RETRY_BASE_WAIT = 1.0     # shortest wait time in seconds
RETRY_MAX_WAIT = 60.0     # longest wait time in seconds

# Default collection values
DEFAULT_MSG_LIMIT = 1000
DEFAULT_CHANNEL_LIMIT = 50  # maximum number of channels to check


# ─── Error types ──────────────────────────────────────────────────────────────────

class SlackCollectorError(Exception):
    """Expected error during collection; exit directly."""


class SlackScopeError(SlackCollectorError):
    """Bot Token is missing required scopes."""


class SlackAuthError(SlackCollectorError):
    """Token is invalid or expired."""


# ─── Configuration management ──────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(
            "Configuration not found; run:python3 slack_auto_collector.py --setup",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        return json.loads(CONFIG_PATH.read_text())
    except json.JSONDecodeError:
        print(f"Configuration file is invalid; run --setup again: {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False))


def setup_config() -> None:
    print("=== Slack auto-collection configuration ===\n")
    print("Step 1: Go to https://api.slack.com/apps and create a new App")
    print("        Select 'From scratch', enter an App Name, then select the target Workspace\n")
    print("Step 2: Open OAuth & Permissions, then add these Bot Token Scopes:")
    print()
    print("  Message scopes (required):")
    print("    channels:history     read public channel history")
    print("    groups:history       read private channel history")
    print("    mpim:history         read group DM history")
    print("    im:history           read DM history (optional)")
    print()
    print("  Channel information (required):")
    print("    channels:read        list public channels")
    print("    groups:read          list private channels")
    print("    mpim:read            list group DMs")
    print("    im:read              list DMs(optional)")
    print()
    print("  User information(required):")
    print("    users:read           search users")
    print()
    print("Step 3:Install to Workspace → copy the Bot User OAuth Token(xoxb-...)")
    print("Step 4:invite the Bot to target channels(/invite @your-bot-name)\n")

    token = input("Bot User OAuth Token (xoxb-...): ").strip()
    if not token.startswith("xoxb-"):
        print("Warning:Token format is invalid; it should start with xoxb-", file=sys.stderr)

    # Validate whether the token is valid.
    print("\nValidating token ...", end=" ", flush=True)
    try:
        client = WebClient(token=token)
        resp = client.auth_test()
        workspace = resp.get("team", "Unknown")
        bot_name = resp.get("user", "Unknown")
        print(f"OK\n  Workspace:{workspace},Bot:{bot_name}")
    except SlackApiError as e:
        err = e.response.get("error", str(e))
        print(f"failed\n  Error:{err}", file=sys.stderr)
        if err == "invalid_auth":
            print("  Token is invalid,regenerate it", file=sys.stderr)
        sys.exit(1)

    config = {"bot_token": token}
    save_config(config)
    print(f"\n✅ Configuration saved to {CONFIG_PATH}")
    print("   Confirm the Bot has been invited to target channels; otherwise messages cannot be read")


# ─── Slack Client wrapper (with rate limit retry) ─────────────────────────────────────────

class RateLimitedClient:
    """Wrap slack_sdk WebClient and automatically handle 429 rate limits."""

    def __init__(self, token: str) -> None:
        self._client = WebClient(token=token)

    def call(self, method: str, **kwargs) -> dict:
        """Call any Slack API and automatically wait/retry when ratelimited."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                fn = getattr(self._client, method)
                resp = fn(**kwargs)
                return resp.data
            except SlackApiError as e:
                error = e.response.get("error", "")

                # Rate limit: read the Retry-After header and wait.
                if error == "ratelimited":
                    wait = float(
                        e.response.headers.get("Retry-After", RETRY_BASE_WAIT * attempt)
                    )
                    wait = min(wait, RETRY_MAX_WAIT)
                    print(
                        f"  [rate limit] wait {wait:.0f}s (retry {attempt}/{MAX_RETRIES})...",
                        file=sys.stderr,
                    )
                    time.sleep(wait)
                    continue

                # Permission error: raise directly without retrying.
                if error == "missing_scope":
                    missing = e.response.get("needed", "unknown")
                    raise SlackScopeError(
                        f"Bot Token is missing scope: {missing}\n"
                        f"  Go to https://api.slack.com/apps -> OAuth & Permissions -> Bot Token Scopes and add it"
                    ) from e

                if error in ("invalid_auth", "token_revoked", "account_inactive"):
                    raise SlackAuthError(
                        f"Token authentication failed ({error}); rerun --setup to configure a new Token"
                    ) from e

                # No channel access (Bot has not joined): let the caller handle it.
                if error in ("not_in_channel", "channel_not_found"):
                    raise

                # Other error: print a warning and return empty data.
                print(f"  [API Warning] {method} returned error:{error}", file=sys.stderr)
                return {}

        # Retries exhausted.
        print(f"  [Error] {method} failed after multiple retries,skip", file=sys.stderr)
        return {}

    def paginate(self, method: str, result_key: str, **kwargs) -> list:
        """Auto-paginate and return the merged list of all results."""
        items: list = []
        cursor = None

        while True:
            params = dict(kwargs)
            if cursor:
                params["cursor"] = cursor

            data = self.call(method, **params)
            if not data:
                break

            items.extend(data.get(result_key, []))

            meta = data.get("response_metadata", {})
            cursor = meta.get("next_cursor")
            if not cursor:
                break

        return items


# ─── user search ──────────────────────────────────────────────────────────────────

def find_user(name: str, client: RateLimitedClient) -> Optional[dict]:
    """
    Search Slack users by name (real_name / display_name / name).
    Supports names, usernames, and fuzzy matching.
    """
    print(f"  search user:{name} ...", file=sys.stderr)

    try:
        members = client.paginate("users_list", "members", limit=200)
    except SlackScopeError as e:
        print(f"  ❌ {e}", file=sys.stderr)
        sys.exit(1)

    # Filter out Bot and deactivated accounts.
    members = [
        m for m in members
        if not m.get("is_bot") and not m.get("deleted") and m.get("id") != "USLACKBOT"
    ]

    name_lower = name.lower()

    def score(member: dict) -> int:
        profile = member.get("profile", {})
        real_name = (profile.get("real_name") or "").lower()
        display_name = (profile.get("display_name") or "").lower()
        username = (member.get("name") or "").lower()

        if name_lower in (real_name, display_name, username):
            return 3  # Exact match
        if (
            name_lower in real_name
            or name_lower in display_name
            or name_lower in username
        ):
            return 2  # Contains match
        # Character-by-character name matching.
        if all(ch in real_name or ch in display_name for ch in name_lower if ch.strip()):
            return 1
        return 0

    scored = [(score(m), m) for m in members]
    candidates = [(s, m) for s, m in scored if s > 0]

    if not candidates:
        print(f"  user not found:{name}", file=sys.stderr)
        print(
            "  Tip:Confirm the name spelling, or try an English username (for example john.doe)",
            file=sys.stderr,
        )
        return None

    candidates.sort(key=lambda x: -x[0])

    if len(candidates) == 1:
        _, user = candidates[0]
        _print_user(user)
        return user

    # Multiple candidates; ask the user to choose.
    print(f"\n  Found {len(candidates)} matches. Please choose:")
    for i, (_, m) in enumerate(candidates[:10]):
        profile = m.get("profile", {})
        real_name = profile.get("real_name", "")
        display_name = profile.get("display_name", "")
        username = m.get("name", "")
        title = profile.get("title", "")
        print(f"    [{i+1}] {real_name} (@{display_name or username})  {title}")

    choice = input("\n  Select number (default 1): ").strip() or "1"
    try:
        idx = int(choice) - 1
        _, user = candidates[idx]
    except (ValueError, IndexError):
        _, user = candidates[0]

    _print_user(user)
    return user


def _print_user(user: dict) -> None:
    profile = user.get("profile", {})
    real_name = profile.get("real_name", user.get("name", ""))
    display_name = profile.get("display_name", "")
    title = profile.get("title", "")
    print(
        f"  found user:{real_name} (@{display_name})  {title}",
        file=sys.stderr,
    )


# ─── Channel discovery ──────────────────────────────────────────────────────────────────

def get_channels_with_user(
    user_id: str,
    channel_limit: int,
    client: RateLimitedClient,
) -> list:
    """
    Return all channels the Bot has joined that also contain the target user.
    Strategy: list all Bot channels first, then check each member list.
    """
    print("  fetching channel list ...", file=sys.stderr)

    try:
        channels = client.paginate(
            "conversations_list",
            "channels",
            types=CHANNEL_TYPES,
            exclude_archived=True,
            limit=200,
        )
    except SlackScopeError as e:
        print(f"  ❌ {e}", file=sys.stderr)
        return []

    # Keep only channels where the Bot is a member.
    bot_channels = [c for c in channels if c.get("is_member")]
    print(f"  Bot has joined {len(bot_channels)} channels; checking members ...", file=sys.stderr)

    if len(bot_channels) > channel_limit:
        print(
            f"  channel count exceeds limit {channel_limit}; checking only the first {channel_limit}",
            file=sys.stderr,
        )
        bot_channels = bot_channels[:channel_limit]

    result = []
    for ch in bot_channels:
        ch_id = ch.get("id", "")
        ch_name = ch.get("name", ch_id)

        try:
            members = client.paginate(
                "conversations_members",
                "members",
                channel=ch_id,
                limit=200,
            )
        except SlackApiError as e:
            err = e.response.get("error", "")
            if err in ("not_in_channel", "channel_not_found"):
                continue
            print(f"    skipping channel {ch_name} ({err})", file=sys.stderr)
            continue
        except SlackScopeError as e:
            print(f"  ❌ {e}", file=sys.stderr)
            continue

        if user_id in members:
            result.append(ch)
            print(f"    ✓ #{ch_name}", file=sys.stderr)

    return result


# ─── Message collection ──────────────────────────────────────────────────────────────────

def fetch_messages_from_channel(
    channel_id: str,
    channel_name: str,
    user_id: str,
    limit: int,
    client: RateLimitedClient,
) -> list:
    """
    Fetch messages sent by the target user from the specified channel.
    Page in reverse chronological order until the limit is reached or no more data remains.
    """
    messages = []
    cursor = None
    pages_fetched = 0
    MAX_PAGES = 50  # Prevent infinite pagination.

    while len(messages) < limit and pages_fetched < MAX_PAGES:
        params: dict = {"channel": channel_id, "limit": 200}
        if cursor:
            params["cursor"] = cursor

        try:
            data = client.call("conversations_history", **params)
        except SlackApiError as e:
            err = e.response.get("error", "")
            if err == "not_in_channel":
                print(
                    f"    Bot is not in channel #{channel_name}; skipping (please /invite @bot)",
                    file=sys.stderr,
                )
            else:
                print(f"    fetch #{channel_name} failed ({err})", file=sys.stderr)
            break

        if not data:
            break

        pages_fetched += 1
        raw_msgs = data.get("messages", [])

        for msg in raw_msgs:
            # Keep only non-system messages sent by the target user.
            if msg.get("user") != user_id:
                continue
            if msg.get("subtype"):  # system types such as join/leave/bot_message
                continue

            text = msg.get("text", "").strip()
            if not text:
                continue

            # Filter emoji-only or attachment-only messages.
            if _is_noise(text):
                continue

            ts_raw = msg.get("ts", "")
            time_str = _format_ts(ts_raw)

            # reply_count indicates a thread-starting message, which has higher weight.
            is_thread_starter = bool(msg.get("reply_count", 0))

            messages.append(
                {
                    "content": text,
                    "time": time_str,
                    "channel": channel_name,
                    "is_thread_starter": is_thread_starter,
                }
            )

        meta = data.get("response_metadata", {})
        cursor = meta.get("next_cursor")
        if not cursor:
            break

    return messages[:limit]


def _is_noise(text: str) -> bool:
    """Return whether this is a low-signal message (emoji-only, @mention, URL)."""
    import re
    # Nearly empty after removing Slack-specific formatting.
    cleaned = re.sub(r"<[^>]+>", "", text).strip()
    cleaned = re.sub(r":[a-z_]+:", "", cleaned).strip()
    return len(cleaned) < 2


def _format_ts(ts: str) -> str:
    """Convert Slack timestamp (Unix float string) to readable time."""
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError):
        return ts


# ─── Main collection flow ────────────────────────────────────────────────────────────────

def collect_messages(
    user: dict,
    channels: list,
    msg_limit: int,
    client: RateLimitedClient,
) -> str:
    """Collect target-user messages from all channels and return formatted text."""
    user_id = user["id"]
    name = user.get("profile", {}).get("real_name") or user.get("name", user_id)

    if not channels:
        return (
            f"# messages\n\n"
            f"No channels shared with {name} were found.\n"
            f"Confirm the Bot has been added to relevant channels (/invite @bot)\n"
        )

    all_messages: list = []
    per_channel_limit = max(100, msg_limit // len(channels))

    for ch in channels:
        ch_id = ch.get("id", "")
        ch_name = ch.get("name", ch_id)
        print(f"  fetching messages from #{ch_name} ...", file=sys.stderr)

        msgs = fetch_messages_from_channel(
            ch_id, ch_name, user_id, per_channel_limit, client
        )
        all_messages.extend(msgs)
        print(f"    fetch {len(msgs)} items", file=sys.stderr)

    # Categorize by weight.
    thread_msgs = [m for m in all_messages if m["is_thread_starter"]]
    long_msgs = [
        m for m in all_messages
        if not m["is_thread_starter"] and len(m["content"]) > 50
    ]
    short_msgs = [
        m for m in all_messages
        if not m["is_thread_starter"] and len(m["content"]) <= 50
    ]

    channel_names = ", ".join(f"#{c.get('name', c.get('id', ''))}" for c in channels)

    lines = [
        "# Slack messages (auto collection)",
        f"target: {name}",
        f"source channels: {channel_names}",
        f"total {len(all_messages)} messages",
        f"  thread-starting messages: {len(thread_msgs)} items",
        f"  long messages (>50 chars): {len(long_msgs)} items",
        f"  short messages: {len(short_msgs)} items",
        "",
        "---",
        "",
        "## thread-starting messages (highest weight: opinions/decisions/technical sharing)",
        "",
    ]
    for m in thread_msgs:
        lines.append(f"[{m['time']}][#{m['channel']}] {m['content']}")
        lines.append("")

    lines += [
        "---",
        "",
        "## long messages (opinions/approach/discussions)",
        "",
    ]
    for m in long_msgs:
        lines.append(f"[{m['time']}][#{m['channel']}] {m['content']}")
        lines.append("")

    lines += ["---", "", "## daily messages(style reference)", ""]
    for m in short_msgs[:300]:
        lines.append(f"[{m['time']}] {m['content']}")

    return "\n".join(lines)


def collect_all(
    name: str,
    output_dir: Path,
    msg_limit: int,
    channel_limit: int,
    config: dict,
) -> dict:
    """Collect all Slack data for a colleague and output it to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict = {}

    print(f"\n🔍 start collection:{name}\n", file=sys.stderr)

    # Initialize Client.
    try:
        client = RateLimitedClient(config["bot_token"])
        # Quickly validate token validity.
        auth_data = client.call("auth_test")
        if not auth_data:
            raise SlackAuthError("auth_test returned no response; please check Token")
        print(
            f"  Workspace:{auth_data.get('team')},Bot:{auth_data.get('user')}",
            file=sys.stderr,
        )
    except SlackAuthError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)

    # Step 1: search user
    user = find_user(name, client)
    if not user:
        print(f"❌ user not found {name}; please check whether the name/username is correct", file=sys.stderr)
        sys.exit(1)

    user_id = user["id"]
    profile = user.get("profile", {})
    real_name = profile.get("real_name") or user.get("name", user_id)

    # Step 2: find shared channels
    print(f"\n📡 Finding channels shared with {real_name} (limit {channel_limit})...", file=sys.stderr)
    channels = get_channels_with_user(user_id, channel_limit, client)
    print(f"  shared channels:{len(channels)}", file=sys.stderr)

    # Step 3: collect messages
    print(f"\n📨 Collecting messages (limit {msg_limit} items)...", file=sys.stderr)
    try:
        msg_content = collect_messages(user, channels, msg_limit, client)
        msg_path = output_dir / "messages.txt"
        msg_path.write_text(msg_content, encoding="utf-8")
        results["messages"] = str(msg_path)
        print(f"  ✅ messages → {msg_path}", file=sys.stderr)
    except SlackCollectorError as e:
        print(f"  ❌ {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"  ⚠️  message collection failed:{e}", file=sys.stderr)

    # Write summary.
    summary = {
        "name": real_name,
        "slack_user_id": user_id,
        "display_name": profile.get("display_name", ""),
        "title": profile.get("title", ""),
        "channels": [
            {"id": c.get("id"), "name": c.get("name")} for c in channels
        ],
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "files": results,
        "note": "Free workspaces retain only the most recent 90 days of messages",
    }
    summary_path = output_dir / "collection_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"  ✅ collection summary → {summary_path}", file=sys.stderr)

    print(f"\n✅ collection complete, output directory:{output_dir}", file=sys.stderr)
    return results


# ─── CLI entrypoint ──────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Slack data auto collector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initial configuration
  python3 slack_auto_collector.py --setup

  # Collect colleague data
  python3 slack_auto_collector.py --name "Jane Doe"
  python3 slack_auto_collector.py --name "john.doe" --output-dir ./knowledge/john --msg-limit 500
        """,
    )
    parser.add_argument("--setup", action="store_true", help="Initialize configuration(Bot Token)")
    parser.add_argument("--name", help="person name or Slack username")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="output directory(default ./knowledge/{name})",
    )
    parser.add_argument(
        "--msg-limit",
        type=int,
        default=DEFAULT_MSG_LIMIT,
        help=f"maximum messages to collect(default {DEFAULT_MSG_LIMIT})",
    )
    parser.add_argument(
        "--channel-limit",
        type=int,
        default=DEFAULT_CHANNEL_LIMIT,
        help=f"maximum channels to check (default {DEFAULT_CHANNEL_LIMIT})",
    )

    args = parser.parse_args()

    if args.setup:
        setup_config()
        return

    if not args.name:
        parser.print_help()
        parser.error("provide --name argument")

    config = load_config()
    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else Path(f"./knowledge/{args.name}")
    )

    try:
        collect_all(
            name=args.name,
            output_dir=output_dir,
            msg_limit=args.msg_limit,
            channel_limit=args.channel_limit,
            config=config,
        )
    except SlackCollectorError as e:
        print(f"\n❌ collection failed:{e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nCanceled", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
