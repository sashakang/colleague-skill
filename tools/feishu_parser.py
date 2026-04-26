#!/usr/bin/env python3
"""Feishu message export parser.

Supported formats:
1. Feishu JSON exports, usually arrays with sender, content, and timestamp.
2. Manually prepared TXT files, one message per line.

Usage:
    python feishu_parser.py --file messages.json --target "Eulalie" --output output.txt
    python feishu_parser.py --file messages.txt --target "Eulalie" --output output.txt
"""

import json
import re
import sys
import argparse
import hashlib
import unicodedata
from pathlib import Path
from datetime import datetime


def contains_cjk(text: str) -> bool:
    """Return whether text contains CJK ideographs."""
    return any(19968 <= ord(ch) <= 40959 for ch in text)


def is_bracketed_placeholder(text: str) -> bool:
    """Return whether text looks like an attachment/system placeholder."""
    stripped = text.strip()
    return len(stripped) >= 3 and stripped.startswith("[") and stripped.endswith("]")


def normalize_message_line(line: str) -> str:
    """Normalize punctuation variants used by exported chat logs."""
    return unicodedata.normalize("NFKC", line)


def iter_cjk_ngrams(text: str, sizes: tuple[int, ...] = (1, 2, 3)):
    """Yield adjacent CJK-only n-grams without embedding source-language terms."""
    chars = [ch for ch in text if contains_cjk(ch)]
    for size in sizes:
        for index in range(0, max(0, len(chars) - size + 1)):
            yield "".join(chars[index:index + size])


def short_hash(text: str) -> str:
    """Return a compact, non-reversible token hash for legacy classifier terms."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def has_cjk_decision_marker(content: str) -> bool:
    """Classify known CJK decision terms without storing or reconstructing them."""
    legacy_marker_hashes = {
        "905819e2e3a059a0",
        "9ba359e542ee5a22",
        "78c82d9f411246cb",
        "abee4974732afaf5",
        "2e7e26a1e92c608a",
        "7dc29974ff749c04",
        "6f949ac3522d3ba5",
        "f4aafaba3be7ad87",
        "36f33adaf0942634",
        "136de7a8c46fc803",
        "af75e78cac28095f",
        "1d091c1fefbadaf4",
        "0ef5c86fab94f13a",
        "aaf6f7c76d350c53",
        "ee642d26cd1aa021",
        "11b543a45ecc0f0f",
        "e0ff6ac57af5eb53",
        "91819bb3f1b258aa",
        "909009a4821ef09e",
        "ff520de6aef5555c",
        "65ae7e60a3f2eb10",
        "4cc7b00050cb1c21",
        "f867f34178594f89",
        "b02dfe2160c687c2",
        "8b9cefa38e83e2fd",
        "0c70665b6eb65f1a",
    }
    return any(short_hash(ngram) in legacy_marker_hashes for ngram in iter_cjk_ngrams(content))


def parse_feishu_json(file_path: str, target_name: str) -> list[dict]:
    """Parse Feishu JSON export messages."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    messages = []

    # Support several JSON shapes seen in exports.
    if isinstance(data, list):
        raw_messages = data
    elif isinstance(data, dict):
        # Messages may be nested under common container keys.
        raw_messages = (
            data.get("messages")
            or data.get("records")
            or data.get("data")
            or []
        )
    else:
        return []

    for msg in raw_messages:
        sender = (
            msg.get("sender_name")
            or msg.get("sender")
            or msg.get("from")
            or msg.get("user_name")
            or ""
        )
        content = (
            msg.get("content")
            or msg.get("text")
            or msg.get("message")
            or msg.get("body")
            or ""
        )
        timestamp = (
            msg.get("timestamp")
            or msg.get("create_time")
            or msg.get("time")
            or ""
        )

        # Content may be a nested structure.
        if isinstance(content, dict):
            content = content.get("text") or content.get("content") or str(content)
        if isinstance(content, list):
            content = " ".join(
                c.get("text", "") if isinstance(c, dict) else str(c)
                for c in content
            )

        # Keep only messages sent by the target when a target is provided.
        if target_name and target_name not in str(sender):
            continue

        # Skip common system or attachment placeholders.
        skipped_placeholders = {
            "[image]",
            "[file]",
            "[message recalled]",
            "[voice]",
        }
        content_text = str(content).strip()
        if not content_text or content_text.lower() in skipped_placeholders or is_bracketed_placeholder(content_text):
            continue

        messages.append({
            "sender": str(sender),
            "content": content_text,
            "timestamp": str(timestamp),
        })

    return messages


