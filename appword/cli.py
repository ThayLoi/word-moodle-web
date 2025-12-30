import typer
from pathlib import Path
from appword.core.parser import parse_docx_to_json
from appword.core.enricher import enrich_json_with_mapping
from appword.core.exporter import build_quiz_from_json

app = typer.Typer(add_completion=False, no_args_is_help=True)

@app.command()
def parse(docx_file: Path, outdir: Path = Path("output_questions")):
    outdir.mkdir(parents=True, exist_ok=True)
    jp = parse_docx_to_json(str(docx_file), output_dir=str(outdir))
    typer.echo(f"JSON: {jp}")

@app.command()
def enrich(json_file: Path, mapping_dir: Path):
    out = enrich_json_with_mapping(str(json_file), str(mapping_dir), json_out=None, overwrite=True)
    typer.echo(f"Enriched JSON: {out}")

@app.command()
def build(json_file: Path, xml_out: Path = Path("output_questions/moodle.xml")):
    xp = build_quiz_from_json(str(json_file), xml_out=str(xml_out))
    typer.echo(f"XML: {xp}")

@app.command("one-shot")
def one_shot(docx_file: Path, outdir: Path = Path("output_questions"), mapping_dir: Path = None):
    outdir.mkdir(parents=True, exist_ok=True)
    jp = parse_docx_to_json(str(docx_file), output_dir=str(outdir))
    if mapping_dir:
        jp = enrich_json_with_mapping(jp, str(mapping_dir), json_out=None, overwrite=True)
    xp = build_quiz_from_json(str(jp), xml_out=str(outdir / "moodle.xml"))
    typer.echo(f"Done  {xp}")

if __name__ == "__main__":
    app()
