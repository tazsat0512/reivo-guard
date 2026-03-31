#!/usr/bin/env node

// When installed via npm, import from 'reivo-guard'.
// For local development, resolve from ../ts/dist/index.js.
import { existsSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const localDist = new URL('../ts/dist/index.js', import.meta.url);
const pkg = existsSync(localDist) ? localDist : 'reivo-guard';
const {
  Guard,
  checkBudget,
  detectLoopByHash,
  getDegradationLevel,
  createMemoryStore,
  getBudgetState,
  addCost,
  detectLoopByCosine,
  assessQuality,
  initEwmaState,
  updateEwma,
  detectAnomaly,
  estimateCost,
} = await import(pkg);

const RESET = '\x1b[0m';
const BOLD = '\x1b[1m';
const GREEN = '\x1b[32m';
const RED = '\x1b[31m';
const YELLOW = '\x1b[33m';
const CYAN = '\x1b[36m';
const DIM = '\x1b[2m';

function ok(msg) { console.log(`  ${GREEN}✓${RESET} ${msg}`); }
function fail(msg) { console.log(`  ${RED}✗${RESET} ${msg}`); }
function info(msg) { console.log(`  ${DIM}${msg}${RESET}`); }
function header(msg) { console.log(`\n${BOLD}${CYAN}▸ ${msg}${RESET}`); }

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

console.log(`
${BOLD}╔══════════════════════════════════════════════════════╗
║           ${CYAN}reivo-guard${RESET}${BOLD} interactive demo              ║
║  Open-source guardrails that auto-kill runaway agents ║
╚══════════════════════════════════════════════════════╝${RESET}
`);

// ── 1. Budget Enforcement ──────────────────────────────
header('Budget Enforcement');
info('Simulating an agent spending against a $10 budget...\n');

const store = createMemoryStore();
const userId = 'demo-user';
const limit = 10.0;

const costs = [2.5, 3.0, 2.0, 1.5, 1.5, 0.8];
for (const cost of costs) {
  await sleep(150);
  const state = await addCost(store, userId, cost);
  const status = checkBudget(state, limit);
  const bar = renderBar(state.usedUsd, limit);
  if (status.blocked) {
    fail(`Request $${cost.toFixed(2)} → ${RED}BLOCKED${RESET}  ${bar}  $${state.usedUsd.toFixed(2)}/$${limit.toFixed(2)}`);
  } else {
    ok(`Request $${cost.toFixed(2)} → allowed   ${bar}  $${state.usedUsd.toFixed(2)}/$${limit.toFixed(2)}`);
  }
}

// ── 2. Graceful Degradation ────────────────────────────
header('Graceful Degradation');
info('Progressive restrictions as budget usage increases...\n');

const ratios = [0.5, 0.75, 0.85, 0.96, 1.0];
for (const ratio of ratios) {
  await sleep(150);
  const used = ratio * 100;
  const deg = getDegradationLevel(used, 100);
  const color = deg.level === 'normal' ? GREEN : deg.level === 'blocked' ? RED : YELLOW;
  ok(`${(ratio * 100).toFixed(0)}% used → ${color}${deg.level}${RESET}  ${DIM}(aggressive=${deg.forceAggressiveRouting}, blockNew=${deg.blockNewSessions}, blockAll=${deg.blockAll})${RESET}`);
}

// ── 3. Loop Detection (Hash) ───────────────────────────
header('Loop Detection (Hash Match)');
info('Agent sends the same prompt repeatedly...\n');

const hashes = [];
const prompts = [
  'What is Python?',
  'Explain decorators',
  'What is Python?',
  'What is Python?',
  'What is Python?',
  'What is Python?',
];

for (const p of prompts) {
  await sleep(150);
  const h = simpleHash(p);
  const result = detectLoopByHash(hashes, h);
  hashes.push(h);
  if (result.isLoop) {
    fail(`"${p}" → ${RED}LOOP DETECTED${RESET} (${result.matchCount} matches)`);
  } else {
    ok(`"${p}" → ok (${result.matchCount}/5 matches)`);
  }
}

// ── 4. Loop Detection (Semantic) ───────────────────────
header('Loop Detection (TF-IDF Cosine Similarity)');
info('Detects semantically similar prompts, not just identical ones...\n');

const semanticPrompts = [
  'How do I sort a list in Python?',
  'What is the best way to sort a Python list?',
  'Can you show me Python list sorting?',
  'Tell me about sorting lists with Python please',
  'Python list sort method explanation',
];

const prevTexts = [];
for (const p of semanticPrompts) {
  await sleep(150);
  if (prevTexts.length >= 2) {
    const result = detectLoopByCosine(prevTexts, p);
    if (result.isLoop) {
      fail(`"${p}" → ${RED}LOOP${RESET} (similarity=${result.similarity?.toFixed(3)})`);
    } else {
      ok(`"${p}" → ok (similarity=${result.similarity?.toFixed(3) ?? 'n/a'})`);
    }
  } else {
    ok(`"${p}" → ok (building history...)`);
  }
  prevTexts.push(p);
}

// ── 5. Anomaly Detection ───────────────────────────────
header('Anomaly Detection (EWMA)');
info('Detecting unusual spikes in token consumption...\n');

let ewma = initEwmaState();
// Pre-train EWMA with 50 stable samples to build tight variance
for (let i = 0; i < 50; i++) {
  ewma = updateEwma(ewma, 100 + (i % 5) - 2); // 98-102 range
}
const tokenRates = [101, 99, 102, 98, 100, 800, 101];
for (const rate of tokenRates) {
  await sleep(150);
  const anomaly = detectAnomaly(ewma, rate);
  ewma = updateEwma(ewma, rate);
  if (anomaly.isAnomaly) {
    fail(`${rate} tokens/req → ${RED}ANOMALY${RESET} (z-score=${anomaly.zScore.toFixed(2)})`);
  } else {
    ok(`${rate} tokens/req → normal (z-score=${anomaly.zScore.toFixed(2)})`);
  }
}

// ── 6. Guard Class (Unified API) ──────────────────────
header('Guard Class (before/after pattern)');
info('The simplest way to use reivo-guard — wraps all checks in one class.\n');

{
  const guard = new Guard({
    budgetLimitUsd: 0.50,
    loopThreshold: 3,
    enableAnomalyDetection: true,
    anomalyWarmup: 5,
  });

  // Simulate agent conversation
  const conversation = [
    { messages: [{ role: 'user', content: 'Summarize this article' }], cost: 0.08, tokens: 150 },
    { messages: [{ role: 'user', content: 'Now translate it to French' }], cost: 0.12, tokens: 200 },
    { messages: [{ role: 'user', content: 'Create a bullet-point version' }], cost: 0.10, tokens: 180 },
    { messages: [{ role: 'user', content: 'Summarize this article' }], cost: 0.08, tokens: 150 },
    { messages: [{ role: 'user', content: 'Summarize this article' }], cost: 0.08, tokens: 150 },
    { messages: [{ role: 'user', content: 'One more expensive call' }], cost: 0.25, tokens: 500 },
  ];

  for (const turn of conversation) {
    await sleep(150);
    const decision = guard.before({ messages: turn.messages, tokenCount: turn.tokens });
    const prompt = turn.messages[0].content;
    if (!decision.allowed) {
      fail(`"${prompt}" → ${RED}BLOCKED${RESET} ${DIM}(${decision.reason})${RESET}`);
    } else {
      guard.after({ costUsd: turn.cost });
      const deg = decision.degradationLevel ?? 'none';
      const remaining = decision.budgetRemainingUsd?.toFixed(2) ?? '∞';
      ok(`"${prompt}" → $${turn.cost.toFixed(2)} ${DIM}(remaining: $${remaining}, level: ${deg})${RESET}`);
    }
  }

  console.log('');
  const s = guard.stats;
  info(`Stats: ${s.totalRequests} requests, $${s.totalCostUsd.toFixed(2)} spent, ${s.blockedRequests} blocked`);
}

// ── 7. Cost Estimation ────────────────────────────────
header('Cost Estimation');
info('Built-in pricing table for 20+ models.\n');

const models = [
  { model: 'gpt-4o', input: 1000, output: 500 },
  { model: 'gpt-4o-mini', input: 1000, output: 500 },
  { model: 'claude-sonnet-4-20250514', input: 1000, output: 500 },
  { model: 'gemini-2.0-flash', input: 1000, output: 500 },
];

for (const m of models) {
  await sleep(100);
  const cost = estimateCost(m.model, m.input, m.output);
  ok(`${m.model}: ${m.input} in + ${m.output} out = ${BOLD}$${cost.toFixed(6)}${RESET}`);
}

// ── 8. Performance ─────────────────────────────────────
header('Performance');

const BENCH_N = 100_000;
const benchState = { usedUsd: 45, blockedUntil: null, lastAlertThreshold: 0 };

let start = performance.now();
for (let i = 0; i < BENCH_N; i++) checkBudget(benchState, 50);
const nsBudget = ((performance.now() - start) * 1e6) / BENCH_N;

const benchHashes = Array.from({ length: 20 }, (_, i) => `h${i}`);
start = performance.now();
for (let i = 0; i < BENCH_N; i++) detectLoopByHash(benchHashes, `h${i % 100}`);
const nsLoop = ((performance.now() - start) * 1e6) / BENCH_N;

start = performance.now();
for (let i = 0; i < BENCH_N; i++) getDegradationLevel(42, 50);
const nsDeg = ((performance.now() - start) * 1e6) / BENCH_N;

console.log('');
ok(`checkBudget()         ${BOLD}${nsBudget.toFixed(0)} ns${RESET} per call`);
ok(`detectLoopByHash()    ${BOLD}${nsLoop.toFixed(0)} ns${RESET} per call`);
ok(`getDegradationLevel() ${BOLD}${nsDeg.toFixed(0)} ns${RESET} per call`);
info(`(${BENCH_N.toLocaleString()} iterations each)`);

// ── Summary ────────────────────────────────────────────
console.log(`
${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}

  ${BOLD}Install:${RESET}  npm install reivo-guard
            pip install reivo-guard

  ${BOLD}GitHub:${RESET}   https://github.com/tazsat0512/reivo-guard
  ${BOLD}npm:${RESET}      https://www.npmjs.com/package/reivo-guard
  ${BOLD}PyPI:${RESET}     https://pypi.org/project/reivo-guard/

${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}
`);

// ── Helpers ────────────────────────────────────────────

function renderBar(used, limit) {
  const width = 20;
  const filled = Math.min(width, Math.round((used / limit) * width));
  const empty = width - filled;
  const ratio = used / limit;
  const color = ratio >= 1 ? RED : ratio >= 0.8 ? YELLOW : GREEN;
  return `${DIM}[${RESET}${color}${'█'.repeat(filled)}${RESET}${DIM}${'░'.repeat(empty)}]${RESET}`;
}

function simpleHash(text) {
  let hash = 0;
  for (let i = 0; i < text.length; i++) {
    hash = ((hash << 5) - hash + text.charCodeAt(i)) | 0;
  }
  return hash.toString(16);
}
