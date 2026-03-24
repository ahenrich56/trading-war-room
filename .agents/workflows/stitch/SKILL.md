---
name: Google Stitch MCP Integration
description: Use the Google Stitch AI design tool to generate UIs and fetch screens via its MCP server proxy.
---

# Google Stitch MCP Skill

Google's Stitch platform allows for rapid AI-generated UI designs that live as HTML/CSS/React components behind an API. This guide outlines how you (the AI Agent) and the user can interact with Stitch through its MCP server wrapper (`@_davideast/stitch-mcp`).

## Prerequisites
Before using Stitch, authenticate the environment.

1. **Initialize Authentication**
   Run the setup wizard to handle gcloud, OAuth, and project setup.
   ```bash
   npx @_davideast/stitch-mcp init
   ```
   *(Note: This requires user interaction to log in.)*

2. **Alternative Authentication (API Key)**
   If the user has a `STITCH_API_KEY`, simply set it in the environment:
   ```bash
   export STITCH_API_KEY="your-api-key"
   ```

## Using the Virtual Tools

The Stitch proxy exposes high-level MCP operations for coding agents. You can run these tools directly via the CLI to extract design code or images.

### 1. Identify Available Projects and Screens
To see what designs are available:
```bash
npx @_davideast/stitch-mcp view --projects
```
Or view a specific screen to get its ID:
```bash
npx @_davideast/stitch-mcp view --project <project-id> --screen <screen-id>
```

### 2. Fetch Screen HTML/Code
Once you have the `projectId` and `screenId`, use the `get_screen_code` virtual tool:
```bash
npx @_davideast/stitch-mcp tool get_screen_code -d '{"projectId": "<project-id>", "screenId": "<screen-id>"}'
```
You can use the resulting HTML/CSS to scaffold React components in the workspace.

### 3. Build a Full Site
To map multiple Stitch screens to specific routes and build an entire deployable site (like Astro), use the `build_site` tool:
```bash
npx @_davideast/stitch-mcp tool build_site -d '{
  "projectId": "123456",
  "routes": [
    { "screenId": "abc", "route": "/" },
    { "screenId": "def", "route": "/about" }
  ]
}'
```

## Previewing Locally
To allow the user to preview all project screens on a local Vite dev server without extracting the code, start the server:
```bash
npx @_davideast/stitch-mcp serve -p <project-id>
```

## Integrating into MCP Client configuration
If you want to formally add the Stitch MCP proxy to this agent workspace's continuous context so it exposes tools natively, add this configuration block to your MCP client config (e.g., `gemini-cli`, `cursor`, etc.):

```json
{
  "mcpServers": {
    "stitch": {
      "command": "npx",
      "args": ["@_davideast/stitch-mcp", "proxy"]
    }
  }
}
```
