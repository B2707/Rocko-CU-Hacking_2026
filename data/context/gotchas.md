# Team Gotchas (acked)

<!-- ONE WRITER: First Mate / gotcha-bot only. Seats submit via /gotcha —
     candidates quarantine in gotcha-candidates/ and ride their branch's PR;
     the FM acks the real ones into this file. Loaded by /start on every
     seat: keep entries ONE line each, newest on top. -->

- Re-running `repo-init.sh` PUTs the base ruleset and silently DROPS the required `review`/`tests-touched` merge checks — fixed to merge-preserve, but after any ruleset edit verify with: `gh api repos/<r>/rulesets/<id> --jq '[.rules[]|select(.type=="required_status_checks")]'`
- `drill.sh` fires all 8 wires in ONE run (`simulate=all`) — do NOT revert to per-wire dispatch: tripwires.yml shares one `tripwires` concurrency group, so parallel dispatch gets all but the newest queued run auto-cancelled (looks like 5/8 mystery failures). The concurrency group still serializes real scheduled scans.
- `gh api -f/-F` flag encoding 422s on `POST /repos/…/hooks` — build webhook payloads as explicit JSON (`jq -n … | gh api --input -`)
