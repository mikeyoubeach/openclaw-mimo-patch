## Problem

Xiaomi MiMo reasoning models (mimo-v2.5-pro, mimo-v2-pro, etc.) return `reasoning_content` in tool-calling responses. On the next request, MiMo's API **requires** this field to be present in the assistant message (even as empty string `""`), or it returns `400 Param Incorrect`.

This causes all tool-calling workflows to fail on the second round when using MiMo as the default model in OpenClaw (cron jobs, agent sessions, etc.).

## Root Cause

In `convertMessages()` (file: `pi-ai/dist/providers/openai-completions.js`), the `reasoning_content` field is only injected for DeepSeek models via `compat.requiresReasoningContentOnAssistantMessages`. Xiaomi MiMo has the identical requirement but is not covered by the condition.

## Proposed Fix

Expand the condition to also trigger for `model.provider === "xiaomi"`:

```js
// Before (line ~700):
if (compat.requiresReasoningContentOnAssistantMessages && model.reasoning && ...)

// After:
const needsReasoningContent =
    compat.requiresReasoningContentOnAssistantMessages ||
    (model.reasoning && model.provider === "xiaomi");
if (needsReasoningContent && model.reasoning && ...)
```

## Verification

I tested this extensively against the MiMo API (token-plan-cn.xiaomimimo.com):

- Sending assistant message WITH `reasoning_content: ""` → 200 OK
- Sending assistant message WITHOUT `reasoning_content` → 400 "Param Incorrect"
- Sending assistant message WITH `reasoning_content: null` → 400
- Sending `thinking: {type: "disabled"}` (no reasoning_content needed) → 200 OK

The fix ensures `reasoning_content: ""` is always present for Xiaomi reasoning models, matching the DeepSeek behavior already in the codebase.

## Workaround

Until this is merged, users can apply the fix with:
```bash
curl -sL https://raw.githubusercontent.com/mikeyoubeach/openclaw-mimo-patch/master/patch.py | python3
openclaw gateway restart
```

Full details and issue analysis: https://github.com/mikeyoubeach/openclaw-mimo-patch
