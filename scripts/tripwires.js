'use strict';

// Tripwire scanner — invoked by .github/workflows/tripwires.yml through
// actions/github-script. The eight locked tripwires (design #59/#69):
//   P0 -> #ops  (diagnose + fix-PR): red-main, panic, demo-freeze
//   P1 -> #feed (notify):            stuck-pr, stale-claim, collision,
//                                    deadlock, budget
// Gate-health (audit C1: review check absent/queued too long) is folded
// into stuck-pr. Every check fails open — a broken tripwire must never
// block work — and conditions re-nag on each 10-min pass until fixed.

const THRESHOLDS = {
  stuckPrMin: 30, // green-but-unmerged nag
  botStaleMin: 15, // gate-health: review check absent/queued (audit C1)
  staleClaimMin: 90, // assigned issue with no activity
  reviewRunsPerHour: 10, // budget proxy: review-bot burn rate
};

const WIRE_SEVERITY = {
  'red-main': 'P0',
  panic: 'P0',
  'demo-freeze': 'P0',
  'stuck-pr': 'P1',
  'stale-claim': 'P1',
  collision: 'P1',
  deadlock: 'P1',
  budget: 'P1',
};

const DRILL_SAMPLES = {
  'red-main': 'ci: failure on main (sample run) — merge freeze until green',
  panic: 'needs-human applied on #999: "sample panic — human decision required"',
  'demo-freeze': 'push to main AFTER demo freeze (1 commit) — revert or break-glass justify',
  'stuck-pr': 'PR #999 green but unmerged 45m / review check queued 20m (gate-health)',
  'stale-claim': 'issue #999 assigned to sample-seat, untouched 120m',
  collision: 'PR #998 and PR #999 both touch src/sample.ts',
  deadlock: 'blocked-by cycle: #101 -> #102 -> #101',
  budget: '14 review-bot runs in the last hour (threshold 10)',
};

function minutesSince(iso) {
  return (Date.now() - Date.parse(iso)) / 60000;
}

async function sendDiscord(core, webhookUrl, text) {
  if (!webhookUrl) {
    core.warning(`no Discord webhook configured — unsent alert: ${text}`);
    return;
  }
  try {
    const res = await fetch(webhookUrl, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ content: text.slice(0, 1900) }),
    });
    if (!res.ok) core.warning(`discord send failed: ${res.status}`);
  } catch (err) {
    core.warning(`discord send failed: ${err.message}`);
  }
}

function makeAlerter(core) {
  const ops = process.env.DISCORD_WEBHOOK_OPS || '';
  const feed = process.env.DISCORD_WEBHOOK_FEED || '';
  return async function alert(wire, detail, isDrill) {
    const severity = WIRE_SEVERITY[wire];
    const prefix = isDrill ? '[DRILL]' : '';
    const text = `${prefix}[${severity}][${wire}] ${detail}`;
    // P0 pages the ops channel; P1 rides the feed. Each falls back to the
    // other so a single configured webhook still carries every alert.
    const url = severity === 'P0' ? ops || feed : feed || ops;
    core.notice(text);
    await sendDiscord(core, url, text);
  };
}

// --- individual checks (each returns a list of {wire, detail}) -------------

async function checkRedMain(github, repo) {
  const { data } = await github.rest.actions.listWorkflowRunsForRepo({
    ...repo,
    branch: 'main',
    status: 'completed',
    per_page: 10,
  });
  const newestPerWorkflow = new Map();
  for (const run of data.workflow_runs) {
    if (!newestPerWorkflow.has(run.name)) newestPerWorkflow.set(run.name, run);
  }
  return [...newestPerWorkflow.values()]
    .filter((run) => run.conclusion === 'failure')
    .map((run) => ({
      wire: 'red-main',
      detail: `${run.name} FAILED on main — merge freeze until green. ${run.html_url}`,
    }));
}

