# openclaw-mimo-patch

Fix Xiaomi MiMo API `400 Param Incorrect` error when using tool calling with reasoning mode in [OpenClaw](https://github.com/openclaw/openclaw).

## Problem

When using Xiaomi MiMo reasoning models (mimo-v2.5-pro, mimo-v2-pro, etc.) as the default model in OpenClaw, **tool calling fails on the second round** with:

```
provider rejected the request schema or tool payload
400 Param Incorrect
```

**Root cause:** MiMo is a reasoning model (like DeepSeek-R1). When it responds with tool calls, the response includes a `reasoning_content` field. On the next request, MiMo's API **requires** this field to be present in the assistant message (even as an empty string `""`). OpenClaw's `convertMessages` function doesn't include `reasoning_content` for Xiaomi models, causing the API to reject the request.

```
Request 1 (OK):  OpenClaw → MiMo → tool_calls + reasoning_content
                  OpenClaw executes tool
Request 2 (400): OpenClaw → MiMo (missing reasoning_content) → ❌ rejected
```

## Usage

```bash
# Apply patch
python patch.py

# Check status (no changes)
python patch.py --check

# Revert to original
python patch.py --revert
```

After patching, restart OpenClaw:
```bash
openclaw gateway restart
```

## When to Re-apply

After any of these events:
- `npm update openclaw`
- `npm install openclaw@latest`
- OpenClaw version change

## Requirements

- Python 3.6+
- OpenClaw installed via npm

## Technical Details

**File patched:**
```
<npm-global-prefix>/node_modules/openclaw/node_modules/@earendil-works/pi-ai/dist/providers/openai-completions.js
```

**Change:** In the `convertMessages` function (~line 700), the condition:
```js
if (compat.requiresReasoningContentOnAssistantMessages && model.reasoning && ...)
```

is expanded to also trigger for `model.provider === "xiaomi"`:
```js
const needsReasoningContent = compat.requiresReasoningContentOnAssistantMessages ||
    (model.reasoning && model.provider === "xiaomi");
```

This matches how DeepSeek models are already handled in the same codebase.

## Tested Models

| Model | Status |
|-------|--------|
| mimo-v2.5-pro | ✅ Fixed |
| mimo-v2.5 | ✅ Fixed |
| mimo-v2-pro | ✅ Fixed |
| mimo-v2-omni | ✅ Fixed |
| mimo-v2-flash | N/A (reasoning=false) |

## License

MIT
