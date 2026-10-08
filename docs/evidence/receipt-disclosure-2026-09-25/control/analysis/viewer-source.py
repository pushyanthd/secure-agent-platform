"""Portable report viewer: no network dependencies or untrusted HTML insertion."""

import base64
import hashlib
import json
from typing import Any

STYLE = """
:root { color-scheme: light; font: 16px/1.5 system-ui, sans-serif; color: #192c43;
  background: #f3f5f8; }
* { box-sizing: border-box; }
body { margin: 0; }
header { background: #13283f; color: #fff; padding: 2.4rem max(4vw, 1rem); }
header p { max-width: 75ch; color: #cedae7; }
h1 { margin: .3rem 0; font-size: clamp(1.6rem, 3vw, 2.4rem); letter-spacing: -.03em; }
h2 { font-size: 1.2rem; margin-top: 0; }
h3 { font-size: 1rem; }
.eyebrow { text-transform: uppercase; letter-spacing: .1em; font-size: .8rem; }
main { max-width: 1440px; margin: auto; padding: 1.5rem max(3vw, 1rem); }
.card { padding: 1.3rem; background: white; border: 1px solid #dbe2eb;
  border-radius: .7rem; margin-bottom: 1.4rem; }
.notice { border-left: 4px solid #d9a027; }
table { border-collapse: collapse; width: 100%; text-align: left; }
th, td { padding: .7rem; border-bottom: 1px solid #e4e9f0; }
th { font-size: .85rem; color: #53687e; }
.scroll { overflow-x: auto; }
.controls { display: flex; flex-wrap: wrap; gap: 1rem; margin: 1rem 0; }
label { display: flex; flex-direction: column; gap: .3rem; font-weight: 600; }
select { padding: .6rem; border: 1px solid #aebccc; border-radius: .35rem;
  background: white; color: #192c43; font: inherit; max-width: 100%; }
select:focus-visible, summary:focus-visible { outline: 3px solid #358cd8; outline-offset: 3px; }
.comparison { display: grid; grid-template-columns: 1fr 1fr; gap: 1.4rem; align-items: start; }
.comparison > article { min-width: 0; }
.pills { display: flex; flex-wrap: wrap; gap: .5rem; margin: .7rem 0; }
.pill { font-size: .8rem; padding: .25rem .65rem; border-radius: 1rem; background: #eaf0f6; }
.good { color: #145d3d; background: #e6f4eb; }
.bad { color: #942f37; background: #fbeaec; }
.review { color: #805809; background: #fff2d4; }
.muted { color: #53687e; font-size: .9rem; }
.step { border-left: 3px solid #9fb6ce; padding: .3rem 0 .5rem 1rem; margin: 1rem 0; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; font: .82rem/1.55 ui-monospace, monospace;
  padding: .8rem; background: #f4f6f9; border-radius: .35rem; }
summary { cursor: pointer; font-weight: 600; padding: .4rem 0; }
.task { white-space: pre-wrap; overflow-wrap: anywhere; }
footer { color: #53687e; font-size: .85rem; padding: 1rem 0; }
@media (max-width: 800px) { .comparison { grid-template-columns: 1fr; } }
@media print { header { background: white; color: black; } header p { color: black; }
  .controls { display: none; } .comparison { display: block; } .card { break-inside: avoid; } }
"""

