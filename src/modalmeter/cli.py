"""Thin command-line wrappers for the shared CPU inspection and report APIs."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from modalmeter import __version__
from modalmeter.errors import InspectionError, InvalidInput
from modalmeter.schemas import MODEL_ID, MODEL_REVISION, InspectionConfig

_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "modalmeter"

app = typer.Typer(
    help="Inspect multimodal inputs on CPU and render portable offline reports.",
    add_completion=False,
    invoke_without_command=True,
    pretty_exceptions_enable=False,
)


def _version(value: bool) -> None:
    if value:
        typer.echo(f"modalmeter {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_version, is_eager=True, help="Show the version and exit."
        ),
    ] = False,
) -> None:
    """Show implemented commands. Endpoint benchmarking remains a later milestone."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@contextmanager
def _errors() -> Iterator[None]:
    """Keep private paths, prompt contents, and upstream exception payloads out of stderr."""
    from modalmeter.report import _clean_text

    try:
        yield
    except InvalidInput as exc:
        typer.echo(f"Error: {_clean_text(str(exc))}", err=True)
        raise typer.Exit(2) from None
    except ValidationError as exc:
        errors = exc.errors(include_input=False, include_context=False, include_url=False)
        message = str(errors[0]["msg"]) if errors else "Invalid configuration."
        typer.echo(f"Error: {_clean_text(message)}", err=True)
        raise typer.Exit(2) from None
    except ValueError:
        typer.echo(
            "Error: Invalid configuration or result; check the command help and schema.", err=True
        )
        raise typer.Exit(2) from None
    except InspectionError as exc:
        typer.echo(f"Error: {_clean_text(str(exc))}", err=True)
        raise typer.Exit(1) from None
    except KeyboardInterrupt:
        typer.echo("Interrupted. No incomplete result was published.", err=True)
        raise typer.Exit(130) from None
    except Exception:
        typer.echo(
            "Error: Operation failed. Check input access, disk space, and dependency versions. "
            "Private input details were omitted.",
            err=True,
        )
        raise typer.Exit(1) from None


@app.command("prepare")
def prepare(
    cache_dir: Annotated[
        Path,
        typer.Option(
            help="Processor artifact cache directory.", show_default="~/.cache/modalmeter"
        ),
    ] = _DEFAULT_CACHE_DIR,
    processor_dir: Annotated[
        Path | None,
        typer.Option(help="Verify an existing directory of exactly the allowlisted files."),
    ] = None,
    offline: Annotated[
        bool, typer.Option(help="Verify cached artifacts without network access.")
    ] = False,
    model: Annotated[str, typer.Option(help="Supported processor model ID.")] = MODEL_ID,
    revision: Annotated[
        str, typer.Option(help="Supported immutable processor revision.")
    ] = MODEL_REVISION,
) -> None:
    """Download or verify eight processor artifacts; never download model weights."""
    from modalmeter.artifacts import artifact_summary, resolve_processor_artifacts

    with _errors():
        resolved = resolve_processor_artifacts(
            cache_dir=cache_dir,
            model_id=model,
            revision=revision,
            offline=offline,
            processor_dir=processor_dir,
        )
        typer.echo(artifact_summary(resolved))


def _prompt(path: Path | None, max_bytes: int) -> str:
    if path is None:
        return "Describe this media."
    if path.is_symlink() or not path.is_file():
        raise InvalidInput("Prompt file must be a regular UTF-8 text file.")
    try:
        with path.open("rb") as handle:
            data = handle.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise InvalidInput("Prompt exceeds the configured UTF-8 byte limit.")
        return data.decode("utf-8")
    except UnicodeError as exc:
        raise InvalidInput("Prompt file must contain valid UTF-8 text.") from exc
    except OSError as exc:
        raise InvalidInput("Could not read the supplied prompt file.") from exc


