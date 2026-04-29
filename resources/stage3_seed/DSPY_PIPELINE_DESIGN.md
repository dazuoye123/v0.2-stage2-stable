# DSPy Pipeline Design

## Overall Principle

Do not use one giant prompt to extract the final JSON. The system should separate paper understanding, series discovery, data point extraction, evidence indexing, canonical normalization, and final template merge. Each stage should return small Pydantic-constrained objects, and the final JSON Array should be assembled by deterministic Python code.

The model is allowed to extract candidate facts and evidence spans. It is not allowed to invent core parameter names. Canonical keys must come from `ontology.yaml`.

## Shared Pydantic Objects

Use strict models for all stages. Suggested common objects:

```python
class EvidenceRef(BaseModel):
    source_id: str | None
    page: int | None
    section: str | None
    figure_id: str | None
    table_id: str | None
    quote_or_context: str | None
    confidence: float | None

class ParameterRecord(BaseModel):
    canonical_key: str | None
    raw_name: str | None
    value: float | str | bool | None
    min_value: float | None
    max_value: float | None
    unit: str | None
    raw_text: str | None
    evidence_refs: list[EvidenceRef] = []
```

`canonical_key` is nullable only before `NormalizeCanonicalKeys`. After normalization it must be either a valid ontology key or rejected into manual review.

## 1. ExtractPaperBasicInfo

Purpose: identify document-level metadata and broad material/process category.

Input:
- Cleaned first pages text
- PDF metadata
- File name

Output:
- `paper_id`
- `title`, `authors`, `year`, `doi`
- `document_type`, `language`, `is_review`
- `material_system`, `process_route`, `research_object_form`
- basic evidence refs

Pydantic: yes. Use fixed enum-like fields where possible:
- `document_type`: journal_article, thesis, conference_paper, review, patent, unknown
- `research_object_form`: continuous_fiber, nanofiber, porous_fiber, precursor_sol, spinning_solution, fiber_membrane, fiber_bulk, other, unknown

Extended data: not needed at this stage except rare bibliographic notes.

## 2. ExtractGlobalConstants

Purpose: extract conditions shared by all series, not results of a variable series.

Input:
- Full text chunks from abstract, experimental section, method section, common characterization section
- Paper basic info
- Ontology key list

Output:
- raw materials
- nominal composition
- shared process summary
- shared parameter candidates
- heat treatment programs
- characterization methods
- global TG/DSC, spectroscopy, and mechanism observations

Pydantic: yes. Use `ParameterRecord` for quantitative facts plus fixed objects for raw materials and heat treatment stages.

Fixed fields:
- raw material role names should use controlled values: aluminum_source, silicon_source, boron_source, zirconium_source, magnesium_source, rare_earth_source, polymer_additive, binder, template, seed, solvent, acid, base, surfactant, other.
- method names should use controlled values: XRD, SEM, TEM, FTIR, TG_DSC, BET, XPS, NMR, Raman, tensile_test, rheology, particle_size, zeta_potential, other.

Allowed in `extended_data`:
- rare cluster species, unusual precursor optical state, special apparatus details, custom synthesis labels.

Not allowed in `extended_data`:
- pH, solid content, viscosity, particle size, zeta potential, polymer content, forming parameters, heat treatment parameters, fiber diameter, pore parameters, density, strength, modulus, thermal conductivity, strength retention.

## 3. ExtractExperimentSeries

Purpose: discover independent experimental dimensions before extracting points.

Input:
- Section-level text chunks
- Figure/table captions
- Paper basic info
- Global constants

Output:
- list of series objects with `series_id`
- `series_name`
- `series_type`
- research question
- independent variable definitions
- controlled variable keys
- relevant source sections/figures/tables

Pydantic: yes, strongly constrained.

Suggested `series_type` values:
- formulation_variable
- precursor_property_variable
- forming_parameter_variable
- heat_treatment_variable
- raw_material_type_variable
- composition_variable
- scale_up_batch_variable
- characterization_only
- review_comparison

Fixed fields:
- `series_id`
- `series_type`
- independent variable `canonical_key` when the variable is in ontology
- otherwise `raw_name` plus `needs_ontology_extension=true`

Allowed in `extended_data`:
- unusual series grouping rationale, such as author-defined batch codes with no parameter names.

## 4. ExtractDataPoints

Purpose: extract each sample/condition row within one series.

Input:
- One series definition
- Relevant text chunks and tables
- Captions and nearby paragraphs
- Global constants
- Ontology key list

Output:
- `sample_id`, `sample_label`
- independent variable values
- per-point process parameters
- per-point results
- qualitative observations
- evidence refs

Pydantic: yes. This stage should be called once per series to reduce cross-series mixing.

Fixed fields:
- `sample_id`
- `independent_variable_values`
- `process_parameters`
- `results`
- `evidence_refs`

Allowed in `extended_data`:
- data point details that are important but not canonical, for example "fiber looked cotton-like", "network-like fibers formed", or author-specific sample aging labels.

