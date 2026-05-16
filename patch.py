#!/usr/bin/env python3
"""
openclaw-mimo-patch: Fix MiMo API 400 error on tool calling in OpenClaw.

Problem: Xiaomi MiMo reasoning models require `reasoning_content` field in
assistant messages during tool-calling rounds. OpenClaw doesn't include it.
Result: "400 Param Incorrect" on the second request of any tool call.

Fix: Patch pi-ai's convertMessages to inject reasoning_content for xiaomi models.

Usage:
    python patch.py          # Apply patch
    python patch.py --check  # Check if patch is needed (no changes)
    python patch.py --revert # Revert to original

Repo: https://github.com/mikeyoubeach/openclaw-mimo-patch
"""

import argparse
import os
import sys
from pathlib import Path

PATCH_MARKER = "// [openclaw-mimo-patch] Xiaomi MiMo reasoning_content fix"

# Locate the file (npm global install)
def find_target():
    # Get npm global prefix dynamically
    import shutil
    npm_cmd = shutil.which("npm")
    if not npm_cmd:
        # Fallback to common paths
        candidates = [
            Path.home() / "AppData" / "Roaming" / "npm",                             # Windows
            Path.home() / ".npm-global",                                              # Linux user install
            Path("/usr/local/lib"),                                                    # macOS/Linux homebrew
            Path("/usr/lib"),                                                          # Linux system
        ]
    else:
        import subprocess
        try:
            prefix = subprocess.check_output(
                [npm_cmd, "prefix", "-g"], text=True, timeout=10
            ).strip()
            candidates = [Path(prefix)]
        except Exception:
            candidates = [Path.home() / "AppData" / "Roaming" / "npm"]

    target_name = Path("node_modules") / "openclaw" / "node_modules" \
        / "@earendil-works" / "pi-ai" / "dist" / "providers" / "openai-completions.js"

    for prefix in candidates:
        p = prefix / target_name
        if p.exists():
            return p
    return None

# The original code block we're looking for
ORIGINAL = (
    '            if (compat.requiresReasoningContentOnAssistantMessages &&\n'
    '                model.reasoning &&\n'
    '                assistantMsg.reasoning_content === undefined) {\n'
    '                assistantMsg.reasoning_content = "";\n'
    '            }'
)

# Our patched version
PATCHED = (
    f'            {PATCH_MARKER}\n'
    '            const needsReasoningContent = compat.requiresReasoningContentOnAssistantMessages ||\n'
    '                (model.reasoning && model.provider === "xiaomi");\n'
    '            if (needsReasoningContent &&\n'
    '                model.reasoning &&\n'
    '                assistantMsg.reasoning_content === undefined) {\n'
    '                assistantMsg.reasoning_content = "";\n'
    '            }'
)


def check(target):
    content = target.read_text(encoding="utf-8")

    if PATCH_MARKER in content:
        return "patched"
    if ORIGINAL in content:
        return "needs_patch"
    # Check if patched version exists without marker (older patch)
    if 'const needsReasoningContent = compat.requiresReasoningContentOnAssistantMessages ||' in content:
        return "patched_no_marker"
    return "unknown"


def apply(target):
    content = target.read_text(encoding="utf-8")
    status = check(target)

    if status == "patched" or status == "patched_no_marker":
        print("✅ Patch already applied, nothing to do.")
        return True

    if status != "needs_patch":
        print("❌ Cannot find the original code block.")
        print("   OpenClaw version may have changed. Please check manually:")
        print(f"   {target}")
        print()
        print("   Look for 'requiresReasoningContentOnAssistantMessages' in convertMessages().")
        return False

    new_content = content.replace(ORIGINAL, PATCHED, 1)
    if new_content == content:
        print("❌ Replacement had no effect. Code may have changed.")
        return False

    target.write_text(new_content, encoding="utf-8")
    print(f"✅ Patch applied successfully!")
    print(f"   File: {target}")
    print()
    print("   Run 'openclaw gateway restart' to activate.")
    return True


def revert(target):
    content = target.read_text(encoding="utf-8")

    if PATCH_MARKER not in content and \
       'const needsReasoningContent = compat.requiresReasoningContentOnAssistantMessages ||' not in content:
        print("ℹ️  No patch found, nothing to revert.")
        return True

    # Revert the version with marker
    new_content = content.replace(PATCHED, ORIGINAL, 1)
    # Also handle version without marker (in case of older patch)
    if new_content == content:
        revert_no_marker = (
            '            const needsReasoningContent = compat.requiresReasoningContentOnAssistantMessages ||\n'
            '                (model.reasoning && model.provider === "xiaomi");\n'
            '            if (needsReasoningContent &&\n'
            '                model.reasoning &&\n'
            '                assistantMsg.reasoning_content === undefined) {\n'
            '                assistantMsg.reasoning_content = "";\n'
            '            }'
        )
        new_content = content.replace(revert_no_marker, ORIGINAL, 1)

    if new_content == content:
        print("❌ Could not revert. Code structure may have changed.")
        return False

    target.write_text(new_content, encoding="utf-8")
    print("✅ Patch reverted to original.")
    print(f"   File: {target}")
    print()
    print("   Run 'openclaw gateway restart' to apply.")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Fix MiMo API 400 error on tool calling in OpenClaw"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true",
                       help="Check patch status without modifying files")
    group.add_argument("--revert", action="store_true",
                       help="Revert the patch to original code")
    args = parser.parse_args()

    target = find_target()
    if not target:
        print("❌ Could not find openclaw pi-ai module.")
        print("   Make sure OpenClaw is installed: npm install -g openclaw")
        sys.exit(1)

    if args.check:
        status = check(target)
        if status == "patched" or status == "patched_no_marker":
            print("✅ Patch is applied.")
        elif status == "needs_patch":
            print("⚠️  Patch is NOT applied. Run 'python patch.py' to fix.")
        else:
            print("❓ Unknown status. File may have changed.")
        sys.exit(0)

    if args.revert:
        ok = revert(target)
        sys.exit(0 if ok else 1)

    # Default: apply
    print("openclaw-mimo-patch: Fix MiMo API 400 Param Incorrect")
    print("=" * 55)
    print()
    ok = apply(target)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
