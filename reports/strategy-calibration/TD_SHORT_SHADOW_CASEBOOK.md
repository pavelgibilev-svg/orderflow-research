# E. TD-short shadow casebook

**Build:** 2026-06-04T17:35:04+00:00

## Top good accepted
| venue | date | outcome | mfe | mae | t2(min) | prior60m | ofi | reclaim | conf | why |
|---|---|:--:|--:|--:|--:|--:|--:|:--:|--:|:--|
| OKX_MARCH | 2026-03-26 | WIN | 4.885 | -0.579 | 1006.5 | -0.5478 | -0.2100395096093769 | 0 | 2 | accepted; microprice_down,thin_bid_path |
| OKX_MARCH | 2026-03-27 | WIN | 4.82 | -0.487 | 561.8 | -0.0764 | -0.1248910440996173 | 0 | 2 | accepted; microprice_down,thin_bid_path |
| OKX_MARCH | 2026-03-26 | WIN | 4.76 | -0.711 | 1028.5 | -0.8789 | -0.12000118458752858 | 0 | 3 | accepted; taker_sell,microprice_down,thin_bid_path |
| OKX_MARCH | 2026-03-26 | WIN | 4.717 | -0.595 | 715.5 | -0.419 | -0.25184839447836066 | 0 | 2 | accepted; microprice_down,thin_bid_path |
| OKX_MARCH | 2026-03-05 | WIN | 4.322 | -1.133 | 1193.2 | -0.9576 | 0.04153993661079715 | 0 | 2 | accepted; microprice_down,thin_bid_path |
| OKX_MARCH | 2026-03-05 | WIN | 4.262 | -1.197 | 1194.3 | -0.9442 | 0.16563642271885298 | 0 | 2 | accepted; microprice_down,thin_bid_path |
| OKX_MARCH | 2026-03-26 | LOSS | 4.178 | -1.562 | 987.9 | -0.753 | 0.003973056118506414 | 1 | 4 | accepted; rejection_proof,taker_sell,microprice_down,thin_bid_path |
| OKX_MARCH | 2026-03-26 | LOSS | 4.178 | -1.562 | 987.9 | -0.753 | 0.07514565262160108 | 1 | 4 | accepted; rejection_proof,taker_sell,microprice_down,thin_bid_path |
| OKX_MARCH | 2026-03-26 | LOSS | 4.178 | -1.562 | 987.9 | -0.753 | -0.19727696327028232 | 1 | 4 | accepted; rejection_proof,taker_sell,microprice_down,thin_bid_path |
| OKX_MARCH | 2026-03-18 | WIN | 4.07 | -0.037 | 359.3 | -0.4377 | -0.3818666239765814 | 1 | 4 | accepted; rejection_proof,taker_sell,microprice_down,thin_bid_path |

## Bad accepted (lost)
| venue | date | outcome | mfe | mae | t2(min) | prior60m | ofi | reclaim | conf | why |
|---|---|:--:|--:|--:|--:|--:|--:|:--:|--:|:--|
| OKX_MARCH | 2026-03-19 | LOSS | 1.925 | -1.768 | None | -0.4033 | -0.2943016783950588 | 0 | 2 | accepted but lost; microprice_down,thin_bid_path |
| OKX_MARCH | 2026-03-19 | LOSS | 1.326 | -2.39 | None | -0.6915 | -0.21864764202680742 | 0 | 2 | accepted but lost; microprice_down,thin_bid_path |
| OKX_MARCH | 2026-03-19 | LOSS | 0.787 | -2.949 | None | -0.6179 | -0.08477245698310885 | 0 | 2 | accepted but lost; microprice_down,thin_bid_path |
| OKX_MARCH | 2026-03-22 | LOSS | 1.655 | -4.452 | None | -0.3058 | 0.05768640596491194 | 0 | 3 | accepted but lost; taker_sell,microprice_down,thin_bid_path |
| OKX_MARCH | 2026-03-22 | LOSS | 1.333 | -4.793 | None | -0.5513 | -0.39369320559862125 | 0 | 3 | accepted but lost; taker_sell,microprice_down,thin_bid_path |
| OKX_MARCH | 2026-03-22 | LOSS | 1.309 | -4.82 | None | -0.637 | -0.3366613879150154 | 0 | 2 | accepted but lost; taker_sell,thin_bid_path |
| OKX_MARCH | 2026-03-22 | LOSS | 1.507 | -5.033 | None | -0.4406 | -0.29623076857583147 | 0 | 2 | accepted but lost; taker_sell,thin_bid_path |
| OKX_MARCH | 2026-03-22 | LOSS | 1.247 | -5.31 | None | -0.6016 | -0.4062824006971852 | 0 | 3 | accepted but lost; taker_sell,microprice_down,thin_bid_path |
| OKX_MARCH | 2026-03-22 | LOSS | 0.41 | -6.203 | None | -1.1255 | -0.33629350160020716 | 1 | 4 | accepted but lost; rejection_proof,taker_sell,microprice_down,thin_bid_path |
| OKX_MARCH | 2026-03-24 | LOSS | 0.013 | -4.331 | None | -0.6711 | -0.19548001213057517 | 1 | 4 | accepted but lost; rejection_proof,taker_sell,microprice_down,thin_bid_path |

