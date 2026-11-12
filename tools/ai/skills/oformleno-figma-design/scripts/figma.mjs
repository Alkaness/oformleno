#!/usr/bin/env node
// Read-only MCP diagnostics and an idempotent launcher for the selected relay.
import { access, mkdir, open, writeFile } from 'node:fs/promises';
import { constants } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';

const project = resolve(dirname(fileURLToPath(import.meta.url)), '../../../../..');
const checkout = process.env.OFORMLENO_FIGMA_REPO || '/home/eugen/claude-talk-to-figma-mcp';
const bun = process.env.OFORMLENO_FIGMA_BUN || '/home/eugen/.bun/bin/bun';
const endpoint = 'http://127.0.0.1:3055/status';
const command = process.argv[2];
const print = value => process.stdout.write(JSON.stringify(value, null, 2) + '\n');

async function status() {
  try {
    const response = await fetch(endpoint, { signal: AbortSignal.timeout(3000) });
    if (!response.ok) throw new Error(`Relay status returned HTTP ${response.status}.`);
    const data = await response.json();
    if (data.status !== 'running' || !Number.isInteger(data.queue?.pluginCount)) {
      throw new Error('Port 3055 is not returning the expected Talk to Figma status.');
    }
    return {
      endpoint,
      running: true,
      pluginCount: data.queue.pluginCount,
      agentCount: data.queue.agentCount,
      pendingRequests: data.queue.pendingRequests,
    };
  } catch (error) {
    if (error.cause?.code === 'ECONNREFUSED') return { endpoint, running: false };
    throw error;
  }
}

async function startRelay() {
  const current = await status();
  if (current.running) return { ...current, reused: true };
  await access(bun, constants.X_OK);
  await access(join(checkout, 'dist/socket.js'));
  const state = join(project, 'tmp/figma-mcp');
  await mkdir(state, { recursive: true, mode: 0o700 });
  const logPath = join(state, 'relay.log');
  const log = await open(logPath, 'a', 0o600);
  let failure;
  let child;
  try {
    child = spawn(bun, [join(checkout, 'dist/socket.js'), '--port=3055'], {
      cwd: project,
      env: { ...process.env, FIGMA_SOCKET_HOST: '127.0.0.1', LOG_LEVEL: 'warn' },
      detached: true,
      stdio: ['ignore', log.fd, log.fd],
    });
    child.once('error', error => { failure = error; });
    child.unref();
  } finally {
    await log.close();
  }
  for (let attempt = 0; attempt < 30; attempt++) {
    await delay(200);
    if (failure) throw failure;
    const result = await status();
    if (result.running) {
      if (child.pid) await writeFile(join(state, 'relay.pid'), `${child.pid}\n`, { mode: 0o600 });
      return { ...result, reused: false, pid: child.pid, logPath };
    }
  }
  throw new Error(`Relay did not become healthy; inspect ${logPath}. No existing process was stopped.`);
}

async function withClient(action) {
  const require = createRequire(join(checkout, 'package.json'));
  const { Client } = require('@modelcontextprotocol/sdk/client/index.js');
  const { StdioClientTransport } = require('@modelcontextprotocol/sdk/client/stdio.js');
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [join(checkout, 'dist/talk_to_figma_mcp/server.js')],
    cwd: project,
    env: { ...process.env, LOG_LEVEL: 'error' },
    stderr: 'pipe',
  });
  const client = new Client({ name: 'oformleno-figma-diagnostics', version: '1.0.0' });
  try {
    await client.connect(transport, { timeout: 15000 });
    // Drain logs without printing design payloads or token-bearing environment values.
    transport.stderr?.resume();
    return await action(client);
  } finally {
    await client.close();
  }
}

async function toolList(client) {
  const tools = [];
  let cursor;
  do {
    const page = await client.listTools(cursor ? { cursor } : undefined);
    tools.push(...page.tools);
    cursor = page.nextCursor;
  } while (cursor);
  return tools;
}

async function main() {
  if (Number(process.versions.node.split('.')[0]) < 22) throw new Error('Use Node 22+ for these helpers and Taste Skill.');
  if (command === 'status') {
    const result = await status();
    print(result);
    if (!result.running) process.exitCode = 2;
    return;
  }
  if (command === 'relay-start') {
    print(await startRelay());
    return;
  }
  if (!['catalog', 'schema', 'probe'].includes(command)) {
    throw new Error('Usage: figma.mjs status | relay-start | catalog | schema TOOL | probe');
  }
  await access(join(checkout, 'dist/talk_to_figma_mcp/server.js'));
  await withClient(async client => {
    const tools = await toolList(client);
    if (command === 'schema') {
      const tool = tools.find(tool => tool.name === process.argv[3]);
      if (!tool) throw new Error('Tool is not registered in this local build; inspect catalog.');
      print(tool);
      return;
    }
    const [prompts, resources] = await Promise.all([client.listPrompts(), client.listResources()]);
    const summary = {
      checkout,
      server: client.getServerVersion(),
      toolCount: tools.length,
      prompts: prompts.prompts.map(prompt => prompt.name),
      resources: resources.resources.map(resource => resource.uri),
    };
    if (command === 'catalog') {
      print({ ...summary, tools: tools.map(tool => tool.name) });
      return;
    }
    const relay = await status();
    const live = [];
    if (relay.running && relay.pluginCount === 1) {
      for (const name of ['get_document_info', 'get_pages', 'get_selection']) {
        const result = await client.callTool({ name, arguments: {} }, undefined, { timeout: 20000 });
        if (result.isError) throw new Error(`Live ${name} read failed. Inspect the plugin connection; no design was changed.`);
        live.push(name);
      }
    }
    print({
      ...summary,
      relay,
      liveReadsVerified: live,
      designMutations: 0,
      ...(!live.length ? { next: relay.running && relay.pluginCount > 1
        ? 'Several plugins are connected; choose the target file and use join_channel in the same MCP session.'
        : 'Start the relay if needed. Open Talk to Figma in the intended Figma file and click Connect.' } : {}),
    });
    if (!live.length) process.exitCode = 2;
  });
}

main().catch(error => {
  // Do not dump stack traces, environment variables or the MCP server stderr.
  process.stderr.write(`Figma setup: ${error.message}\n`);
  process.exitCode = 1;
});
