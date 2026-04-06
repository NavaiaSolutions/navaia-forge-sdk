/**
 * NavaiaForge SDK — Monitor Tasks and Token Usage
 *
 * Demonstrates listing tasks, checking statuses, and querying
 * observability metrics for a workforce.
 */

import { NavaiaForge } from "@navaia/forge";

const nf = new NavaiaForge({
  apiKey: "nf_your_api_key",
  baseUrl: "https://api.navaia.com",
});

const WORKFORCE_ID = "wf_your_workforce_id";

// ── 1. List all tasks ──────────────────────────────────────

const allTasks = await nf.tasks.list(WORKFORCE_ID);
console.log(`Total tasks: ${allTasks.length}\n`);

const statusIcons: Record<string, string> = {
  done: "[OK]",
  in_progress: "[..]",
  pending: "[--]",
  failed: "[!!]",
  rejected: "[XX]",
};

for (const task of allTasks) {
  const icon = statusIcons[task.status] ?? "[??]";
  console.log(`  ${icon} ${task.title}`);
  console.log(`       ID: ${task.id}`);
  console.log(`       Status: ${task.status}`);
  console.log(`       Created: ${task.created_at}`);
  if (task.completed_at) {
    console.log(`       Completed: ${task.completed_at}`);
  }
  console.log();
}

// ── 2. Filter by status ───────────────────────────────────

const inProgress = await nf.tasks.list(WORKFORCE_ID, "in_progress");
const failed = await nf.tasks.list(WORKFORCE_ID, "failed");
console.log(`In progress: ${inProgress.length}`);
console.log(`Failed: ${failed.length}`);

// ── 3. Inspect a specific task ─────────────────────────────

if (allTasks.length > 0) {
  const latest = allTasks[0]!;
  const detail = await nf.tasks.get(latest.id);

  console.log(`\nLatest task detail:`);
  console.log(`  Title:       ${detail.title}`);
  console.log(`  Description: ${detail.description}`);
  console.log(`  Status:      ${detail.status}`);
  console.log(`  Agent:       ${detail.agent_id ?? "unassigned"}`);
  console.log(`  Priority:    ${detail.priority}`);
  if (detail.result) {
    console.log(`  Result:      ${detail.result.slice(0, 200)}...`);
  }
  if (detail.error) {
    console.log(`  Error:       ${detail.error}`);
  }
}

// ── 4. Observability — metrics summary ─────────────────────

const metrics = await nf.observability.summary(WORKFORCE_ID);
console.log(`\nMetrics Summary:`);
console.log(`  Total tasks:       ${metrics.total_tasks}`);
console.log(`  Completed:         ${metrics.completed_tasks}`);
console.log(`  Failed:            ${metrics.failed_tasks}`);
console.log(`  Active agents:     ${metrics.active_agents}`);
console.log(`  Tokens today:      ${metrics.total_tokens_today.toLocaleString()}`);
console.log(`  Cost today:        $${metrics.cost_today.toFixed(4)}`);

// ── 5. Token usage breakdown ──────────────────────────────

const tokenHistory = await nf.observability.tokenUsage(WORKFORCE_ID, 7);
console.log(`\nToken usage (last 7 days): ${tokenHistory.length} records`);

const totalInput = tokenHistory.reduce((sum, r) => sum + r.input_tokens, 0);
const totalOutput = tokenHistory.reduce((sum, r) => sum + r.output_tokens, 0);
const totalCost = tokenHistory.reduce((sum, r) => sum + r.cost_weighted, 0);

console.log(`  Input tokens:  ${totalInput.toLocaleString()}`);
console.log(`  Output tokens: ${totalOutput.toLocaleString()}`);
console.log(`  Total cost:    $${totalCost.toFixed(4)}`);

// ── 6. Retry failed tasks ─────────────────────────────────

if (failed.length > 0) {
  console.log(`\nRetrying ${failed.length} failed task(s)...`);
  for (const task of failed) {
    const retried = await nf.tasks.retry(task.id);
    console.log(`  Retried: ${retried.title} -> ${retried.status}`);
  }
}
