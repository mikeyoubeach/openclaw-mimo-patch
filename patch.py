#!/usr/bin/env python3
"""
openclaw-mimo-patch
===================
修复 OpenClaw 使用小米 MiMo 推理模型时，tool calling 第二轮请求报 400 的问题。

问题描述：
    MiMo 是推理模型（类似 DeepSeek-R1），首次请求返回的响应中包含 reasoning_content 字段。
    OpenClaw 在执行完工具后发起第二轮请求时，没有把 reasoning_content 字段传回去，
    而 MiMo API 要求 thinking mode 下 assistant message 必须携带此字段（哪怕为空字符串），
    因此 API 返回 "400 Param Incorrect"。

修复方式：
    在 pi-ai 的 convertMessages 函数中，给 xiaomi provider 且 reasoning=true 的模型
    自动注入 reasoning_content: ""，与 DeepSeek 的处理方式一致。

用法：
    python patch.py            # 打补丁
    python patch.py --check    # 检查状态（不修改文件）
    python patch.py --revert   # 恢复原状

仓库：https://github.com/mikeyoubeach/openclaw-mimo-patch
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ============================================================
# 补丁标记（用于检测是否已打过补丁，也方便 --revert 精确回滚）
# ============================================================
PATCH_MARKER = "// [openclaw-mimo-patch] Xiaomi MiMo reasoning_content fix"

# ============================================================
# 定位目标文件
# ============================================================
def find_target() -> Path | None:
    """
    通过 npm prefix -g 动态获取全局安装路径，兼容 Windows / macOS / Linux。
    如果 npm 不可用，则尝试常见默认路径。
    """
    npm_cmd = shutil.which("npm")

    if npm_cmd:
        try:
            prefix = subprocess.check_output(
                [npm_cmd, "prefix", "-g"], text=True, timeout=10
            ).strip()
            candidates = [Path(prefix)]
        except Exception:
            candidates = []
    else:
        candidates = []

    # 常见回退路径
    candidates += [
        Path.home() / "AppData" / "Roaming" / "npm",        # Windows
        Path.home() / ".npm-global",                         # Linux 用户安装
        Path("/usr/local/lib"),                               # macOS / Linux homebrew
        Path("/usr/lib"),                                     # Linux 系统
        Path.home() / "Library" / "Application Support"      # macOS
            / "openclaw" / "node_modules",
    ]

    # XDG
    xdg = os.environ.get("XDG_DATA_HOME", "")
    if xdg:
        candidates.append(Path(xdg))

    target_rel = (
        Path("node_modules") / "openclaw" / "node_modules"
        / "@earendil-works" / "pi-ai" / "dist" / "providers"
        / "openai-completions.js"
    )

    for prefix in candidates:
        p = prefix / target_rel
        if p.exists():
            return p

    return None

# ============================================================
# 代码块定义
# ============================================================

# 原始代码（OpenClaw 未修复时的写法）
ORIGINAL = (
    '            if (compat.requiresReasoningContentOnAssistantMessages &&\n'
    '                model.reasoning &&\n'
    '                assistantMsg.reasoning_content === undefined) {\n'
    '                assistantMsg.reasoning_content = "";\n'
    '            }'
)

# 修复后的代码（增加 xiaomi provider 的判断）
PATCHED = (
    f'            {PATCH_MARKER}\n'
    '            // MiMo 推理模型要求 assistant message 必须携带 reasoning_content\n'
    '            // 字段（哪怕为空字符串），否则 API 返回 400。\n'
    '            // 这里对 xiaomi provider 做与 DeepSeek 相同的处理。\n'
    '            const needsReasoningContent =\n'
    '                compat.requiresReasoningContentOnAssistantMessages ||\n'
    '                (model.reasoning && model.provider === "xiaomi");\n'
    '            if (needsReasoningContent &&\n'
    '                model.reasoning &&\n'
    '                assistantMsg.reasoning_content === undefined) {\n'
    '                assistantMsg.reasoning_content = "";\n'
    '            }'
)

# 不带标记的旧版补丁（兼容早期手动打过的补丁）
PATCHED_NO_MARKER = (
    '            const needsReasoningContent = compat.requiresReasoningContentOnAssistantMessages ||\n'
    '                (model.reasoning && model.provider === "xiaomi");\n'
    '            if (needsReasoningContent &&\n'
    '                model.reasoning &&\n'
    '                assistantMsg.reasoning_content === undefined) {\n'
    '                assistantMsg.reasoning_content = "";\n'
    '            }'
)

# ============================================================
# 核心操作
# ============================================================

def check(target: Path) -> str:
    """检查补丁状态，返回: patched / needs_patch / patched_no_marker / unknown"""
    content = target.read_text(encoding="utf-8")

    if PATCH_MARKER in content:
        return "patched"
    if PATCHED_NO_MARKER in content:
        return "patched_no_marker"
    if ORIGINAL in content:
        return "needs_patch"
    return "unknown"


def apply(target: Path) -> bool:
    """打补丁"""
    content = target.read_text(encoding="utf-8")
    status = check(target)

    if status in ("patched", "patched_no_marker"):
        print("✅ 补丁已存在，无需重复打。")
        return True

    if status != "needs_patch":
        print("❌ 找不到原始代码块，OpenClaw 版本可能已更新。")
        print(f"   请手动检查文件：{target}")
        print("   搜索关键词：requiresReasoningContentOnAssistantMessages")
        return False

    new_content = content.replace(ORIGINAL, PATCHED, 1)
    if new_content == content:
        print("❌ 替换失败，代码结构可能有变化。")
        return False

    target.write_text(new_content, encoding="utf-8")
    print("✅ 补丁打入成功！")
    print(f"   文件：{target}")
    print()
    print("   请运行 openclaw gateway restart 使补丁生效。")
    return True


def revert(target: Path) -> bool:
    """恢复原状"""
    content = target.read_text(encoding="utf-8")

    if PATCH_MARKER not in content and PATCHED_NO_MARKER not in content:
        print("ℹ️  未检测到补丁，无需恢复。")
        return True

    new_content = content.replace(PATCHED, ORIGINAL, 1)
    if new_content == content:
        new_content = content.replace(PATCHED_NO_MARKER, ORIGINAL, 1)

    if new_content == content:
        print("❌ 恢复失败，代码结构可能有变化。")
        return False

    target.write_text(new_content, encoding="utf-8")
    print("✅ 已恢复为原始代码。")
    print(f"   文件：{target}")
    print()
    print("   请运行 openclaw gateway restart 使更改生效。")
    return True


def print_status(target: Path):
    """打印当前状态"""
    status = check(target)
    if status in ("patched", "patched_no_marker"):
        print("✅ 补丁已生效。")
    elif status == "needs_patch":
        print("⚠️  补丁未打！运行 python patch.py 修复。")
    else:
        print("❓ 状态未知，文件结构可能有变化。")


# ============================================================
# 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="修复 OpenClaw + MiMo API tool calling 400 错误"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true",
                       help="仅检查状态，不修改文件")
    group.add_argument("--revert", action="store_true",
                       help="恢复为原始代码")
    args = parser.parse_args()

    target = find_target()
    if not target:
        print("❌ 找不到 OpenClaw 的 pi-ai 模块。")
        print("   请确认 OpenClaw 已通过 npm 安装：npm install -g openclaw")
        sys.exit(1)

    print("openclaw-mimo-patch: 修复 MiMo API 400 Param Incorrect")
    print("=" * 55)
    print(f"目标文件：{target}")
    print()

    if args.check:
        print_status(target)
        sys.exit(0)

    if args.revert:
        ok = revert(target)
        sys.exit(0 if ok else 1)

    # 默认：打补丁
    ok = apply(target)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