## Correctly rejected losses
| venue | date | outcome | mfe | mae | t2(min) | prior60m | ofi | reclaim | conf | why |
|---|---|:--:|--:|--:|--:|--:|--:|:--:|--:|:--|
| OKX_MARCH | 2026-03-03 | LOSS | 0.191 | -8.292 | None | 1.5503 | -0.2534834987207325 | 0 | 2 | rejected; no_fresh_weakness_60m |
| OKX_MARCH | 2026-03-19 | LOSS | 0.751 | -2.986 | None | -0.5087 | -0.04444379884372885 | 0 | 2 | rejected; buyer_absorption |
| OKX_MARCH | 2026-03-19 | LOSS | 0.751 | -2.986 | None | -0.5087 | -0.17293096679110795 | 0 | 2 | rejected; buyer_absorption |
| OKX_MARCH | 2026-03-19 | LOSS | 0.975 | -2.753 | None | 0.1502 | 0.007281379973713101 | 1 | 4 | rejected; no_fresh_weakness_60m |
| OKX_MARCH | 2026-03-19 | LOSS | 0.0 | -3.11 | None | 0.0134 | 0.1355993173936762 | 0 | 3 | rejected; no_fresh_weakness_60m |
| OKX_MARCH | 2026-03-19 | LOSS | 0.396 | -2.852 | None | 0.0889 | 0.06361510769116539 | 0 | 2 | rejected; no_fresh_weakness_60m;buyer_absorption |
| OKX_MARCH | 2026-03-19 | LOSS | 0.603 | -2.248 | None | 0.8932 | -0.10406975760753669 | 0 | 3 | rejected; no_fresh_weakness_60m |
| OKX_MARCH | 2026-03-19 | LOSS | 0.591 | -2.26 | None | 0.4708 | 0.029550083268686883 | 1 | 3 | rejected; no_fresh_weakness_60m;buyer_absorption |
| OKX_MARCH | 2026-03-22 | LOSS | 1.496 | -5.045 | None | -0.1121 | 0.22967073575141095 | 0 | 2 | rejected; buyer_absorption |
| OKX_MARCH | 2026-03-22 | LOSS | 0.41 | -6.203 | None | -1.1255 | 0.49524581435466974 | 1 | 4 | rejected; buyer_absorption |

## Wrongly rejected winners (missed)
| venue | date | outcome | mfe | mae | t2(min) | prior60m | ofi | reclaim | conf | why |
|---|---|:--:|--:|--:|--:|--:|--:|:--:|--:|:--|
| OKX_MARCH | 2026-03-26 | WIN | 5.275 | -0.265 | 257.9 | 0.2761 | -0.08547068579559393 | 0 | 1 | rejected; no_fresh_weakness_60m |
| OKX_MARCH | 2026-03-27 | WIN | 5.096 | -0.026 | 382.9 | 0.2604 | -0.27742976625385696 | 1 | 3 | rejected; no_fresh_weakness_60m |
| OKX_MARCH | 2026-03-27 | WIN | 5.028 | -0.028 | 363.8 | 0.1817 | 0.1063229580839657 | 1 | 3 | rejected; no_fresh_weakness_60m |
| OKX_MARCH | 2026-03-27 | WIN | 4.858 | -0.446 | 616.8 | 0.0552 | 0.1112474423411586 | 1 | 3 | rejected; no_fresh_weakness_60m;buyer_absorption |
| OKX_MARCH | 2026-03-27 | WIN | 4.702 | -0.611 | 575.7 | 0.0285 | -0.21900282358173334 | 0 | 2 | rejected; no_fresh_weakness_60m;buyer_absorption |
| OKX_MARCH | 2026-03-26 | WIN | 4.6 | -0.695 | 1219.3 | -0.2155 | -0.061391910698974525 | 0 | 2 | rejected; buyer_absorption |
| OKX_MARCH | 2026-03-26 | WIN | 4.572 | -0.725 | 1222.3 | -0.2571 | 0.001765179980247958 | 0 | 1 | rejected; weak_confluence(1/4) |
| OKX_MARCH | 2026-03-06 | WIN | 4.561 | -0.641 | 816.5 | -0.2667 | -0.15925109558846662 | 0 | 2 | rejected; buyer_absorption |
| OKX_MARCH | 2026-03-26 | WIN | 4.528 | -1.221 | 890.1 | 0.3677 | -0.29516167504371527 | 0 | 2 | rejected; no_fresh_weakness_60m;buyer_absorption |
| OKX_MARCH | 2026-03-27 | WIN | 4.45 | -0.536 | 358.1 | -0.4067 | -0.0766330844467576 | 0 | 1 | rejected; buyer_absorption |