# Stage 3 Two-Pass DataPoint Contract

Stage 3 `two-pass` Pass 2 parameter/data-point payloads are only allowed to use these shapes:

## A. Standard parameter record

```json
{
  "canonical_key": "calcination_temperature_C",
  "raw_name": "calcination temperature",
  "value": 1200,
  "unit": "C",
  "source_text": "calcination at 1200 C",
  "evidence_refs": [{"source_id": "text_2.5"}]
}
```

## B. Compact bundle

```json
{
  "key": "calcination temperature",
  "value": 1200,
  "unit": "C",
  "context": "calcination at 1200 C",
  "evidence_id": "Fig. 3"
}
```

## C. Compact bundle list

```json
{
  "parameters": [
    {"key": "PEO content", "value": 3.5, "unit": "wt%", "context": "PEO content = 3.5 wt%"},
    {"key": "spinning pressure", "value": 0.4, "unit": "MPa", "context": "spinning pressure = 0.4 MPa"}
  ]
}
```

## Normalization rules

- Shapes `B` and `C` must be normalized into legal `DataPoint` / `ParameterRecord` objects.
- The postprocess layer must never materialize pseudo records like:
  - `raw_name = key`
  - `raw_name = value`
  - `raw_name = unit`
  - `raw_name = context`
  - `raw_name = evidence_ref`
- Unknown keys must not become accepted `data_points`.
  - They should be rejected or marked for manual review.
- If `value` is list-valued:
  - spectral peak lists may be split or preserved as raw text with normalization notes
  - non-spectral lists must not be written directly into scalar `value` fields
- Deterministic evidence fallback must preserve Stage 2 scientific figures even when LLM evidence output is empty.