Not allowed in `extended_data`:
- any key listed in `ontology.yaml` with `is_core_statistical_field: true`.

## 5. ExtractEvidenceObjects

Purpose: build a structured figure/table/image index before multimodal extraction.

Input:
- Figure captions
- Table captions
- Page locations
- Optional OCR or visual model outputs

Output:
- evidence objects for figures, panels, curves, peaks, SEM regions, TEM objects, scale bars, sample labels

Pydantic: yes. IDs should be deterministic:
- `fig_01`
- `panel_fig_01_a`
- `curve_fig_03_xrd_sample_a`
- `obj_fig_06_fiber_region_01`

Fixed fields:
- `figure_id`, `figure_type`, `page`, `caption`
- `panel_id`, `panel_label`
- `curve_id`
- `object_id`, `object_type`, `object_label`
- `bbox` when available

Allowed in `extended_data`:
- visual model notes, OCR uncertainty, scale bar parsing notes.

## 6. NormalizeCanonicalKeys

Purpose: map raw parameter names to canonical ontology keys and normalize units.

Input:
- All extracted `ParameterRecord` objects
- `ontology.yaml`
- unit conversion rules

Output:
- normalized parameter records
- rejected or uncertain records
- normalization log

Pydantic: yes. After this stage:
- `canonical_key` must be in ontology
- `unit` must equal ontology `standard_unit` when numeric
- min/max ranges must be split
- mean plus error keeps mean in `value` and error in `uncertainty`

This stage can use a small DSPy classifier for ambiguous aliases, but final acceptance should be deterministic:
- exact canonical key match
- alias match
- fuzzy match above threshold plus compatible unit/category
- otherwise manual review

## 7. MergeAndFillTemplate

Purpose: deterministic assembly of final `schema_v2.json` shape.

Input:
- Paper basic info
- Global constants
- Series and data points
- Evidence objects
- Multimodal extractions
- Cross-modal links
- Normalization log

Output:
- one legal JSON Array

Pydantic: yes for the final object, with `extra="forbid"` on core models.

This stage should not ask the LLM to write final JSON directly. Python should:
- create a deep copy of the template
- merge normalized objects
- recursively fill missing fields with `null`
- validate ID uniqueness
- validate that all core keys are canonical
- validate that `extended_data` contains no core statistical key

## Postprocessing Logic

Recommended Python flow:

1. Load `schema_v2.json` as a template and `ontology.yaml` as the source of truth.
2. Run staged DSPy modules and collect semi-structured Pydantic outputs.
3. Flatten all `ParameterRecord` objects from global constants, series constants, and data points.
4. Normalize keys by ontology alias tables.
5. Normalize units:
   - GPa to MPa for strength fields ending in `_MPa`
   - kPa to MPa for pressure fields ending in `_MPa`
   - C/h to C/min for `heating_rate_C_min`
   - m/min to mm/min only for fields ending in `_mm_min`
   - nm/um only according to the target canonical key
6. Merge records into fixed schema locations by category and canonical key.
7. Recursively fill absent keys with `None`.
8. Validate final root is a JSON Array.
9. Check no core statistical key appears under any `extended_data`.
10. Check no non-canonical key appears in:
    - `shared_parameters`
    - `process_parameters`
    - `results`
    - `additional_parameter_records[*].canonical_key`
    - `independent_variable_values[*].canonical_key`
11. Create `quality_flags` for OCR-only evidence, low confidence links, missing series grouping, uncertain unit conversion, or suspected table parsing errors.

## Minimal Module Layout

```python
class PaperExtractionPipeline(dspy.Module):
    def __init__(self, ontology):
        self.basic = dspy.ChainOfThought(ExtractPaperBasicInfo)
        self.global_constants = dspy.ChainOfThought(ExtractGlobalConstants)
        self.series = dspy.ChainOfThought(ExtractExperimentSeries)
        self.points = dspy.ChainOfThought(ExtractDataPoints)
        self.evidence = dspy.ChainOfThought(ExtractEvidenceObjects)
        self.normalize = NormalizeCanonicalKeysModule(ontology)
        self.merge = MergeAndFillTemplateModule(ontology)

    def forward(self, paper_chunks, captions, pdf_metadata):
        basic = self.basic(paper_chunks.head, pdf_metadata)
        global_constants = self.global_constants(paper_chunks, basic, ontology_keys=ontology.keys())
        series = self.series(paper_chunks, captions, basic, global_constants)
        points = [self.points(s, paper_chunks.for_series(s), captions) for s in series.items]
        evidence = self.evidence(captions, paper_chunks.figure_contexts)
        normalized = self.normalize(global_constants, series, points)
        return self.merge(basic, global_constants, series, points, evidence, normalized)
```

The code above is a design sketch, not the full implementation. The important architectural decision is that the final JSON is assembled and validated outside the LLM.
