# Stage 3 Two-Pass After badb7f8 Limit20 Quality Review

## Overall conclusion

Live two-pass ran on 20 selected papers with 19 success and 1 failure. The datapoint normalization fixes are holding structurally: raw_name pseudo-parameter residues are 0, cleaned_body image residue is 0, and canonical/rejected counts are 0 across the 19 successful papers. However, the quality gate still fails because one paper failed live and a small subset still has sparse or zero process steps.

## Grade summary

- A=0
- B=17
- C=2
- D=1

## Key findings

- raw_name=key/value/unit/context/evidence_ref residues: 0

- cleaned_body image residue papers: 0

- process_steps_count=0 papers: 1

- evidence_objects=0 with scientific figures: 0

- average canonical_key_errors_count: 0.00

- average rejected_parameter_records_count: 0.00

## Failed paper

- 013_多孔莫来石纤维基隔热陶瓷的制备与性能研究: AttributeError 'str' object has no attribute 'get'

## Recommendation

Quality gate does not pass yet. Do not expand to 50 or remaining papers. Fix the failed paper path and sparse process-steps cases first; keep full mode as the higher-quality reference baseline.
