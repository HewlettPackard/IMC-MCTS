# Report proxies for revised controllers

Profile: single_child_controller_report_proxies_v1. Scope: 9x9, 96 hidden
units, 162 or 163 inputs, CAM1024, three 512 KiB node banks and one 512 KiB
child bank. The configured arithmetic, ADC lanes and precision must match
the existing digital geometry. Both readout variants use their own reports.

These are engineering cost estimates, not matching synthesis. The old
reports retain their exact parameters, units, warnings and source hashes.
The selection and tree-update parents already contain cache/board/path
buffers, seeded choice, Q17 datapaths and handshakes. FSM glue excludes
child modules. Their reference costs remain useful for a budget for similar
functions, but are not evidence for the new linked-list/bitmap controller.
The 163rd neural input preserves the accumulator, divider, hidden width
and readout geometry; its precise synthesized cost is not available.

For the three changed controllers, and the neural parent only when its
162-input report is incompatible, estimate the whole parent at 1.25 times
the reference. The 25% reserve is an explicit engineering assumption, not
an experimentally established overhead. Test multipliers 1.0, 1.25 and 2.0.
Those scenarios expose sensitivity; real costs can lie outside them.
Applying a whole-parent reserve avoids unsupported fine-grained power
splits. Internal parts are included once and have no separately invented
power or area. Per-node state is already included in the fixed SRAM pool.

Area = native report area * multiplier * (22/65)^2.
Dynamic energy = (active_mW * active_us + clock_idle_mW * idle_us)
                 * multiplier * (22/65) * (0.8/1.0)^2.
Leakage energy = native leakage_mW * elapsed_us * multiplier.
Power-times-microseconds gives nJ. Leakage remains a native65 proxy, not a
22 nm measurement. Clock-only idle, no power gating, and assumed 500 MHz
remain unchanged. Existing physical allowances apply once to the enlarged
area and digital energy subtotal. Neither reference slack nor reference
setup-path counts validate the new control schedule.

Every estimate includes the reference parameters, report paths, multiplier,
policy hash, reason and status in JSON. CSV and Studio disclose the proxy.
Existing matching-report APIs continue to reject parameter mismatches.
The report proxy is a separate admission path restricted to this geometry.
Legacy full-expansion profiles retain their old accounting.

This closes the modeled-core estimate for the reviewed configuration. It
does not close controller characterization, physical timing, analog accuracy,
Go host-rule costs, I/O or weight-programming costs. These omissions must
remain visible in paper claims. No inference about playing strength follows.
