# QWEN-E2E-05 ? B?ng latency c?ng b? cho review

Kh?ng ch?a raw prompts, d? li?u ngu?n ho?c credentials. Th?i gian c? overhead observer; API g?m network/tunnel/queue/inference.

## L??t ??u

# QWEN-E2E-05 — Latency từng Qwen call

Thời gian giây. API tính đến đọc hết body; adapter gồm tokenizer/parser. Các stages lồng nhau không cộng trực tiếp.

| QA | Call | Agent/stage | Input | Output | API s | Adapter s | HTTP |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| VFB-SH-0018 | 1 | m5-coordinator-plan | 534 | 243 | 59.064 | 59.872 | 200 |
| VFB-SH-0018 | 2 | m5-specialist-T1 | 2527 | 567 | 76.557 | 76.642 | 200 |
| VFB-SH-0018 | 3 | m5-specialist-T1 | None | None | 1.509 | 1.642 | 500 |
| VFB-SH-0018 | 4 | m5-specialist-T2 | None | None | 0.366 | 0.474 | 500 |
| VFB-SH-0018 | 5 | m5-specialist-T3 | None | None | 0.787 | 0.910 | 500 |
| VFB-MH-0017 | 6 | m5-coordinator-plan | None | None | 0.468 | 0.497 | 502 |
| VFB-NR-0018 | 7 | m5-coordinator-plan | None | None | 1.624 | 1.656 | 502 |


## Provider rerun

# QWEN-E2E-05 — Latency từng Qwen call

Thời gian giây. API tính đến đọc hết body; adapter gồm tokenizer/parser. Các stages lồng nhau không cộng trực tiếp.

| QA | Call | Agent/stage | Input | Output | API s | Adapter s | HTTP |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| VFB-SH-0018 | 1 | m5-coordinator-plan | 534 | 243 | 82.653 | 83.404 | 200 |
| VFB-SH-0018 | 2 | m5-specialist-T1 | 2527 | 567 | 55.614 | 55.741 | 200 |
| VFB-SH-0018 | 3 | m5-specialist-T1 | 7734 | 48 | 20.878 | 21.158 | 200 |
| VFB-SH-0018 | 4 | m5-specialist-T1 | 4898 | 78 | 16.530 | 16.726 | 200 |
| VFB-SH-0018 | 5 | m5-specialist-T2 | 6104 | 560 | 88.304 | 88.536 | 200 |
| VFB-SH-0018 | 6 | m5-specialist-T2 | 8476 | 560 | 114.605 | 114.809 | 200 |
| VFB-SH-0018 | 7 | m5-specialist-T2 | 7349 | 153 | 38.268 | 38.434 | 200 |
| VFB-SH-0018 | 8 | m5-specialist-T3 | 6860 | 69 | 22.552 | 22.720 | 200 |
| VFB-SH-0018 | 9 | m5-specialist-T3 | 6992 | 69 | 18.577 | 18.883 | 200 |
| VFB-SH-0018 | 10 | m5-specialist-T3 | 5775 | 78 | 20.106 | 20.375 | 200 |
| VFB-MH-0017 | 11 | m5-coordinator-plan | 534 | 319 | 87.911 | 87.966 | 200 |
| VFB-MH-0017 | 12 | m5-specialist-T1 | 3838 | 93 | 15.759 | 15.850 | 200 |
| VFB-MH-0017 | 13 | m5-specialist-T1 | 8800 | 93 | 32.152 | 32.306 | 200 |
| VFB-MH-0017 | 14 | m5-specialist-T1 | 5988 | 133 | 25.013 | 25.167 | 200 |
| VFB-MH-0017 | 15 | m5-specialist-T1 | 3601 | 65 | 11.428 | 11.518 | 200 |
| VFB-MH-0017 | 16 | m5-specialist-T2 | 9917 | 144 | 50.138 | 50.335 | 200 |
| VFB-MH-0017 | 17 | m5-specialist-T2 | 5818 | 144 | 24.793 | 25.025 | 200 |
| VFB-MH-0017 | 18 | m5-specialist-T2 | 3644 | 185 | 23.524 | 23.698 | 200 |
| VFB-MH-0017 | 19 | m5-specialist-T3 | 9925 | 144 | 49.753 | 50.225 | 200 |
| VFB-MH-0017 | 20 | m5-specialist-T3 | 5826 | 144 | 24.679 | 24.933 | 200 |
| VFB-MH-0017 | 21 | m5-specialist-T3 | 3708 | 65 | 11.379 | 11.479 | 200 |
| VFB-MH-0017 | 22 | m6-document | 1648 | 153 | 16.753 | 16.807 | 200 |
| VFB-NR-0018 | 23 | m5-coordinator-plan | 553 | 337 | 117.715 | 117.765 | 200 |
| VFB-NR-0018 | 24 | m5-specialist-T1 | 3409 | 79 | 12.582 | 12.678 | 200 |
| VFB-NR-0018 | 25 | m5-specialist-T1 | 4350 | 186 | 24.786 | 24.944 | 200 |
| VFB-NR-0018 | 26 | m5-specialist-T1 | 4352 | 27 | 4.829 | 5.050 | 200 |
| VFB-NR-0018 | 27 | m5-specialist-T1 | 2268 | 268 | 70.356 | 70.447 | 200 |
| VFB-NR-0018 | 28 | m5-specialist-T2 | 4127 | 131 | 21.320 | 21.431 | 200 |
| VFB-NR-0018 | 29 | m5-specialist-T2 | 4389 | 27 | 5.265 | 5.359 | 200 |
| VFB-NR-0018 | 30 | m5-specialist-T2 | 4258 | 79 | 12.984 | 13.088 | 200 |
| VFB-NR-0018 | 31 | m5-specialist-T2 | 2438 | 162 | 17.054 | 17.129 | 200 |
| VFB-NR-0018 | 32 | m5-specialist-T3 | 4524 | 52 | 12.278 | 12.392 | 200 |
| VFB-NR-0018 | 33 | m5-specialist-T3 | 2425 | 132 | 14.408 | 14.471 | 200 |
| VFB-NR-0018 | 34 | m6-lite | 2240 | 143 | 16.105 | 16.186 | 200 |
