# Stage 3 Two-pass A Grade Drift Audit

- next100 A count = 60
- combined A for next100 = 0
- A->A = 0
- A->B = 60
- A->C = 0
- B->B = 22
- B->C = 7
- C->C = 11
- C->B = 0

## Conclusion

- The disappearance of A is caused by review rubric drift, not by new Stage 3 outputs changing.
- The combined 70+100 review penalized missing `source_text/evidence_text` at the datapoint level too aggressively and effectively collapsed many A papers into B.
- There is no evidence that it read the wrong output directory: 032/072 fixes and next100-specific values were reflected correctly.
- There is also no extractor regression in raw_name/canonical/rejected/evidence hard metrics.