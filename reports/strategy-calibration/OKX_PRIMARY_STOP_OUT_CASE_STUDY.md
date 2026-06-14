# OKX primary unique zones - case study of stop-outs

**Build:** 2026-05-23T09:42:51+00:00
**Scope:** all 15 primary unique reached zones from engine. Stop-outs (any of MODE 1 / MODE 2 stops at -1 %): **8**.

## Per-zone audit

| date | dir | entry | zone L/H | width % | entry→invalid % | conf→trig min | flow mult | break % | OFI score | trig score | alert exit | alert pnl % | strict exit | stopout? | zone-bdy stop would survive |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|:---:|:---:|
| 2026-03-02 | LONG | 66284.95 | 65714.45/66170.55 | 0.688 if width else - | 0.8606780272143224 | 24.116666666666667 | 5.757624965962408 | 0.17288657869700974 | 0.08544428805846682 | 1 | stop_1pct | -1.0 | stop_1pct | YES | no |
| 2026-03-03 | SHORT | 68699.35 | 68737.75/68932.95 | 0.284 if width else - | 0.3400323292723894 | 10.516666666666667 | 8.874654949551008 | 0.0558644994926284 | -0.08652858554267313 | 1 | target_2pct | 2.0 | target_2pct | no | no |
| 2026-03-03 | LONG | 67032.55 | 66793.45/66980.85 | 0.280 if width else - | 0.35669238302885065 | 8.333333333333334 | 1.4058283699699314 | 0.0771862405448678 | 0.22457841713612223 | 0.9704167516303623 | stop_1pct | -1.0 | stop_1pct | YES | no |
| 2026-03-04 | LONG | 68406.45 | 67827.45/68329.79782499999 | 0.734 if width else - | 0.8464114129588658 | 51.18333333333333 | 3.448428502122618 | 0.1121797187170445 | -0.058226410967494056 | 1 | stop_1pct | -1.0 | None | YES | no |
| 2026-03-05 | SHORT | 72567.75 | 72682.15/72971.05 | 0.398 if width else - | 0.5557565171856684 | 57.18333333333333 | 1.4096023977034298 | 0.1573976554078191 | 0.1455232034301897 | 0.9698395940539284 | stop_1pct | -1.0 | None | YES | no |
| 2026-03-06 | SHORT | 70757.05 | 70793.85/70888.476525 | 0.134 if width else - | 0.18574336408881176 | 47.8 | 1.4630098752781397 | 0.05198191650828837 | -0.010135902196575813 | 0.9888840968214125 | target_2pct | 2.0 | target_2pct | no | no |
| 2026-03-08 | SHORT | 67168.45 | 67209.05/67286.05 | 0.115 if width else - | 0.17508220005077654 | 2.0833333333333335 | 1.96184439252578 | 0.06040853129155347 | -0.40480723115410644 | 1 | stop_1pct | -1.0 | stop_1pct | YES | no |
| 2026-03-09 | LONG | 66583.75 | 66255.45/66473.95 | 0.328 if width else - | 0.4930632474139755 | 35.483333333333334 | 1.8095018664104272 | 0.16517748682002936 | 0.1215195256798341 | 1 | target_2pct | 2.0 | target_2pct | no | no |
| 2026-03-10 | LONG | 68515.15 | 68350.95/68466.55 | 0.169 if width else - | 0.23965502520245102 | 7.683333333333334 | 8.934067559419262 | 0.07098356788824801 | -0.04697650072069879 | 1 | target_2pct | 2.0 | target_2pct | no | YES |
| 2026-03-10 | SHORT | 70667.0 | 70720.05/70967.015775 | 0.349 if width else - | 0.4245486224121685 | 0.55 | 1.5491760859415693 | 0.07501408723551936 | -0.15778829629368935 | 1 | target_2pct | 2.0 | target_2pct | no | no |
| 2026-03-10 | SHORT | 70960.85 | 71228.75/71346.55 | 0.166 if width else - | 0.5435391486995957 | 39.516666666666666 | 1.4353089025859906 | 0.37611217380621476 | 0.1361596555016534 | 0.9782192888771584 | target_2pct | 2.0 | target_2pct | no | YES |
| 2026-03-11 | LONG | 69650.65 | 69450.05/69607.95 | 0.227 if width else - | 0.2880087981949792 | 15.583333333333334 | 1.4072733621356353 | 0.061343567796490334 | -0.21926238676529217 | 0.9658395303010983 | stop_1pct | -1.0 | stop_1pct | YES | no |
| 2026-03-13 | LONG | 71719.95 | 70413.925425/71681.85 | 1.768 if width else - | 1.8210059753248617 | 9.066666666666666 | 3.161273380452247 | 0.05315152998979695 | 0.1429105537321096 | 1 | stop_1pct | -1.0 | stop_1pct | YES | YES |
| 2026-03-13 | SHORT | 72792.25 | 72983.85/73296.95 | 0.430 if width else - | 0.6933430413265109 | 1.2666666666666666 | 1.4993141460233668 | 0.2625238323272968 | -0.24323999245406194 | 1 | stop_1pct | -1.0 | None | YES | no |
| 2026-03-15 | LONG | 71119.75 | 70964.450025/71065.95 | 0.143 if width else - | 0.21836406202215522 | 11.25 | 1.4601896845386804 | 0.0757043281627881 | -0.22753928887150687 | 0.9884880481914706 | target_2pct | 2.0 | target_2pct | no | no |

## Aggregate stop-out diagnostics

- primaries that hit -1 % stop in alert-level OR strict-ledger: **8 / 15**
- of stop-outs: zone-boundary stop would have survived: **1 / 8**

Interpretation:
- If many stop-outs would survive a zone-boundary stop, the issue is **stop too tight (1 % fixed too aggressive)**, not signal wrongness.
- If few would survive (most MAE > zone width), the issue is **entry overextension** — by the time engine triggers, price has already moved beyond zone protection.