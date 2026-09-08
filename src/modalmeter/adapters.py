"""One pinned CPU processor adapter; no model weights or server transport."""

import hashlib
import importlib
import importlib.metadata
import math
import platform
import re
from typing import Any, Literal

from modalmeter.artifacts import ResolvedArtifacts
from modalmeter.errors import InspectionError, InvalidInput, MissingExtra
from modalmeter.media import LoadedMedia
from modalmeter.schemas import (
    Compatibility,
    EvidenceKind,
    InspectionConfig,
    Measurement,
    ProcessorProvenance,
    TokenAccounting,
)

ADAPTER_VERSION = "qwen3-vl-native/1"
_PINNED = {
    "transformers": "4.57.6",
    "torch": "2.9.1",
    "torchvision": "0.24.1",
    "pillow": "12.0.0",
    "av": "16.1.0",
}


def observed(value: int, *, source: str, method: str, unit: str = "positions") -> Measurement:
    return Measurement(
        value=value,
        unit=unit,
        evidence_kind=EvidenceKind.OBSERVED,
        source=source,
        scope="one processed media prompt",
        method=method,
    )


def unavailable(reason: str, *, unit: str = "positions") -> Measurement:
    return Measurement(
        value=None,
        unit=unit,
        evidence_kind=EvidenceKind.UNAVAILABLE,
        source="ModalMeter CPU inspection",
        scope="one inspection",
        method="not captured",
        unavailable_reason=reason,
    )


def _row(values: Any) -> list[int]:
    if hasattr(values, "tolist"):
        values = values.tolist()
    if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], list):
        raise InvalidInput("Token accounting requires exactly one processed prompt.")
    return [int(value) for value in values[0]]


def account_tokens(processor: Any, batch: Any, modality: str) -> TokenAccounting:
    """Count actual known token IDs; never count strings or padded tensor width."""
    ids = _row(batch["input_ids"])
    mask = _row(batch["attention_mask"]) if "attention_mask" in batch else None
    if mask is not None and (len(mask) != len(ids) or any(value not in (0, 1) for value in mask)):
        raise InspectionError("Processor attention mask has an unsupported shape or values.")
    active = mask if mask is not None else [1] * len(ids)
    token_id = int(processor.image_token_id if modality == "image" else processor.video_token_id)
    indices = [
        index
        for index, (token, keep) in enumerate(zip(ids, active, strict=True))
        if keep and token == token_id
    ]
    grid_name = "image_grid_thw" if modality == "image" else "video_grid_thw"
    grids = batch[grid_name].tolist()
    if len(grids) != 1 or len(grids[0]) != 3:
        raise InspectionError("Processor returned an unsupported media grid shape.")
    grid = [int(value) for value in grids[0]]
    component = processor.image_processor if modality == "image" else processor.video_processor
    grid_product = math.prod(grid)
    tensor_name = "pixel_values" if modality == "image" else "pixel_values_videos"
    encoder_positions = int(batch[tensor_name].shape[0])
    merge_length = int(component.merge_size) ** 2
    grid_count = grid_product // merge_length
    boundaries = sum(
        keep and token in (processor.vision_start_token_id, processor.vision_end_token_id)
        for token, keep in zip(ids, active, strict=True)
    )
    prompt_length = (
        observed(sum(mask), source="processor attention_mask", method="Sum non-padding positions.")
        if mask is not None
        else unavailable("Processor did not return an attention mask.")
    )
    residual = (
        Measurement(
            value=sum(mask) - len(indices),
            unit="positions",
            evidence_kind=EvidenceKind.DERIVED,
            source="attention_mask and input_ids",
            scope="one processed media prompt",
            method="Non-padding prompt positions minus visual placeholder positions; includes "
            "chat template, timestamps and structural tokens, not just user text.",
        )
        if mask is not None
        else unavailable("A non-padding prompt length was not available.")
    )
    return TokenAccounting(
        encoder_grid_positions=observed(
            encoder_positions,
            source=tensor_name,
            method="Read the actual emitted patch tensor row count (shape[0]).",
        ),
        visual_placeholder_positions=observed(
            len(indices),
            source="processor input_ids",
            method=f"Count token ID {token_id} at active attention-mask positions.",
        ),
        grid_derived_visual_positions=Measurement(
            value=grid_count,
            unit="positions",
            evidence_kind=EvidenceKind.DERIVED,
            source=grid_name,
            scope="one processed media prompt",
            method="grid_t * grid_h * grid_w / merge_size^2; checked against placeholder IDs.",
        ),
        nonpadding_prompt_positions=prompt_length,
        nonvisual_prompt_positions=residual,
        vision_boundary_positions=observed(
            boundaries,
            source="processor input_ids",
            method="Count known vision-start and vision-end token IDs at active positions.",
        ),
        video_timestamp_positions=(
            observed(
                0,
                source="image modality",
                method="Image prompts have no video timestamp insertion.",
            )
            if modality == "image"
            else unavailable(
                "Timestamp tokens are not isolated; included in the nonvisual residual."
            )
        ),
        user_text_positions=unavailable(
            "User text is not isolated from template/structure; use the nonvisual residual."
        ),
        server_prompt_usage=unavailable("No serving endpoint was contacted.", unit="tokens"),
        server_completion_usage=unavailable("No serving endpoint was contacted.", unit="tokens"),
        placeholder_token_id=token_id,
        observed_placeholder_indices=indices,
        grid_matches_placeholders=(
            encoder_positions == grid_product
            and grid_product % merge_length == 0
            and grid_count == len(indices)
        ),
    )


