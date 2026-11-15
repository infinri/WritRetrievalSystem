# PR #11 review probes (preserved)

`review_repros_baseline.rs.txt` is the independent reviewer's probe file, which asserts the
observed defects. `baseline-output.txt` is that file run against merged `00505e9`: all 6
pass, so all 6 defects reproduce. `after-fix-output.txt` is the same probes after increment
A: all 6 fail, so the defects are gone. The desired contracts live in
`tests/temporal_contracts.rs`. The probe file is kept here as text and is not a test target,
so it does not bless the defects.
