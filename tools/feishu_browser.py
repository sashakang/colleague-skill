#!/usr/bin/env python3
"""
Feishu browser collector (Playwright approach)

Reuses the local Chrome login state, requires no token, and can access all authorized Feishu content.

Supports:
  - Feishu documents (docx/docs)
  - Feishu wiki (wiki)
  - Feishu sheets (sheets), exported as CSV
  - Feishu messages from a specified group chat

Install:
  pip install playwright
  playwright install chromium

Usage:
  python3 feishu_browser.py --url "https://xxx.feishu.cn/wiki/xxx" --output out.txt
  python3 feishu_browser.py --url "https://xxx.feishu.cn/docx/xxx" --output out.txt
  python3 feishu_browser.py --chat "Backend Team" --target "Zhang San" --limit 500 --output out.txt
  python3 feishu_browser.py --url "https://xxx.feishu.cn/sheets/xxx" --output out.csv
"""

from __future__ import annotations

import sys
import time
import json
import argparse
import platform
from pathlib import Path
from typing import Optional


def get_default_chrome_profile() -> str:
    """Return the default Chrome profile path for the OS"""
    system = platform.system()
    if system == "Darwin":
        return str(Path.home() / "Library/Application Support/Google/Chrome/Default")
    elif system == "Linux":
        return str(Path.home() / ".config/google-chrome/Default")
    elif system == "Windows":
        import os
        return str(Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data/Default")
    return str(Path.home() / ".config/google-chrome/Default")


def make_context(playwright, chrome_profile: Optional[str], headless: bool):
    """Create a browser context that reuses login state"""
    profile = chrome_profile or get_default_chrome_profile()
    try:
        ctx = playwright.chromium.launch_persistent_context(
            user_data_dir=profile,
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            ignore_default_args=["--enable-automation"],
            viewport={"width": 1280, "height": 900},
        )
        return ctx
    except Exception as e:
        print(f"⚠️  could not load Chrome profile: {e}", file=sys.stderr)
        print(f"   tried path: {profile}", file=sys.stderr)
        print("   Use --chrome-profile to manually specify the path", file=sys.stderr)
        sys.exit(1)


def detect_page_type(url: str) -> str:
    """Determine the Feishu page type from the URL."""
    if "/wiki/" in url:
        return "wiki"
    elif "/docx/" in url or "/docs/" in url:
        return "doc"
    elif "/sheets/" in url or "/spreadsheets/" in url:
        return "sheet"
    elif "/base/" in url:
        return "base"
    else:
        return "unknown"


def fetch_doc(page, url: str) -> str:
    """Collect text content from a Feishu document or wiki page."""
    page.goto(url, wait_until="domcontentloaded", timeout=30000)

    # Wait for the editor to load. Feishu documents can render slowly.
    selectors = [
        ".docs-reader-content",
        ".lark-editor-content",
        "[data-block-type]",
        ".doc-render-core",
        ".wiki-content",
        ".node-doc-content",
    ]

    loaded = False
    for sel in selectors:
        try:
            page.wait_for_selector(sel, timeout=15000)
            loaded = True
            break
        except Exception:
            continue

    if not loaded:
        # Wait briefly, then extract body text directly.
        time.sleep(5)

    # Give asynchronous content extra time to render.
    time.sleep(2)

    # Try multiple selectors to extract body text.
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                text = el.inner_text()
                if len(text.strip()) > 50:
                    return text.strip()
        except Exception:
            continue

    # Fallback: extract the whole body.
    text = page.inner_text("body")
    return text.strip()


def fetch_sheet(page, url: str) -> str:
    """Collect a Feishu sheet and convert it to CSV format."""
    page.goto(url, wait_until="domcontentloaded", timeout=30000)

    try:
        page.wait_for_selector(".spreadsheet-container, .sheet-container", timeout=15000)
    except Exception:
        time.sleep(5)

    time.sleep(3)

    # Extract sheet data through JavaScript.
    data = page.evaluate("""
        () => {
            const rows = [];
            // Try to extract visible cells from the DOM.
            const cells = document.querySelectorAll('[data-row][data-col]');
            if (cells.length === 0) return null;

            const grid = {};
            let maxRow = 0, maxCol = 0;
            cells.forEach(cell => {
                const r = parseInt(cell.getAttribute('data-row'));
                const c = parseInt(cell.getAttribute('data-col'));
                if (!grid[r]) grid[r] = {};
                grid[r][c] = cell.innerText.replace(/\\n/g, ' ').trim();
                maxRow = Math.max(maxRow, r);
                maxCol = Math.max(maxCol, c);
            });

            for (let r = 0; r <= maxRow; r++) {
                const row = [];
                for (let c = 0; c <= maxCol; c++) {
                    row.push(grid[r] && grid[r][c] ? grid[r][c] : '');
                }
                rows.push(row);
            }
            return rows;
        }
    """)

    if data:
        lines = []
        for row in data:
            lines.append(",".join(f'"{cell}"' for cell in row))
        return "\n".join(lines)

    # Fallback: extract text directly.
    return page.inner_text("body")


def fetch_messages(page, chat_name: str, target_name: str, limit: int = 500) -> str:
    """
    Collect messages from the target person in the specified group chat.
    This requires navigating to the Feishu Web messages page first.
    """
    # Open the Feishu messages page.
    page.goto("https://applink.feishu.cn/client/chat/open", wait_until="domcontentloaded", timeout=20000)
    time.sleep(3)

    # Try to search for the group chat.
    try:
        # Click search.
        search_btn = page.query_selector('[data-test-id="search-btn"], .search-button')
        if search_btn:
            search_btn.click()
            time.sleep(1)
            page.keyboard.type(chat_name)
            time.sleep(2)

            # Select the first result.
            result = page.query_selector('.search-result-item:first-child, .im-search-item:first-child')
            if result:
                result.click()
                time.sleep(2)
    except Exception as e:
        print(f"⚠️  automatic group chat search failed: {e}", file=sys.stderr)
        print(f"   Manually navigate to the {chat_name} group chat, then press Enter to continue...", file=sys.stderr)
        input()

    # Scroll upward to load historical messages.
    print("Loading message history...", file=sys.stderr)
    messages_container = page.query_selector('.message-list, .im-message-list, [data-testid="message-list"]')

    if messages_container:
        for _ in range(10):  # Scroll 10 times.
            page.evaluate("el => el.scrollTop = 0", messages_container)
            time.sleep(1.5)
    else:
        for _ in range(10):
            page.keyboard.press("Control+Home")
            time.sleep(1.5)

    time.sleep(2)

    # Extract messages.
    messages = page.evaluate(f"""
        () => {{
            const target = "{target_name}";
            const results = [];

            // Common message DOM structures.
            const msgSelectors = [
                '.message-item',
                '.im-message-item',
                '[data-message-id]',
                '.msg-list-item',
            ];

            let items = [];
            for (const sel of msgSelectors) {{
                items = document.querySelectorAll(sel);
                if (items.length > 0) break;
            }}

            items.forEach(item => {{
                const senderEl = item.querySelector(
                    '.sender-name, .message-sender, [data-testid="sender-name"], .name'
                );
                const contentEl = item.querySelector(
                    '.message-content, .msg-content, [data-testid="message-content"], .text-content'
                );
                const timeEl = item.querySelector(
                    '.message-time, .msg-time, [data-testid="message-time"], .time'
                );

                const sender = senderEl ? senderEl.innerText.trim() : '';
                const content = contentEl ? contentEl.innerText.trim() : '';
                const time = timeEl ? timeEl.innerText.trim() : '';

                if (!content) return;
                if (target && !sender.includes(target)) return;

                results.push({{ sender, content, time }});
            }});

            return results.slice(-{limit});
        }}
    """)

    if not messages:
        print("⚠️  Could not automatically extract messages; trying to extract page text", file=sys.stderr)
        return page.inner_text("body")

    # Categorize output by weight.
    long_msgs = [m for m in messages if len(m.get("content", "")) > 50]
    short_msgs = [m for m in messages if len(m.get("content", "")) <= 50]

    lines = [
        f"# Feishu messages (browser collection)",
        f"group chat: {chat_name}",
        f"target person: {target_name}",
        f"total {len(messages)} messages",
        "",
        "---",
        "",
        "## long messages (opinions/decisions)",
        "",
    ]
    for m in long_msgs:
        lines.append(f"[{m.get('time', '')}] {m.get('content', '')}")
        lines.append("")

    lines += ["---", "", "## daily messages", ""]
    for m in short_msgs[:200]:
        lines.append(f"[{m.get('time', '')}] {m.get('content', '')}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Feishu browser collector that reuses Chrome login state")
    parser.add_argument("--url", help="Feishu document/Wiki/sheet link")
    parser.add_argument("--chat", help="group chat name for message collection")
    parser.add_argument("--target", help="target person name; only this person's messages are extracted")
    parser.add_argument("--limit", type=int, default=500, help="maximum message items to collect (default 500)")
    parser.add_argument("--output", default=None, help="output file path; defaults to stdout")
    parser.add_argument("--chrome-profile", default=None, help="Chrome profile path; defaults to auto-detection")
    parser.add_argument("--headless", action="store_true", help="headless mode; do not show the browser window")
    parser.add_argument("--show-browser", action="store_true", help="show the browser window for debugging")

    args = parser.parse_args()

    if not args.url and not args.chat:
        parser.error("provide --url (document link) or --chat (group chat name)")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Error: install Playwright first: pip install playwright && playwright install chromium", file=sys.stderr)
        sys.exit(1)

    headless = args.headless and not args.show_browser

    print(f"Starting browser ({'headless' if headless else 'headed'} mode)...", file=sys.stderr)

    with sync_playwright() as p:
        ctx = make_context(p, args.chrome_profile, headless=headless)
        page = ctx.new_page()

        # Check whether the user is already logged in.
        page.goto("https://www.feishu.cn", wait_until="domcontentloaded", timeout=15000)
        time.sleep(2)
        if "login" in page.url.lower() or "signin" in page.url.lower():
            print("⚠️  login state was not detected.", file=sys.stderr)
            print("   Log in to Feishu in the opened browser window, then press Enter...", file=sys.stderr)
            if headless:
                print("   Tip: use --show-browser to display the browser window and complete login", file=sys.stderr)
                sys.exit(1)
            input()

        # Run the requested task type.
        if args.url:
            page_type = detect_page_type(args.url)
            print(f"page type: {page_type}, start collection...", file=sys.stderr)

            if page_type == "sheet":
                content = fetch_sheet(page, args.url)
            else:
                content = fetch_doc(page, args.url)

        elif args.chat:
            content = fetch_messages(
                page,
                chat_name=args.chat,
                target_name=args.target or "",
                limit=args.limit,
            )

        ctx.close()

    if not content or len(content.strip()) < 10:
        print("⚠️  could not extract valid content", file=sys.stderr)
        sys.exit(1)

    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
        print(f"✅ saved to {args.output} ({len(content)} characters)", file=sys.stderr)
    else:
        print(content)


if __name__ == "__main__":
    main()