class QwenProcessorAdapter:
    def __init__(self, config: InspectionConfig, artifacts: ResolvedArtifacts):
        self.config = config
        self.artifacts = artifacts
        versions: dict[str, str] = {}
        try:
            for name, expected in _PINNED.items():
                versions[name] = importlib.metadata.version(name)
                if versions[name].split("+")[0] != expected:
                    raise InvalidInput(f"The verified adapter requires {name}=={expected}.")
            for name in ("numpy", "tokenizers", "huggingface-hub"):
                versions[name] = importlib.metadata.version(name)
            transformers = importlib.import_module("transformers")
            self.processor: Any = transformers.AutoProcessor.from_pretrained(
                str(artifacts.directory),
                local_files_only=True,
                trust_remote_code=False,
            )
        except (ImportError, importlib.metadata.PackageNotFoundError) as exc:
            raise MissingExtra(
                "Inspection requires the inspect extra: run 'uv sync --extra inspect' "
                "or install 'modalmeter[inspect]'."
            ) from exc
        self.versions = versions
        self.runtime = {
            "system": platform.system(),
            "os_version": platform.mac_ver()[0]
            if platform.system() == "Darwin"
            else platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "device": "cpu",
        }
        if any(
            marker in config.prompt
            for marker in [
                *self.processor.tokenizer.all_special_tokens,
                "<|placeholder|>",
            ]
        ):
            raise InvalidInput("Prompt contains reserved tokenizer markers; supply plain text.")

    def default_frame_indices(self, count: int, fps: float) -> list[int]:
        metadata_class = importlib.import_module("transformers.video_utils").VideoMetadata
        metadata = metadata_class(total_num_frames=count, fps=fps)
        with importlib.import_module("torch").device("cpu"):
            return [int(index) for index in self.processor.video_processor.sample_frames(metadata)]

    def _configure_and_bound(self, media: LoadedMedia) -> None:
        component = (
            self.processor.image_processor
            if media.manifest.kind == "image"
            else self.processor.video_processor
        )
        if self.config.pixel_budget is not None:
            if self.config.pixel_budget < int(component.size["shortest_edge"]):
                raise InvalidInput(
                    f"Pixel budget must be at least {component.size['shortest_edge']} "
                    "for this modality."
                )
            component.size = {**component.size, "longest_edge": self.config.pixel_budget}
        try:
            if media.manifest.kind == "image":
                resize = importlib.import_module(
                    "transformers.models.qwen2_vl.image_processing_qwen2_vl_fast"
                ).smart_resize
                height, width = resize(
                    media.manifest.oriented_height,
                    media.manifest.oriented_width,
                    factor=component.patch_size * component.merge_size,
                    min_pixels=component.size["shortest_edge"],
                    max_pixels=component.size["longest_edge"],
                )
                frames = int(component.temporal_patch_size)
                input_bytes = media.manifest.oriented_width * media.manifest.oriented_height * 3
            else:
                resize = importlib.import_module(
                    "transformers.models.qwen3_vl.video_processing_qwen3_vl"
                ).smart_resize
                height, width = resize(
                    num_frames=int(media.content.shape[0]),
                    height=media.manifest.oriented_height,
                    width=media.manifest.oriented_width,
                    temporal_factor=component.temporal_patch_size,
                    factor=component.patch_size * component.merge_size,
                    min_pixels=component.size["shortest_edge"],
                    max_pixels=component.size["longest_edge"],
                )
                frames = media.manifest.processed_frame_count
                input_bytes = int(media.content.nbytes)
        except ValueError as exc:
            raise InvalidInput(f"Unsupported input geometry/aspect ratio: {exc}") from exc
        # Conservative working-tensor allowance, not a claim about process RSS or GPU memory.
        predicted_working_bytes = int(height) * int(width) * frames * 3 * 4 * 4 + input_bytes * 4
        if predicted_working_bytes > self.config.max_tensor_bytes:
            raise InvalidInput(
                "Processor working-tensor budget exceeded. Use fewer frames or a smaller "
                "--pixel-budget, or explicitly increase max_tensor_bytes in the Python config."
            )

    def process(self, media: LoadedMedia) -> tuple[Any, str]:
        with importlib.import_module("torch").device("cpu"):
            return self._process_cpu(media)

    def _process_cpu(self, media: LoadedMedia) -> tuple[Any, str]:
        self._configure_and_bound(media)
        prompt: str = self.processor.apply_chat_template(
            [
                {
                    "role": "user",
                    "content": [
                        {"type": media.manifest.kind},
                        {"type": "text", "text": self.config.prompt},
                    ],
                }
            ],
            tokenize=False,
            add_generation_prompt=True,
        )
        if media.manifest.kind == "image":
            batch = self.processor(
                text=[prompt], images=[media.content], return_attention_mask=True
            )
        else:
            metadata_class = importlib.import_module("transformers.video_utils").VideoMetadata
            indices = [frame.ordinal for frame in media.manifest.selected_frames]
            if len(indices) == 1:
                indices = (
                    indices * 2
                )  # Explicit short-video repair already recorded in the manifest.
            metadata = metadata_class(
                total_num_frames=media.manifest.source_frame_count,
                fps=media.manifest.average_fps,
                frames_indices=indices.copy(),
                height=media.manifest.source_height,
                width=media.manifest.source_width,
            )
            # Keep metadata and Python token lists in the SAME upstream call. No tensor
            # conversion of metadata, duplicate processing, hooks or monkey-patching.
            batch = self.processor(
                text=[prompt],
                videos=[media.content],
                video_metadata=[metadata],
                do_sample_frames=False,
                return_metadata=True,
                return_tensors=None,
                return_attention_mask=True,
            )
            expected = [frame.source_ordinal for frame in media.manifest.processed_frames]
            if list(batch["video_metadata"][0].frames_indices) != expected:
                raise InspectionError(
                    "Observed processor frame padding disagrees with the media manifest."
                )
        template = self.processor.chat_template
        if not isinstance(template, str):
            raise InspectionError("Pinned processor template has an unexpected type.")
        return batch, hashlib.sha256(template.encode()).hexdigest()

    def provenance(self, modality: str) -> ProcessorProvenance:
        component = (
            self.processor.image_processor
            if modality == "image"
            else self.processor.video_processor
        )
        settings = {
            name: getattr(component, name)
            for name in (
                "size",
                "patch_size",
                "temporal_patch_size",
                "merge_size",
                "do_resize",
                "do_rescale",
                "rescale_factor",
                "do_normalize",
                "image_mean",
                "image_std",
                "do_convert_rgb",
            )
        }
        settings["resample"] = int(component.resample)
        settings["processor_class"] = type(component).__name__
        settings["device"] = "cpu"
        if modality == "video":
            settings.update(
                {
                    "sampling_owner": "ModalMeter: native default indices or uniform PTS",
                    "do_sample_frames": False,
                    "native_default_fps": component.fps,
                    "native_min_frames": component.min_frames,
                    "native_max_frames": component.max_frames,
                    "timestamp_basis": "ordinal / nominal FPS; native grouped/rounded labels",
                }
            )
        return ProcessorProvenance(
            model_id=self.config.model_id,
            revision=self.config.revision,
            adapter_version=ADAPTER_VERSION,
            dependency_versions=self.versions,
            artifact_sha256=self.artifacts.hashes,
            effective_settings=settings,
            runtime=self.runtime,
        )

    def compatibility(self, modality: Literal["image", "video"], matches: bool) -> Compatibility:
        # A versioned local reference-suite claim, distinct from each runtime accounting check.
        verified_tuple = (
            self.runtime["system"] == "Darwin"
            and self.runtime["os_version"] == "26.6.2"
            and self.runtime["machine"] == "arm64"
            and self.runtime["python"] == "3.12.11"
            and self.versions["numpy"] == "2.5.3"
            and self.versions["tokenizers"] == "0.22.2"
            and self.versions["huggingface-hub"] == "0.36.2"
        )
        state: Literal["not_run", "processor_verified", "processor_mismatch"] = (
            "processor_mismatch"
            if not matches
            else "processor_verified"
            if verified_tuple
            else "not_run"
        )
        return Compatibility(
            modality=modality,
            processor_verification=state,
            processor_evidence=(
                "Pinned adapter compared with unmodified CPU processor in tests/test_processor.py; "
                "see docs/evidence/m1 and docs/evidence/m2 for exact cases and limits. "
                "This run also compares emitted grid counts with actual active placeholder IDs."
                if verified_tuple
                else "Runtime grid/ID accounting checked; the complete OS/Python/dependency tuple "
                "has no recorded independent reference-suite run."
            ),
        )

    def group_labels(self, batch: Any) -> list[str]:
        decoded: str = self.processor.tokenizer.decode(_row(batch["input_ids"]))
        return re.findall(r"<[-0-9.]+ seconds>(?=<\|vision_start\|>)", decoded)
