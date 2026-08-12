# Publishing the CRP Scan VS Code Extension

## Prerequisites

1. **Azure DevOps Personal Access Token (PAT)**
   - Go to https://dev.azure.com/ → Create account if needed
   - User settings → Personal access tokens → New Token
   - Scopes: **Marketplace > Manage**, **Marketplace > Acquire**, **Marketplace > Publish**
   - Set expiration (max 1 year)
   - Copy the token immediately — it won't be shown again

2. **Publisher Account**
   - Go to https://marketplace.visualstudio.com/manage
   - Sign in with Microsoft account
   - Create publisher: `autocyber-ai`
   - Fill in display name, description, website (crprotocol.io)

3. **vsce CLI**
   ```bash
   npm install -g @vscode/vsce
   ```

## Build & Package

```bash
cd crp-scan/vscode-extension

# Install dependencies
npm install

# Compile TypeScript
npm run compile

# Package (creates .vsix file)
vsce package

# The output will be: crp-scan-0.2.0.vsix
```

## Publish

```bash
# Login with your PAT
vsce login autocyber-ai
# Paste your PAT when prompted

# Publish
vsce publish

# Or publish a specific version
vsce publish 0.2.0
```

## Verify

1. Visit https://marketplace.visualstudio.com/items?itemName=autocyber-ai.crp-scan
2. Install in VS Code: Extensions → Search "CRP Scan" → Install
3. Test: Open a Python file with `openai.chat.completions.create()` → Run `CRP: Scan Workspace`

## Updates

```bash
# Bump version in package.json
# Update CHANGELOG.md
vsce publish
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `vsce: command not found` | `npm install -g @vscode/vsce` |
| `Invalid publisher` | Create publisher at https://marketplace.visualstudio.com/manage first |
| `Token expired` | Generate new PAT in Azure DevOps |
| `Package too large` | Add files to `.vscodeignore` |