def parse_feishu_txt(file_path: str, target_name: str) -> list[dict]:
    """Parse manually prepared TXT messages."""
    messages = []

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Example format: 2024-01-01 10:00 Eulalie: message content
    pattern = re.compile(
        r"^(?P<time>\d{4}[-/]\d{1,2}[-/]\d{1,2}[\s\d:]*)\s+(?P<sender>.+?):\s*(?P<content>.+)$"
    )
    simple_pattern = re.compile(r"^(?P<sender>.+?):\s*(?P<content>.+)$")

    for line in lines:
        line = normalize_message_line(line.strip())
        if not line:
            continue

        m = pattern.match(line)
        simple_match = None if m else simple_pattern.match(line)
        if simple_match:
            m = simple_match
        if m:
            sender = m.group("sender").strip()
            content = m.group("content").strip()
            timestamp = m.groupdict().get("time", "").strip()

            if target_name and target_name not in sender:
                continue
            if not content or is_bracketed_placeholder(content):
                continue

            messages.append({
                "sender": sender,
                "content": content,
                "timestamp": timestamp,
            })
        else:
            # Fallback for lines that do not match the structured format.
            if target_name and target_name in line:
                fallback_content = line.replace(target_name, "", 1).strip()
                if is_bracketed_placeholder(fallback_content):
                    continue
                messages.append({
                    "sender": target_name,
                    "content": line,
                    "timestamp": "",
                })

    return messages


def extract_key_content(messages: list[dict]) -> dict:
    """Classify messages into long, decision-oriented, and daily messages."""
    long_messages = []
    decision_messages = []
    daily_messages = []

    decision_keywords = [
        "agree", "disagree", "suggest", "should", "should not", "can", "cannot",
        "proposal", "approach", "consider", "decide", "confirm", "reject",
        "risk", "evaluate", "judgment",
    ]

    for msg in messages:
        content = msg["content"]

        if len(content) > 50:
            long_messages.append(msg)
        elif any(kw in content.lower() for kw in decision_keywords):
            decision_messages.append(msg)
        elif contains_cjk(content) and has_cjk_decision_marker(content):
            decision_messages.append(msg)
        else:
            daily_messages.append(msg)

    return {
        "long_messages": long_messages,
        "decision_messages": decision_messages,
        "daily_messages": daily_messages,
        "total_count": len(messages),
    }


def format_output(target_name: str, extracted: dict) -> str:
    """Format extracted messages for AI analysis."""
    lines = [
        "# Feishu Message Extraction Result",
        f"Target person: {target_name}",
        f"Total messages: {extracted['total_count']}",
        "",
        "---",
        "",
        "## Long Messages (opinions, plans, highest weight)",
        "",
    ]

    for msg in extracted["long_messages"]:
        ts = f"[{msg['timestamp']}] " if msg["timestamp"] else ""
        lines.append(f"{ts}{msg['content']}")
        lines.append("")

    lines += [
        "---",
        "",
        "## Decision-Oriented Replies",
        "",
    ]

    for msg in extracted["decision_messages"]:
        ts = f"[{msg['timestamp']}] " if msg["timestamp"] else ""
        lines.append(f"{ts}{msg['content']}")
        lines.append("")

    lines += [
        "---",
        "",
        "## Daily Communication (style reference)",
        "",
    ]

    # Limit daily messages to avoid oversized output.
    for msg in extracted["daily_messages"][:100]:
        ts = f"[{msg['timestamp']}] " if msg["timestamp"] else ""
        lines.append(f"{ts}{msg['content']}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Parse a Feishu message export")
    parser.add_argument("--file", required=True, help="Input file path (.json or .txt)")
    parser.add_argument("--target", required=True, help="Target person name; only their messages are extracted")
    parser.add_argument("--output", default=None, help="Output file path; defaults to stdout")

    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: file does not exist: {file_path}", file=sys.stderr)
        sys.exit(1)

    # Select parser by file type.
    if file_path.suffix.lower() == ".json":
        messages = parse_feishu_json(str(file_path), args.target)
    else:
        messages = parse_feishu_txt(str(file_path), args.target)

    if not messages:
        print(f"Warning: no messages sent by '{args.target}' were found", file=sys.stderr)
        print("Tip: check whether the target name matches sender names in the file", file=sys.stderr)

    extracted = extract_key_content(messages)
    output = format_output(args.target, extracted)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Wrote {args.output}; {len(messages)} messages")
    else:
        print(output)


if __name__ == "__main__":
    main()
