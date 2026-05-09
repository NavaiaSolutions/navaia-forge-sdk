/**
 * NavaiaForge SDK — Quickstart Example
 *
 * Demonstrates creating a workforce, adding an agent, submitting a task,
 * and waiting for the result.
 */

import { NavaiaForge } from "@navaia/forge";

const nf = new NavaiaForge({
  apiKey: process.env.NAVAIA_FORGE_API_KEY ?? "nf_your_api_key",
  baseUrl: process.env.NAVAIA_FORGE_BASE_URL ?? "http://localhost:8000",
});

// Create a workforce
const workforce = await nf.workforces.create({
  name: "My First Workforce",
  description: "Testing NavaiaForge",
});
console.log(`Workforce created: ${workforce.id}`);

// Add an agent
const agent = await nf.agents.create({
  workforce_id: workforce.id,
  name: "Researcher",
  role: "research",
  instructions: "Find and summarize information on any given topic.",
  model_provider: "anthropic",
  model_name: "sonnet",
});
console.log(`Agent created: ${agent.id}`);

// Submit a task
const task = await nf.tasks.create({
  workforce_id: workforce.id,
  title: "Research AI trends in 2025",
  description: "Provide a comprehensive summary of the top AI trends.",
  agent_id: agent.id,
});
console.log(`Task submitted: ${task.id}`);

// Wait for completion
const result = await nf.tasks.waitForCompletion(task.id, {
  timeout: 300_000,
});
console.log(`Status: ${result.status}`);
console.log(`Result: ${result.result}`);
