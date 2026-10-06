---
name: render-on-hermes
description: Use whenever any other render-* skill loads, or any time the user asks you to do something on Render. Tells you that this Hermes container has the Render MCP server pre-registered with full MCP tool access for the provided API key and that the `render` CLI is NOT installed in this image, so skip every "install MCP", "install CLI", and "run render CLI" step that upstream render-* skills describe.
version: 1.0.0
author: Render (vendored by Green Hour)
license: MIT
metadata:
  hermes:
    tags: [Render, MCP, Operations, Bootstrap, Security]
    related_skills: [render-mcp, render-deploy, render-debug, render-monitor, render-blueprints]
---

# Render on Hermes

Vendored from [`render-examples/hermes-render`](https://github.com/render-examples/hermes-render) (MIT).
This Green Hour deployment is pre-wired for Render. The other `render-*` skills
(pulled from `github.com/render-oss/skills`) are written for generic AI coding
tools, so they assume you might need to install the CLI or configure MCP
yourself. **Skip all of that.**

## What's already done for you

| Capability        | State on this container                                      |
|-------------------|--------------------------------------------------------------|
| Render MCP server | Registered in `config.yaml` as `render`                      |
| MCP transport     | HTTP, `https://mcp.render.com/mcp`                           |
| MCP auth          | `Authorization: Bearer ${RENDER_MCP_API_KEY}` (lazy)         |
| MCP tool scope    | **Full MCP tool access** for the provided API key            |
| Render CLI        | **Not installed.**                                           |
| Skill bundle      | `github.com/render-oss/skills` at a pinned commit            |

## Default scope: full MCP access

The `render` MCP server is registered without a `tools.include` filter, so you
can see every tool the provided `RENDER_MCP_API_KEY` can use — including
mutating tools. The real permission boundary is the Render role behind that
key. Before mutating anything, state the effect explicitly.

If no workspace is selected, call `mcp_render_list_workspaces` and pick the
obvious one; only ask the user when several are plausible.

## About the `render-cli` skill

The upstream bundle includes a `render-cli` skill describing commands the CLI
can do (live log streaming, `render psql`, SSH). **The CLI is not installed.**
If an MCP equivalent exists, use it (`list_logs`, `get_metrics`, ...). If not,
draft the command for the *user* to run from their own shell — don't run it
through your terminal tool, it will fail with "command not found".

## How MCP tools appear

Hermes prefixes MCP tools with `mcp_<server>_<tool>`, so upstream `list_services()`
is `mcp_render_list_services()` here.

## Quick verification

```
mcp_render_list_services()
```

If that returns a list, MCP is wired up. If it 401s or the tool is missing,
the gateway didn't see `RENDER_MCP_API_KEY` at startup — tell the user to set
it under **Environment** and **Restart gateway**.

## You are running ON Render

This Hermes container is itself a Render web service. If the user says "look at
this service" without naming one, they mean the one you're running inside.
Restarting it kills your own session — never do that casually.
