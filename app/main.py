from fastapi import FastAPI, HTTPException

from .config import get_settings
from .schemas import (
    FreepikImageGenerationResponse,
    FreepikVideoGenerationResponse,
    GenerateImageRequest,
    GenerateVideoRequest,
    HealthResponse,
    HiggsfieldGenerateImageRequest,
    HiggsfieldGenerateVideoRequest,
    HiggsfieldGenerationResponse,
)
from .services.freepik_client import generate_image, generate_video
from .services.higgsfield_client import generate_image as higgsfield_generate_image
from .services.higgsfield_client import generate_video as higgsfield_generate_video


app = FastAPI(title=get_settings().app_name, version=get_settings().app_version)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/v1/freepik/generate-image", response_model=FreepikImageGenerationResponse)
async def generate_image_route(body: GenerateImageRequest) -> dict:
    try:
        return await generate_image(
            prompt=body.prompt,
            model_name=body.model_name,
            extra_payload=body.extra_payload,
            negative_prompt=body.negative_prompt,
            aspect_ratio=body.aspect_ratio,
            num_images=body.num_images,
            style=body.style,
            filter_nsfw=body.filter_nsfw,
            poll=body.poll,
            poll_timeout_seconds=body.poll_timeout_seconds,
            poll_interval_seconds=body.poll_interval_seconds,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/freepik/generate-video", response_model=FreepikVideoGenerationResponse)
async def generate_video_route(body: GenerateVideoRequest) -> dict:
    try:
        return await generate_video(
            image=body.image,
            prompt=body.prompt,
            model_name=body.model_name,
            endpoint_path=body.endpoint_path,
            task_endpoint_path=body.task_endpoint_path,
            extra_payload=body.extra_payload,
            duration_seconds=body.duration_seconds,
            aspect_ratio=body.aspect_ratio,
            camera_fixed=body.camera_fixed,
            poll=body.poll,
            poll_timeout_seconds=body.poll_timeout_seconds,
            poll_interval_seconds=body.poll_interval_seconds,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/higgsfield/generate-image", response_model=HiggsfieldGenerationResponse)
async def higgsfield_generate_image_route(body: HiggsfieldGenerateImageRequest) -> dict:
    try:
        return await higgsfield_generate_image(
            prompt=body.prompt,
            model_id=body.model_id,
            aspect_ratio=body.aspect_ratio,
            seed=body.seed,
            extra_args=body.extra_args,
            poll=body.poll,
            poll_timeout_seconds=body.poll_timeout_seconds,
            poll_interval_seconds=body.poll_interval_seconds,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/higgsfield/generate-video", response_model=HiggsfieldGenerationResponse)
async def higgsfield_generate_video_route(body: HiggsfieldGenerateVideoRequest) -> dict:
    try:
        return await higgsfield_generate_video(
            image_url=body.image_url,
            prompt=body.prompt,
            model_id=body.model_id,
            extra_args=body.extra_args,
            poll=body.poll,
            poll_timeout_seconds=body.poll_timeout_seconds,
            poll_interval_seconds=body.poll_interval_seconds,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
