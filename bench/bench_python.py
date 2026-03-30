"""Benchmark reivo-guard overhead."""

import time
from reivo_guard import Guard

ITERATIONS = 100_000

guard = Guard(budget_limit_usd=1_000_000.0, loop_threshold=1000)

messages = [{"role": "user", "content": f"message {i}"} for i in range(3)]

# Warm up
for _ in range(100):
    guard.before(messages=messages)
    guard.after(cost_usd=0.001)

guard.reset()

# Benchmark before()
start = time.perf_counter_ns()
for i in range(ITERATIONS):
    guard.before(messages=[{"role": "user", "content": f"msg {i}"}])
elapsed_before = (time.perf_counter_ns() - start) / ITERATIONS

# Benchmark after()
start = time.perf_counter_ns()
for i in range(ITERATIONS):
    guard.after(cost_usd=0.001)
elapsed_after = (time.perf_counter_ns() - start) / ITERATIONS

# Benchmark after() with token estimation
guard2 = Guard(budget_limit_usd=1_000_000.0)
start = time.perf_counter_ns()
for i in range(ITERATIONS):
    guard2.after(model="gpt-4o-mini", input_tokens=500, output_tokens=200)
elapsed_estimate = (time.perf_counter_ns() - start) / ITERATIONS

print(f"guard.before()  : {elapsed_before:.0f} ns ({elapsed_before/1000:.1f} µs)")
print(f"guard.after()   : {elapsed_after:.0f} ns ({elapsed_after/1000:.1f} µs)")
print(f"guard.after(est): {elapsed_estimate:.0f} ns ({elapsed_estimate/1000:.1f} µs)")
print(f"iterations      : {ITERATIONS:,}")