@app.command("inspect")
def inspect_command(
    path: Annotated[
        Path, typer.Argument(help="Local image or video; remote URLs are unsupported.")
    ],
    output: Annotated[Path, typer.Option("--output", "-o", help="New inspection run directory.")],
    processor_dir: Annotated[
        Path | None, typer.Option(help="Existing verified processor files.")
    ] = None,
    cache_dir: Annotated[
        Path,
        typer.Option(
            help="Processor artifact cache directory.", show_default="~/.cache/modalmeter"
        ),
    ] = _DEFAULT_CACHE_DIR,
    offline: Annotated[bool, typer.Option(help="Require cached processor artifacts.")] = False,
    model: Annotated[str, typer.Option(help="Supported processor model ID.")] = MODEL_ID,
    revision: Annotated[str, typer.Option(help="Immutable processor revision.")] = MODEL_REVISION,
    sampling: Annotated[
        str, typer.Option(help="model-default or uniform (video only).")
    ] = "model-default",
    frames: Annotated[
        int | None, typer.Option(min=1, help="Requested uniform video frame budget.")
    ] = None,
    pixel_budget: Annotated[
        int | None, typer.Option(min=1, help="Explicit processor pixel budget.")
    ] = None,
    prompt_file: Annotated[
        Path | None, typer.Option(help="UTF-8 prompt file; text is never retained.")
    ] = None,
    include_media: Annotated[
        bool, typer.Option(help="Opt into bounded embedded thumbnails.")
    ] = False,
    overwrite: Annotated[
        bool, typer.Option(help="Replace a complete ModalMeter-owned run only.")
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Print the sanitized result JSON.")
    ] = False,
    max_file_bytes: Annotated[int, typer.Option(min=1, help="Maximum encoded source bytes.")] = 256
    * 1024**2,
    max_pixels: Annotated[
        int, typer.Option(min=1, help="Maximum decoded pixels per source frame.")
    ] = 16_777_216,
    max_frames: Annotated[int, typer.Option(min=1, help="Maximum selected frame count.")] = 128,
    max_decoded_frames: Annotated[
        int, typer.Option(min=1, help="Maximum decoded source frames.")
    ] = 10_000,
    max_decoded_bytes: Annotated[
        int, typer.Option(min=1, help="Maximum retained decoded frame bytes.")
    ] = 256 * 1024**2,
    max_decode_seconds: Annotated[
        float,
        typer.Option(
            min=0.001,
            help="Cooperative media-preparation deadline in seconds; checked between frames.",
        ),
    ] = 30.0,
    max_tensor_bytes: Annotated[
        int, typer.Option(min=1, help="Maximum processor tensor budget.")
    ] = 256 * 1024**2,
    max_prompt_bytes: Annotated[
        int, typer.Option(min=1, help="Maximum UTF-8 prompt bytes.")
    ] = 16_384,
) -> None:
    """Inspect one image/video with the pinned real processor on CPU, without weights."""
    from modalmeter.storage import sanitized_result, validate_output_directory, write_inspection_run

    with _errors():
        validate_output_directory(output, overwrite=overwrite)
        config = InspectionConfig.model_validate(
            {
                "path": path,
                "model_id": model,
                "revision": revision,
                "processor_dir": processor_dir,
                "cache_dir": cache_dir,
                "offline": offline,
                "sampling": sampling,
                "frames": frames,
                "pixel_budget": pixel_budget,
                "prompt": _prompt(prompt_file, max_prompt_bytes),
                "include_media": include_media,
                "max_file_bytes": max_file_bytes,
                "max_pixels": max_pixels,
                "max_frames": max_frames,
                "max_decoded_frames": max_decoded_frames,
                "max_decoded_bytes": max_decoded_bytes,
                "max_decode_seconds": max_decode_seconds,
                "max_tensor_bytes": max_tensor_bytes,
                "max_prompt_bytes": max_prompt_bytes,
            }
        )
        from modalmeter.inspect import inspect_media

        result = inspect_media(config)
        write_inspection_run(result, output, overwrite=overwrite, include_media=include_media)
        if json_output:
            typer.echo(
                sanitized_result(result, include_media=include_media).model_dump_json(indent=2)
            )
        else:
            tokens = result.token_accounting
            typer.echo(
                f"Inspection complete: {result.manifest.kind}; "
                f"{tokens.visual_placeholder_positions.value} visual placeholder positions; "
                f"{tokens.nonpadding_prompt_positions.value} non-padding prompt positions."
            )
            typer.echo(
                "Wrote inspection.json, manifest.json, and report.html to the requested output."
            )
            typer.echo("Serving parity remains unverified; no latency or GPU memory was measured.")


@app.command("report")
def report_command(
    source: Annotated[Path, typer.Argument(help="Stored run directory or result JSON file.")],
    output: Annotated[Path, typer.Option("--output", "-o", help="HTML output file.")],
    include_media: Annotated[
        bool, typer.Option(help="Show thumbnails only if already stored.")
    ] = False,
    overwrite: Annotated[
        bool, typer.Option(help="Replace the requested existing HTML file.")
    ] = False,
) -> None:
    """Render stored result data offline; no inspection extra or processor is needed."""
    from modalmeter.storage import load_result, write_html_report

    with _errors():
        result = load_result(source)
        write_html_report(result, output, overwrite=overwrite, include_media=include_media)
        typer.echo("Wrote the self-contained HTML report to the requested output.")


@app.command("compare")
def compare_command(
    sources: Annotated[
        list[Path], typer.Argument(help="Two to eight inspection runs or JSON files.")
    ],
    output: Annotated[Path, typer.Option("--output", "-o", help="New comparison run directory.")],
    include_media: Annotated[
        bool, typer.Option(help="Show thumbnails only if already stored.")
    ] = False,
    overwrite: Annotated[
        bool, typer.Option(help="Replace a complete ModalMeter-owned run only.")
    ] = False,
) -> None:
    """Compare input facts and derived token counts; latency and memory stay unavailable."""
    from modalmeter.storage import compare_runs, validate_output_directory, write_comparison_run

    with _errors():
        validate_output_directory(output, overwrite=overwrite)
        result = compare_runs(list(sources))
        write_comparison_run(result, output, overwrite=overwrite, include_media=include_media)
        label = (
            "compatible" if result.comparable else "incompatible; inspect the recorded differences"
        )
        typer.echo(f"Comparison written: {len(result.results)} inspections; baseline {label}.")
