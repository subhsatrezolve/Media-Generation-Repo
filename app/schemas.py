"""
Pydantic schemas for API request/response models.

This module contains all data models used for API validation and serialization.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class FreepikResource(str, Enum):
    text_to_image = "text-to-image"
    image_to_video = "image-to-video"
    video = "video"


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Service health status")


class FreepikProxyRequest(BaseModel):
    """Generic request payload passed directly to Freepik."""

    payload: dict[str, Any] = Field(default_factory=dict, description="Raw payload passed directly to Freepik")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "payload": {
                    "prompt": "Cinematic portrait lighting",
                    "aspect_ratio": "square_1_1",
                }
            }
        }
    )


class FreepikTaskResponse(BaseModel):
    """Generic response wrapper for direct Freepik task create/get calls."""

    model_config = ConfigDict(extra="allow")


class WaitTaskRequest(BaseModel):
    resource: FreepikResource
    model: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    timeout_seconds: int = Field(default=300, ge=5, le=1800)
    poll_interval_seconds: float = Field(default=4.0, ge=1.0, le=30.0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "resource": "text-to-image",
                "model": "flux-dev",
                "task_id": "task_123",
                "timeout_seconds": 300,
                "poll_interval_seconds": 3.0,
            }
        }
    )


class WaitTaskResponse(BaseModel):
    status: str = Field(description="Final task status")
    response: dict[str, Any] = Field(description="Raw task payload returned by Freepik")


class FreepikModelsResponse(BaseModel):
    text_to_image: list[str]
    image_to_video: list[str]
    video: list[str]
    notes: str


class FreepikImageGenerationRequest(BaseModel):
    """Request model for direct Freepik text-to-image generation."""

    prompt: str = Field(..., min_length=1, description="Text prompt for image generation.")
    model_name: str = Field(
        default="flux-dev",
        min_length=1,
        description="Freepik text-to-image model slug from Freepik docs (for example: 'flux-dev').",
    )
    extra_payload: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional extra model-specific payload fields passed through to Freepik.",
    )
    negative_prompt: Optional[str] = Field(
        default=None,
        description="Optional negative prompt (if supported by selected model).",
    )
    aspect_ratio: Optional[str] = Field(
        default="square_1_1",
        description="Optional aspect ratio key (for example: square_1_1, widescreen_16_9).",
    )
    num_images: int = Field(default=1, ge=1, le=4, description="Requested number of images.")
    style: Optional[str] = Field(default=None, description="Optional style hint.")
    filter_nsfw: Optional[bool] = Field(
        default=True,
        description="Optional NSFW filtering flag. Set only if endpoint supports it.",
    )
    poll: bool = Field(default=True, description="Whether to poll until completion.")
    poll_timeout_seconds: int = Field(default=60, ge=5, le=1800, description="Polling timeout in seconds.")
    poll_interval_seconds: float = Field(default=3.0, ge=0.5, le=10.0, description="Polling interval in seconds.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "prompt": "A futuristic eco-friendly city at sunrise, ultra detailed",
                "model_name": "flux-dev",
                "aspect_ratio": "square_1_1",
                "num_images": 1,
                "filter_nsfw": True,
                "poll": True,
            }
        }
    )


class FreepikImageGenerationResponse(BaseModel):
    type: str
    provider: str
    model: str
    task_id: str
    status: str
    image_urls: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class FreepikVideoGenerationRequest(BaseModel):
    """Request model for direct Freepik image-to-video generation."""

    image: str = Field(..., min_length=1, description="Source image URL or base64.")
    prompt: str = Field(..., min_length=1, description="Motion prompt for the video.")
    model_name: str = Field(
        default="seedance-lite-1080p",
        min_length=1,
        description="Freepik image-to-video model slug.",
    )
    endpoint_path: Optional[str] = Field(
        default=None,
        description="Optional create endpoint path override.",
    )
    task_endpoint_path: Optional[str] = Field(
        default=None,
        description="Optional polling endpoint path override. Use '{task_id}' placeholder if needed.",
    )
    extra_payload: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional extra model-specific payload fields passed through to Freepik.",
    )
    duration_seconds: int = Field(default=5, ge=1, le=30, description="Target duration hint.")
    aspect_ratio: Optional[str] = Field(default="widescreen_16_9", description="Optional aspect ratio key.")
    camera_fixed: bool = Field(default=False, description="Whether camera should stay fixed.")
    poll: bool = Field(default=True, description="Whether to poll until completion.")
    poll_timeout_seconds: int = Field(default=300, ge=5, le=1800, description="Polling timeout in seconds.")
    poll_interval_seconds: float = Field(default=3.0, ge=0.5, le=10.0, description="Polling interval in seconds.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "image": "https://example.com/source.png",
                "prompt": "Subtle camera dolly-in with light particles",
                "model_name": "seedance-lite-1080p",
                "poll": True,
            }
        }
    )


class FreepikVideoGenerationResponse(BaseModel):
    type: str
    provider: str
    model: str
    task_id: str
    status: str
    video_urls: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class EditImageRequest(BaseModel):
    """Request model for Freepik seedream-v4-edit."""

    prompt: str = Field(min_length=1)
    reference_images: list[str] | None = None
    aspect_ratio: str = "square_1_1"
    guidance_scale: float = 2.5
    seed: int | None = None
    poll: bool = True
    poll_timeout_seconds: int = Field(default=60, ge=5, le=1800)
    poll_interval_seconds: float = Field(default=3.0, ge=1.0, le=30.0)


class EditImageResponse(BaseModel):
    type: str
    provider: str
    model: str
    task_id: str
    status: str
    image_urls: list[str] = Field(default_factory=list)
    error: str | None = None


class HiggsfieldGenerateByModelRequest(BaseModel):
    args: dict[str, Any] = Field(default_factory=dict, description="Model arguments expected by Higgsfield")


class HiggsfieldRequestStatusResponse(BaseModel):
    request_id: str | None = None
    status: str | None = None
    output: dict[str, Any] | list[Any] | str | None = None
    error: dict[str, Any] | str | None = None
    model_config = ConfigDict(extra="allow")


class HiggsfieldWaitRequest(BaseModel):
    request_id: str = Field(min_length=1)
    timeout_seconds: int = Field(default=300, ge=5, le=1800)
    poll_interval_seconds: float = Field(default=3.0, ge=0.5, le=30.0)


class HiggsfieldGenerateImageRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    model_id: str = Field(default="higgsfield-ai/soul/standard", min_length=1)
    aspect_ratio: str | None = None
    seed: int | None = None
    extra_args: dict[str, Any] | None = None
    poll: bool = True
    poll_timeout_seconds: int = Field(default=300, ge=5, le=1800)
    poll_interval_seconds: float = Field(default=3.0, ge=0.5, le=30.0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "prompt": "fashion portrait, studio light",
                "model_id": "higgsfield-ai/soul/standard",
                "aspect_ratio": "9:16",
                "poll": True,
            }
        }
    )


class HiggsfieldGenerateVideoRequest(BaseModel):
    image_url: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)
    model_id: str = Field(default="higgsfield-ai/dop/standard", min_length=1)
    extra_args: dict[str, Any] | None = None
    poll: bool = True
    poll_timeout_seconds: int = Field(default=300, ge=5, le=1800)
    poll_interval_seconds: float = Field(default=3.0, ge=0.5, le=30.0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "image_url": "https://example.com/source.png",
                "prompt": "camera slowly circles subject",
                "model_id": "higgsfield-ai/dop/standard",
                "poll": True,
            }
        }
    )


class HiggsfieldGenerationResponse(BaseModel):
    type: str
    provider: str
    model_id: str
    request_id: str
    status: str
    output: dict[str, Any] | list[Any] | str | None = None
    image_urls: list[str] = Field(default_factory=list)
    video_urls: list[str] = Field(default_factory=list)
    error: str | None = None
    response: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)


class HiggsfieldModelsResponse(BaseModel):
    image_models: list[str]
    video_models: list[str]
    notes: str


# Backward-compatible aliases used by existing routes.
GenerateImageRequest = FreepikImageGenerationRequest
GenerateVideoRequest = FreepikVideoGenerationRequest

