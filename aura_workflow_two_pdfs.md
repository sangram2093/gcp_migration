# Aura Workflow (Old vs New PDFs)

## 1) Parse old PDF into chunks
- Tool: `parse_pdf`
- Args:
  - `pdfPath`: /path/to/old.pdf
  - `chunkSizeChars` (optional, default 12000): 12000
- Output: Markdown with `## Chunk N` sections (oldMarkdown).

## 2) Parse new PDF into chunks
- Tool: `parse_pdf`
- Args:
  - `pdfPath`: /path/to/new.pdf
  - `chunkSizeChars` (optional): 12000
- Output: Markdown with `## Chunk N` sections (newMarkdown).

## 3) Extract entities from OLD chunks
- Tool: `extract_entities`
- Args:
  - `markdown`: oldMarkdown (from step 1)
  - `prompt` or `promptFilePath` (optional custom prompt; omit to use default)
  - `previousGraphJson`: (leave blank for old)
- Output: Markdown + JSON graph (oldGraphJson).

## 4) Extract entities from NEW chunks (biasing with OLD graph to reduce duplicates)
- Tool: `extract_entities`
- Args:
  - `markdown`: newMarkdown (from step 2)
  - `prompt` or `promptFilePath` (optional custom prompt)
  - `previousGraphJson`: oldGraphJson (from step 3)
- Output: Markdown + JSON graph (newGraphJson).

## 5) Build PlantUML (new and diff)
- Tool: `plantuml_builder`
- Args:
  - `newGraphJson`: newGraphJson (from step 4)
  - `oldGraphJson`: oldGraphJson (from step 3)
  - `title`: (optional)
  - `scale`: (optional, e.g., `max 1600*900`)
- Output: PlantUML for the new graph and a diff (common gray, new green, removed red).
