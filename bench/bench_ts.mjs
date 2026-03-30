import {
  checkBudget,
  detectLoopByHash,
  getDegradationLevel,
  createMemoryStore,
  getBudgetState,
  addCost,
} from 'reivo-guard';

const ITERATIONS = 100_000;

// Benchmark checkBudget (pure function)
const state = { usedUsd: 45.0, blockedUntil: null, lastAlertThreshold: 0 };
let start = performance.now();
for (let i = 0; i < ITERATIONS; i++) {
  checkBudget(state, 50.0);
}
const elapsedBudget = ((performance.now() - start) * 1_000_000) / ITERATIONS;

// Benchmark detectLoopByHash
const hashes = Array.from({ length: 20 }, (_, i) => `hash_${i}`);
start = performance.now();
for (let i = 0; i < ITERATIONS; i++) {
  detectLoopByHash(hashes, `hash_${i % 100}`);
}
const elapsedLoop = ((performance.now() - start) * 1_000_000) / ITERATIONS;

// Benchmark getDegradationLevel
start = performance.now();
for (let i = 0; i < ITERATIONS; i++) {
  getDegradationLevel(42 + (i % 10), 50);
}
const elapsedDeg = ((performance.now() - start) * 1_000_000) / ITERATIONS;

// Benchmark KV round-trip (in-memory store)
const store = createMemoryStore();
start = performance.now();
for (let i = 0; i < 10_000; i++) {
  await addCost(store, 'user1', 0.001);
}
const elapsedKV = ((performance.now() - start) * 1_000_000) / 10_000;

console.log(`checkBudget()        : ${elapsedBudget.toFixed(0)} ns (${(elapsedBudget/1000).toFixed(1)} µs)`);
console.log(`detectLoopByHash()   : ${elapsedLoop.toFixed(0)} ns (${(elapsedLoop/1000).toFixed(1)} µs)`);
console.log(`getDegradationLevel(): ${elapsedDeg.toFixed(0)} ns (${(elapsedDeg/1000).toFixed(1)} µs)`);
console.log(`addCost() + KV r/w   : ${elapsedKV.toFixed(0)} ns (${(elapsedKV/1000).toFixed(1)} µs)`);
console.log(`iterations           : ${ITERATIONS.toLocaleString()}`);
