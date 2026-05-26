# Stage 3 Two-pass Next50 After C Repair Review

This review re-evaluates the full next50 cohort against the current `stage3_twopass/` outputs after targeted offline repair of the prior C-grade papers.

## Summary

- A = 5
- B = 44
- C = 1
- D = 0
- mainline usable count (A/B) = 49/50
- manual_hold_count = 1
- manual_hold_papers = 042_氧化铝连续纤维的研制及表征（初步搞到这里了）
- raw_name key/value bug count = 0
- list_value_validation_error_count = 0
- evidence_zero_with_scientific_figures_count = 0
- cleaned_body_image_residue_count = 0
- average_canonical_key_errors_count = 0.0
- average_rejected_parameter_records_count = 0.0
- average_other_action_ratio = 0.2744
- average_missing_evidence_text_ratio = 0.54

## Conclusion

After the targeted C-grade process-step repairs, the next50 cohort is now **A=5, B=44, C=1, D=0**. Only **1** paper remains outside the mainline usable set, and it is explicitly marked `manual_hold` instead of being silently promoted.

## Manual Hold

- 042_氧化铝连续纤维的研制及表征（初步搞到这里了）: process steps still come primarily from method-overview / review-style text, so it should stay out of the mainline usable set until a process-steps-only repair or manual review is done.