SCRIPT = """
"use strict";
const data = JSON.parse(document.getElementById("evidence").textContent);
const $ = id => document.getElementById(id);
function node(tag, text, cls) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = String(text);
  if (cls) el.className = cls;
  return el;
}
function detail(parent, title, value) {
  const el = node("details");
  el.append(node("summary", title), node("pre", JSON.stringify(value, null, 2)));
  parent.append(el);
}
function ratio(metric) { return metric.numerator + "/" + metric.denominator; }
function select(id, values, chosen) {
  for (const value of values) {
    const option = node("option", value);
    option.value = value;
    $(id).append(option);
  }
  $(id).value = chosen;
  $(id).addEventListener("change", render);
}
function attackId(row) { return row.attack_id ?? (row.attacked ? "primary" : null); }
function episode(container, profile, task, attack) {
  container.replaceChildren();
  const row = data.episodes.find(r => r.task_id === task && r.profile === profile
    && attackId(r) === attack);
  container.append(node("h2", profile));
  if (!row) { container.append(node("p", "No scheduled result.", "bad")); return; }
  const pills = node("div", undefined, "pills");
  pills.append(node("span", row.status, "pill"));
  pills.append(node("span", row.grade.task_success ? "Task passed" : "Task failed",
    "pill " + (row.grade.task_success ? "good" : "bad")));
  if (attack !== null) pills.append(node("span", row.grade.attack_success ? "Attacker win observed"
    : "No attacker win observed", "pill " + (row.grade.attack_success ? "bad" : "good")));
  container.append(pills);
  container.append(node("p", (row.elapsed_seconds === null ? "Duration unknown"
    : row.elapsed_seconds.toFixed(2) + " s") + " · " + row.model_calls
    + " model calls · " + row.generated_tokens + " generated tokens", "muted"));
  container.append(node("p", "Episode " + row.episode_id + " · " + row.reason, "muted"));
  container.append(node("h3", "Tool timeline"));
  if (!row.trace.length) container.append(
    node("p", "No recorded tool execution decisions.", "muted"));
  row.trace.forEach((step, index) => {
    const block = node("section", undefined, "step");
    const decision = step.execution.decision;
    block.append(node("h3", (index + 1) + ". " + step.action.tool));
    block.append(node("span", decision.outcome + " · " + decision.reason,
      "pill " + (decision.outcome === "ALLOW" ? "good"
      : decision.outcome === "DENY" ? "bad" : "review")));
    block.append(node("pre", JSON.stringify(step.action.arguments, null, 2)));
    if (step.simulated_review) block.append(node("p", "Simulated exact-action review: "
      + (step.simulated_review.approved ? "approved" : "rejected"), "pill review"));
    detail(block, "Tool result (untrusted content)", step.execution.result);
    container.append(block);
  });
  const receipt = row.response_decision?.reason === "VERIFIED_EFFECT_RECEIPT";
  container.append(node("h3", receipt ? "Final response (verified effect receipt)"
    : "Final response (model claim)"));
  if (row.response_decision) {
    const decision = row.response_decision;
    container.append(node("p", decision.outcome + " · " + decision.reason,
      "pill " + (decision.outcome === "ALLOW" ? "good" : "bad")));
    detail(container, "Response authorization", decision);
  }
  container.append(node("pre", row.final_response || "No final response.", "final-output"));
  detail(container, "Independent state grade", row.grade);
}
function render() {
  const task = $("task").value;
  $("task-text").textContent = data.tasks[task];
  const attacked = $("input").value === "attacked";
  const attacks = [...new Set(data.episodes.filter(r => r.task_id === task && r.attacked)
    .map(attackId))];
  const previous = $("attack").value;
  $("attack").replaceChildren();
  for (const id of attacks) {
    const option = node("option", id); option.value = id; $("attack").append(option);
  }
  $("attack").value = attacks.includes(previous) ? previous : attacks[0];
  $("attack").disabled = !attacked;
  const attack = attacked ? $("attack").value : null;
  episode($("left"), $("left-profile").value, task, attack);
  episode($("right"), $("right-profile").value, task, attack);
}
$("mode").textContent = data.analysis.mode === "fresh_local_inference"
  ? "Fresh local inference · development evidence" : "Authored replay · zero model trials";
$("accounting").textContent = data.analysis.scheduled_episodes
  + " scheduled episodes accounted for · "
  + data.analysis.task_clusters + " authored task clusters · not a release benchmark";
const profiles = Object.keys(data.analysis.profiles);
for (const profile of profiles) {
  const values = data.analysis.profiles[profile];
  const tr = node("tr");
  tr.append(node("td", profile));
  for (const metric of ["clean_utility", "attacked_utility", "observed_attack_success",
    "worst_case_attack_success"]) tr.append(node("td", ratio(values[metric])));
  tr.append(node("td", JSON.stringify(values.statuses)));
  $("metrics").append(tr);
}
const tasks = Object.keys(data.tasks);
select("task", tasks, tasks[0]);
select("left-profile", profiles, profiles[0]);
select("right-profile", profiles, profiles.includes("defended") ? "defended" : profiles.at(-1));
select("input", ["clean", "attacked"], "attacked");
$("attack").addEventListener("change", render);
for (const limit of data.analysis.limits) $("limits").append(node("li", limit));
detail($("provenance"), "Experiment versions and budgets", data.analysis.provenance);
render();
"""

TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none';
script-src 'sha256-__SCRIPT_HASH__'; style-src 'sha256-__STYLE_HASH__';
base-uri 'none'; form-action 'none'; connect-src 'none'; object-src 'none'">
<title>AgentGuard · Paired development evidence</title>
<style>__STYLE__</style></head><body>
<header><div class="eyebrow">AgentGuard / Evidence explorer</div>
<h1>Useful work. Explicit boundaries. Inspectable results.</h1>
<p id="mode"></p><p id="accounting"></p></header>
<main><noscript><p class="card notice">Enable JavaScript to inspect this local report,
or read the accompanying analysis.md and analysis.json files.</p></noscript>
<section class="card scroll" aria-label="Evaluation totals"><h2>Utility and attack outcomes</h2>
<table><thead><tr><th>Profile</th><th>Clean utility</th><th>Attacked utility</th>
<th>Observed wins</th><th>Worst-case wins</th><th>Episode statuses</th></tr></thead>
<tbody id="metrics"></tbody></table>
<p class="muted">Counts include every scheduled episode. A completed model response
does not establish task success. Worst-case wins include unresolved attacked episodes.</p></section>
<section class="card"><h2>Compare the same task and input</h2>
<div class="controls"><label>Task<select id="task"></select></label>
<label>Input<select id="input"></select></label>
<label>Attack variant<select id="attack"></select></label>
<label>Left profile<select id="left-profile"></select></label>
<label>Right profile<select id="right-profile"></select></label></div>
<p id="task-text" class="task"></p></section>
<div class="comparison" aria-live="polite"><article id="left" class="card"></article>
<article id="right" class="card"></article></div>
<section class="card notice"><h2>Scope and limits</h2><ul id="limits"></ul>
<div id="provenance"></div></section>
<footer>Standalone local report · No services, credentials, or external assets required.
This is an evidence viewer; it cannot execute tools or approve actions.</footer></main>
<script id="evidence" type="application/json">__DATA__</script>
<script>__SCRIPT__</script></body></html>
"""


def csp_hash(value: str) -> str:
    return base64.b64encode(hashlib.sha256(value.encode()).digest()).decode()


def render_viewer(report: dict[str, Any], analysis: dict[str, Any], tasks: dict[str, str]) -> str:
    payload = json.dumps(
        {"analysis": analysis, "tasks": tasks, "episodes": report["episodes"]},
        ensure_ascii=True,
    )
    # JSON inside a script element is still parsed by the HTML tokenizer. Escape
    # angle brackets so document text cannot close that element or add active HTML.
    payload = payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    # Insert untrusted data last, so template-looking document text stays literal.
    return (
        TEMPLATE.replace("__SCRIPT_HASH__", csp_hash(SCRIPT))
        .replace("__STYLE_HASH__", csp_hash(STYLE))
        .replace("__STYLE__", STYLE)
        .replace("__SCRIPT__", SCRIPT)
        .replace("__DATA__", payload)
    )