async function checkPrs(github, repo) {
  const found = [];
  const { data: prs } = await github.rest.pulls.list({
    ...repo,
    state: 'open',
    per_page: 30,
  });
  const active = prs.filter((pr) => !pr.draft);

  for (const pr of active) {
    const ageMin = minutesSince(pr.updated_at);
    try {
      const { data: checks } = await github.rest.checks.listForRef({
        ...repo,
        ref: pr.head.sha,
        per_page: 50,
      });
      const runs = checks.check_runs;
      const review = runs.find((c) => c.name === 'review');
      const reviewPending = !review || review.status !== 'completed';
      if (reviewPending && ageMin > THRESHOLDS.botStaleMin) {
        found.push({
          wire: 'stuck-pr',
          detail: `gate-health: review check ${review ? review.status : 'MISSING'} on PR #${pr.number} for ${Math.round(ageMin)}m — bot may be down (any seat can break-glass if urgent). ${pr.html_url}`,
        });
        continue;
      }
      const allGreen =
        runs.length > 0 &&
        runs.every(
          (c) =>
            c.status === 'completed' &&
            ['success', 'skipped', 'neutral'].includes(c.conclusion)
        );
      if (allGreen && ageMin > THRESHOLDS.stuckPrMin) {
        found.push({
          wire: 'stuck-pr',
          detail: `PR #${pr.number} green but unmerged for ${Math.round(ageMin)}m — merge it or say why. ${pr.html_url}`,
        });
      }
    } catch (err) {
      // checks API hiccup on one PR must not kill the sweep
    }
  }

  // collision: two open PRs editing the same file
  const fileOwners = new Map();
  for (const pr of active.slice(0, 10)) {
    try {
      const { data: files } = await github.rest.pulls.listFiles({
        ...repo,
        pull_number: pr.number,
        per_page: 100,
      });
      for (const f of files) {
        const owners = fileOwners.get(f.filename) ?? [];
        fileOwners.set(f.filename, [...owners, pr.number]);
      }
    } catch (err) {
      /* skip this PR */
    }
  }
  const collisions = [...fileOwners.entries()].filter(([, o]) => o.length > 1);
  if (collisions.length > 0) {
    const sample = collisions
      .slice(0, 5)
      .map(([file, owners]) => `${file} (PRs ${owners.map((n) => `#${n}`).join(', ')})`)
      .join('; ');
    found.push({
      wire: 'collision',
      detail: `${collisions.length} file(s) touched by multiple open PRs — coordinate before merging: ${sample}`,
    });
  }
  return { found, openPrCount: active.length };
}

function findBlockedCycle(issues) {
  const open = new Set(issues.map((i) => i.number));
  const edges = new Map();
  for (const issue of issues) {
    const deps = [...String(issue.body || '').matchAll(/blocked[ -]by[^0-9]{0,20}#(\d+)/gi)]
      .map((m) => Number(m[1]))
      .filter((n) => open.has(n));
    edges.set(issue.number, deps);
  }
  const state = new Map(); // 1 = visiting, 2 = done
  const stack = [];
  function dfs(node) {
    state.set(node, 1);
    stack.push(node);
    for (const dep of edges.get(node) ?? []) {
      if (state.get(dep) === 1) {
        return [...stack.slice(stack.indexOf(dep)), dep];
      }
      if (!state.has(dep)) {
        const cycle = dfs(dep);
        if (cycle) return cycle;
      }
    }
    state.set(node, 2);
    stack.pop();
    return null;
  }
  for (const node of edges.keys()) {
    if (!state.has(node)) {
      const cycle = dfs(node);
      if (cycle) return cycle;
    }
  }
  return null;
}

async function checkIssues(github, repo, openPrCount) {
  const found = [];
  const { data: raw } = await github.rest.issues.listForRepo({
    ...repo,
    state: 'open',
    per_page: 100,
  });
  const issues = raw.filter((i) => !i.pull_request);
  const labelsOf = (i) => i.labels.map((l) => (typeof l === 'string' ? l : l.name));

  // panic: the needs-human queue must drain fast — re-nag while non-empty
  const panicking = issues.filter((i) => labelsOf(i).includes('needs-human'));
  if (panicking.length > 0) {
    found.push({
      wire: 'panic',
      detail: `needs-human queue non-empty: ${panicking.map((i) => `#${i.number}`).join(', ')} — a human must decide.`,
    });
  }

  // stale-claim: assigned but untouched
  const stale = issues.filter(
    (i) => i.assignees.length > 0 && minutesSince(i.updated_at) > THRESHOLDS.staleClaimMin
  );
  if (stale.length > 0) {
    const sample = stale
      .slice(0, 5)
      .map((i) => `#${i.number} (@${i.assignees[0].login}, ${Math.round(minutesSince(i.updated_at))}m)`)
      .join(', ');
    found.push({
      wire: 'stale-claim',
      detail: `${stale.length} claimed issue(s) untouched >${THRESHOLDS.staleClaimMin}m: ${sample} — reclaim or release.`,
    });
  }

  // deadlock: blocked-by cycle, or a board where nothing can move
  const cycle = findBlockedCycle(issues);
  if (cycle) {
    found.push({
      wire: 'deadlock',
      detail: `blocked-by cycle: ${cycle.map((n) => `#${n}`).join(' -> ')} — FM must break one edge.`,
    });
  } else if (issues.length > 0) {
    const anyReady = issues.some((i) => labelsOf(i).includes('ready'));
    const anyClaimed = issues.some((i) => i.assignees.length > 0);
    if (!anyReady && !anyClaimed && openPrCount === 0) {
      found.push({
        wire: 'deadlock',
        detail: `board deadlock: ${issues.length} open issue(s), none ready, none claimed, no PRs in flight — FM must promote or unblock.`,
      });
    }
  }
  return found;
}

async function checkBudget(github, repo) {
  const since = new Date(Date.now() - 3600_000).toISOString();
  const { data } = await github.rest.actions.listWorkflowRuns({
    ...repo,
    workflow_id: 'claude-review.yml',
    created: `>=${since}`,
    per_page: 100,
  });
  if (data.total_count > THRESHOLDS.reviewRunsPerHour) {
    return [
      {
        wire: 'budget',
        detail: `${data.total_count} review-bot runs in the last hour (threshold ${THRESHOLDS.reviewRunsPerHour}) — token burn high; batch pushes or draft your PRs.`,
      },
    ];
  }
  return [];
}

async function checkDemoFreeze(github, repo) {
  const freezeAt = process.env.DEMO_FREEZE_AT || '';
  if (!freezeAt || Number.isNaN(Date.parse(freezeAt)) || Date.now() < Date.parse(freezeAt)) {
    return [];
  }
  const { data: commits } = await github.rest.repos.listCommits({
    ...repo,
    sha: 'main',
    since: freezeAt,
    per_page: 10,
  });
  if (commits.length > 0) {
    return [
      {
        wire: 'demo-freeze',
        detail: `${commits.length} commit(s) on main AFTER demo freeze (${freezeAt}) — revert or break-glass justify. Latest: ${commits[0].html_url}`,
      },
    ];
  }
  return [];
}

// --- entrypoint -------------------------------------------------------------

module.exports = async function run({ github, context, core }) {
  const repo = { owner: context.repo.owner, repo: context.repo.repo };
  const alert = makeAlerter(core);

  // Drill path: fire the named wire(s) through the REAL alert route, prefixed.
  // `simulate=all` fires every wire in ONE run — same real webhook path, same
  // [DRILL] prefix, same 3 P0 (#ops) / 5 P1 (#feed) checkpoint — but one runner
  // cold-start and one status poll instead of eight (faster + far less exposed
  // to a transient GitHub API blip killing the drill). A single wire name still
  // works for targeted re-tests.
  const simulate = (process.env.SIMULATE || '').trim();
  if (simulate) {
    const wires = simulate === 'all' ? Object.keys(WIRE_SEVERITY) : [simulate];
    for (const wire of wires) {
      if (!WIRE_SEVERITY[wire]) {
        core.setFailed(`unknown tripwire: ${wire} (valid: all, ${Object.keys(WIRE_SEVERITY).join(', ')})`);
        return;
      }
      await alert(wire, DRILL_SAMPLES[wire], true);
    }
    return;
  }

  // Instant paths: label application and post-freeze pushes alert without
  // waiting for the next cron pass.
  if (context.eventName === 'issues') {
    const label = context.payload.label?.name;
    if (label === 'needs-human') {
      const issue = context.payload.issue;
      await alert('panic', `needs-human applied on #${issue.number}: ${issue.title} — a human must decide. ${issue.html_url}`, false);
    }
    return;
  }
  if (context.eventName === 'push') {
    const fired = await checkDemoFreeze(github, repo);
    for (const f of fired) await alert(f.wire, f.detail, false);
    return;
  }

  // Full sweep (cron / manual dispatch without simulate).
  const fired = [];
  const sweeps = [
    () => checkRedMain(github, repo),
    async () => {
      const { found, openPrCount } = await checkPrs(github, repo);
      const issueFound = await checkIssues(github, repo, openPrCount);
      return [...found, ...issueFound];
    },
    () => checkBudget(github, repo),
    () => checkDemoFreeze(github, repo),
  ];
  for (const sweep of sweeps) {
    try {
      fired.push(...(await sweep()));
    } catch (err) {
      core.warning(`tripwire sweep error (failing open): ${err.message}`);
    }
  }

  for (const f of fired) await alert(f.wire, f.detail, false);
  core.notice(fired.length === 0 ? 'tripwires: all quiet' : `tripwires fired: ${fired.map((f) => f.wire).join(', ')}`);
};
