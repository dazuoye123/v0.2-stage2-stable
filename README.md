# alumina_sol_extractor

Lightweight alumina-sol literature extraction project.

Current stage:

1. Upload a local PDF to MinerU.
2. Download MinerU Markdown and images.
3. Save raw MinerU output under `data/mineru_raw/{paper_id}/`.
4. Rewrite local image paths into `data/outputs/{paper_id}/figures/`.
5. Normalize common chemistry formula artifacts.
6. Save cleaned Markdown to `data/markdown/{paper_id}.md`.

Docling and Mistral are not used in this version.

## Setup

```bash
pip install -r requirements.txt
```

Set your MinerU token:

```bash
set MINERU_API_KEY=your-token
```

Optional:

```bash
set MINERU_BASE_URL=https://mineru.net
```

## Run

Put a PDF at:

```text
data/pdfs/example.pdf
```

Then run:

```bash
python main.py
```

## Test

```bash
python scripts/test_chemical_text_normalizer.py
```

## License Note

This project keeps the Apache 2.0 license notice. Earlier design discussion was
inspired by LeMaterial/lematerial-llm-synthesis, but this code path is now a
MinerU-only, alumina-sol-specific implementation.
