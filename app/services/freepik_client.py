"""
Freepik API client for image and video generation.
"""

import asyncio
import json
import os
import re
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

FREEPIK_API_BASE_URL = os.getenv("FREEPIK_API_BASE_URL", "https://api.freepik.com").rstrip("/")
FREEPIK_API_KEY = os.getenv("FREEPIK_API_KEY")
FREEPIK_DEFAULT_IMAGE_URL = os.getenv("FREEPIK_DEFAULT_IMAGE_URL", "https://d3u0tzju9qaucj.cloudfront.net/49383509-d21f-4835-962a-7467c3c7a063/d7b4a329-e3b0-49c4-b473-2d998b232fc9.png")
FREEPIK_DEFAULT_VIDEO_URL = os.getenv("FREEPIK_DEFAULT_VIDEO_URL", "https://samplelib.com/lib/preview/mp4/sample-5s.mp4")
FREEPIK_DEFAULT_AUDIO_URL = os.getenv("FREEPIK_DEFAULT_AUDIO_URL", "https://samplelib.com/lib/preview/mp3/sample-3s.mp3")

FREEPIK_VALID_STYLES = frozenset(
    {
        "photo",
        "digital-art",
        "3d",
        "painting",
        "low-poly",
        "pixel-art",
        "anime",
        "cyberpunk",
        "comic",
        "vintage",
        "cartoon",
        "vector",
        "studio-shot",
        "dark",
        "sketch",
        "mockup",
        "2000s-pone",
        "70s-vibe",
        "watercolor",
        "art-nouveau",
        "origami",
        "surreal",
        "fantasy",
        "traditional-japan",
    }
)

FREEPIK_STYLE_ALIASES = {
    "illustration": "cartoon",
    "illustrations": "cartoon",
    "realistic": "photo",
    "realism": "photo",
    "drawing": "sketch",
    "digital": "digital-art",
}

FREEPIK_ASPECT_RATIO_TO_RATIO = {
    "square_1_1": "1:1",
    "widescreen_16_9": "16:9",
    "portrait_9_16": "9:16",
    "landscape_4_3": "4:3",
    "portrait_3_4": "3:4",
    "portrait_2_3": "2:3",
    "landscape_3_2": "3:2",
}

FREEPIK_RUNWAY_RATIO_MAP = {
    "square_1_1": "1024:1024",
    "widescreen_16_9": "1920:1080",
    "portrait_9_16": "1080:1920",
    "landscape_4_3": "1440:1080",
    "portrait_3_4": "1080:1440",
    "portrait_2_3": "1168:880",
    "landscape_3_2": "1360:768",
}


class FreepikAPIError(RuntimeError):
    """Structured Freepik API error with status/body for adaptive retries."""

    def __init__(self, status_code: int, response_text: str):
        self.status_code = status_code
        self.response_text = response_text
        self.response_json: Optional[Dict[str, Any]] = None
        try:
            parsed = json.loads(response_text)
            if isinstance(parsed, dict):
                self.response_json = parsed
        except Exception:
            self.response_json = None
        super().__init__(f"Freepik API error {status_code}: {response_text[:200]}")


async def _post_json(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not FREEPIK_API_KEY:
        raise RuntimeError("FREEPIK_API_KEY is not configured.")

    url = f"{FREEPIK_API_BASE_URL}{path}"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-freepik-api-key": FREEPIK_API_KEY,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        # Retry transient upstream errors once (e.g. occasional 504 gateway timeout).
        for attempt in range(2):
            resp = await client.post(url, json=payload, headers=headers)
            text = resp.text
            if resp.status_code == 200:
                try:
                    return resp.json()
                except Exception as exc:
                    raise RuntimeError(f"Failed to parse JSON response: {exc}") from exc

            if resp.status_code in {502, 503, 504} and attempt == 0:
                await asyncio.sleep(1.0)
                continue

            raise FreepikAPIError(resp.status_code, text)

    raise RuntimeError("Unexpected Freepik POST flow")


async def _get_json(path: str) -> Dict[str, Any]:
    if not FREEPIK_API_KEY:
        raise RuntimeError("FREEPIK_API_KEY is not configured.")

    url = f"{FREEPIK_API_BASE_URL}{path}"
    headers = {
        "Accept": "application/json",
        "x-freepik-api-key": FREEPIK_API_KEY,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(url, headers=headers)
        text = resp.text
        if resp.status_code != 200:
            raise FreepikAPIError(resp.status_code, text)
        try:
            return resp.json()
        except Exception as exc:
            raise RuntimeError(f"Failed to parse JSON response: {exc}") from exc


def _extract_invalid_params(error_json: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not error_json:
        return []
    invalid = error_json.get("invalid_params")
    if isinstance(invalid, list):
        return [i for i in invalid if isinstance(i, dict)]
    return []


def _choices_from_reason(reason: str) -> list[str]:
    # Supports quoted enums and numeric hints like "Input should be 6".
    out = re.findall(r"'([^']+)'", reason or "")
    if out:
        return out
    return re.findall(r"\b\d+\b", reason or "")


async def _create_image_task_with_fallbacks(
    *,
    model: str,
    create_path: str,
    payload: Dict[str, Any],
    endpoint_was_overridden: bool,
) -> tuple[Dict[str, Any], str, Dict[str, Any]]:
    current_path = create_path
    current_payload = dict(payload)

    for _ in range(4):
        try:
            created = await _post_json(current_path, current_payload)
            return created, current_path, current_payload
        except FreepikAPIError as exc:
            if (
                exc.status_code == 404
                and not endpoint_was_overridden
                and current_path == f"/v1/ai/text-to-image/{model}"
            ):
                current_path = f"/v1/ai/{model}"
                continue

            if exc.status_code == 400 and exc.response_json:
                invalid_params = _extract_invalid_params(exc.response_json)
                required_fields: set[str] = set()
                for item in invalid_params:
                    field = item.get("field")
                    reason_l = str(item.get("reason") or "").lower()
                    if isinstance(field, str) and "required" in reason_l:
                        required_fields.add(field)

                adapted = False

                # Some text models require ratio instead of aspect_ratio.
                if "body.ratio" in required_fields and "ratio" not in current_payload:
                    aspect = current_payload.get("aspect_ratio")
                    if aspect:
                        aspect_key = str(aspect)
                        if model.lower() == "runway":
                            current_payload["ratio"] = FREEPIK_RUNWAY_RATIO_MAP.get(
                                aspect_key, "1024:1024"
                            )
                        else:
                            current_payload["ratio"] = FREEPIK_ASPECT_RATIO_TO_RATIO.get(
                                aspect_key, aspect_key
                            )
                        current_payload.pop("aspect_ratio", None)
                        adapted = True

                # Normalize aspect_ratio value to one of allowed choices from validation message.
                for item in invalid_params:
                    field = str(item.get("field") or "")
                    reason = str(item.get("reason") or "")
                    if field == "body.aspect_ratio":
                        choices = _choices_from_reason(reason)
                        if choices:
                            cur = str(current_payload.get("aspect_ratio") or "")
                            if cur in FREEPIK_ASPECT_RATIO_TO_RATIO:
                                mapped = FREEPIK_ASPECT_RATIO_TO_RATIO[cur]
                                if mapped in choices:
                                    current_payload["aspect_ratio"] = mapped
                                    adapted = True
                                elif choices:
                                    current_payload["aspect_ratio"] = choices[0]
                                    adapted = True
                            elif cur not in choices:
                                current_payload["aspect_ratio"] = choices[0]
                                adapted = True

                    if field == "body.input_image" and "required" in reason.lower():
                        # Map common aliases if caller provided another field name.
                        if "input_image" not in current_payload:
                            for alias in ("image", "image_url", "reference_image"):
                                if alias in current_payload:
                                    current_payload["input_image"] = current_payload[alias]
                                    adapted = True
                                    break

                if adapted:
                    continue

            raise

    raise RuntimeError("Unexpected Freepik image task creation flow.")


async def generate_image(
    prompt: str,
    *,
    model_name: str = "flux-dev",
    extra_payload: Optional[Dict[str, Any]] = None,
    negative_prompt: Optional[str] = None,
    aspect_ratio: Optional[str] = "square_1_1",
    num_images: int = 1,
    style: Optional[str] = None,
    filter_nsfw: Optional[bool] = True,
    poll: bool = True,
    poll_timeout_seconds: int = 60,
    poll_interval_seconds: float = 3.0,
) -> Dict[str, Any]:
    num_images = max(1, min(num_images, 4))
    model = (model_name or "flux-dev").strip() or "flux-dev"
    create_path = f"/v1/ai/text-to-image/{model}"

    payload: Dict[str, Any] = {"prompt": prompt}
    if aspect_ratio:
        payload["aspect_ratio"] = aspect_ratio
    if filter_nsfw is not None:
        payload["filter_nsfw"] = bool(filter_nsfw)
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt

    if style:
        normalized_style = FREEPIK_STYLE_ALIASES.get(style.strip().lower(), style.strip().lower())
        if normalized_style in FREEPIK_VALID_STYLES:
            payload["style"] = normalized_style

    if extra_payload:
        payload.update(extra_payload)

    created, resolved_create_path, resolved_payload = await _create_image_task_with_fallbacks(
        model=model,
        create_path=create_path,
        payload=payload,
        endpoint_was_overridden=False,
    )

    data = created.get("data") or {}
    task_id = data.get("task_id")
    status = data.get("status")

    if not task_id:
        raise RuntimeError(f"Freepik image generation ({model}) did not return a task_id.")

    summary: Dict[str, Any] = {
        "type": "image_generation",
        "provider": "freepik",
        "model": model,
        "task_id": task_id,
        "status": status or "CREATED",
        "image_urls": [],
        "meta": {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "filter_nsfw": bool(filter_nsfw) if filter_nsfw is not None else None,
            "model_name": model,
            "endpoint_path": resolved_create_path,
            "request_payload": resolved_payload,
            "num_images": num_images,
        },
    }

    if not poll:
        return summary

    resolved_task_path = f"{resolved_create_path.rstrip('/')}/{task_id}"
    deadline = asyncio.get_running_loop().time() + poll_timeout_seconds
    last_error: Optional[Exception] = None

    while asyncio.get_running_loop().time() < deadline:
        try:
            task = await _get_json(resolved_task_path)
            tdata = task.get("data") or task
            status = tdata.get("status") or status
            summary["status"] = status

            generated = tdata.get("generated") or []
            if status == "COMPLETED":
                urls: List[str] = []
                for item in generated:
                    if isinstance(item, dict):
                        url = item.get("url") or item.get("image_url")
                        if url:
                            urls.append(url)
                    elif isinstance(item, str):
                        urls.append(item)
                summary["image_urls"] = urls
                return summary

            if status == "FAILED":
                fail_msg = tdata.get("error") or tdata.get("message") or tdata.get("failure_reason")
                if fail_msg:
                    summary["error"] = fail_msg if isinstance(fail_msg, str) else str(fail_msg)
                return summary

            await asyncio.sleep(poll_interval_seconds)
            last_error = None
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(poll_interval_seconds)

    if last_error:
        summary["error"] = str(last_error)
    summary["status"] = status or "IN_PROGRESS"
    return summary


def _adapt_video_payload_from_validation(
    *,
    model: str,
    payload: dict[str, Any],
    invalid_params: list[dict[str, Any]],
) -> bool:
    adapted = False
    default_image = payload.get("image") or payload.get("image_url") or FREEPIK_DEFAULT_IMAGE_URL

    for item in invalid_params:
        field = str(item.get("field") or "")
        reason = str(item.get("reason") or "")
        reason_l = reason.lower()
        choices = _choices_from_reason(reason)

        if field.startswith("body.duration"):
            if choices:
                if payload.get("duration") != choices[0]:
                    payload["duration"] = choices[0]
                    adapted = True
            elif payload.get("duration") not in {"5", "10"}:
                payload["duration"] = "5"
                adapted = True

        elif field == "body.aspect_ratio" or field.endswith(".aspect_ratio"):
            current = str(payload.get("aspect_ratio") or "")
            symbolic_from_ratio = {
                "16:9": "widescreen_16_9",
                "9:16": "social_story_9_16",
                "1:1": "square_1_1",
            }
            if current in FREEPIK_ASPECT_RATIO_TO_RATIO:
                mapped = FREEPIK_ASPECT_RATIO_TO_RATIO[current]
                if mapped != current:
                    payload["aspect_ratio"] = mapped
                    adapted = True
                    current = mapped

            if choices and current in symbolic_from_ratio and symbolic_from_ratio[current] in choices:
                payload["aspect_ratio"] = symbolic_from_ratio[current]
                adapted = True
                current = payload["aspect_ratio"]

            if choices and current not in choices:
                payload["aspect_ratio"] = choices[0]
                adapted = True

        elif field == "body.ratio":
            ratio = payload.get("ratio")
            if ratio is None:
                aspect = str(payload.get("aspect_ratio") or "")
                if model.lower().startswith("runway"):
                    payload["ratio"] = FREEPIK_RUNWAY_RATIO_MAP.get(aspect, "1024:1024")
                else:
                    payload["ratio"] = FREEPIK_ASPECT_RATIO_TO_RATIO.get(aspect, aspect or "16:9")
                payload.pop("aspect_ratio", None)
                adapted = True
                ratio = payload.get("ratio")

            if choices and str(ratio) not in choices:
                payload["ratio"] = choices[0]
                adapted = True

        elif field == "body.image_url" and ("required" in reason_l or "missing" in reason_l):
            if "image_url" not in payload and "image" in payload:
                payload["image_url"] = payload["image"]
                adapted = True

        elif field == "body.image" and ("required" in reason_l or "missing" in reason_l):
            if "image" not in payload and "image_url" in payload:
                payload["image"] = payload["image_url"]
                adapted = True

        elif field == "body.first_frame" and ("required" in reason_l or "missing" in reason_l):
            if "first_frame" not in payload:
                payload["first_frame"] = default_image
                adapted = True

        elif field == "body.last_frame" and ("required" in reason_l or "missing" in reason_l):
            if "last_frame" not in payload:
                payload["last_frame"] = default_image
                adapted = True

        # Some responses require at least one frame; satisfy with first_frame.
        elif "at least one frame" in reason_l and "first_frame" not in payload and "last_frame" not in payload:
            payload["first_frame"] = default_image
            adapted = True

        elif field == "body.images" and ("required" in reason_l or "missing" in reason_l):
            if "images" not in payload:
                payload["images"] = [default_image]
                adapted = True

        elif field == "body.first_image_url" and ("required" in reason_l or "missing" in reason_l):
            if "first_image_url" not in payload:
                payload["first_image_url"] = default_image
                adapted = True

        elif field == "body.last_image_url" and ("required" in reason_l or "missing" in reason_l):
            if "last_image_url" not in payload:
                payload["last_image_url"] = default_image
                adapted = True

        elif field == "body.resolution" and ("required" in reason_l or "missing" in reason_l):
            if "resolution" not in payload:
                payload["resolution"] = "1080p"
                adapted = True

    return adapted


async def generate_video(
    image: str,
    prompt: str,
    *,
    model_name: str = "seedance-lite-1080p",
    endpoint_path: Optional[str] = None,
    task_endpoint_path: Optional[str] = None,
    extra_payload: Optional[Dict[str, Any]] = None,
    duration_seconds: int = 5,
    aspect_ratio: Optional[str] = "widescreen_16_9",
    camera_fixed: bool = False,
    poll: bool = True,
    poll_timeout_seconds: int = 60,
    poll_interval_seconds: float = 3.0,
) -> Dict[str, Any]:
    model = (model_name or "seedance-lite-1080p").strip() or "seedance-lite-1080p"
    create_path = (endpoint_path or f"/v1/ai/image-to-video/{model}").strip()
    if not create_path.startswith("/"):
        create_path = f"/{create_path}"
    endpoint_was_overridden = bool(endpoint_path and endpoint_path.strip())

    duration_str = "10" if duration_seconds >= 10 else "5"

    def _build_video_payload(use_video_namespace: bool) -> Dict[str, Any]:
        base: Dict[str, Any] = {
            "prompt": prompt,
            "duration": duration_str,
            "camera_fixed": bool(camera_fixed),
        }
        source_image = image or FREEPIK_DEFAULT_IMAGE_URL
        if use_video_namespace:
            base["image_url"] = source_image
        else:
            base["image"] = source_image
        if aspect_ratio:
            base["aspect_ratio"] = aspect_ratio
        if extra_payload:
            base.update(extra_payload)
        return base

    if endpoint_was_overridden:
        candidate_paths = [create_path]
    else:
        candidate_paths = [f"/v1/ai/image-to-video/{model}", f"/v1/ai/video/{model}"]

    created = None
    resolved_create_path = candidate_paths[0]
    payload: Dict[str, Any] = {}
    last_error: Optional[Exception] = None

    for candidate in candidate_paths:
        candidate_payload = _build_video_payload(
            use_video_namespace=candidate.startswith("/v1/ai/video/")
        )

        for _ in range(5):
            try:
                created = await _post_json(candidate, candidate_payload)
                resolved_create_path = candidate
                payload = candidate_payload
                break
            except FreepikAPIError as exc:
                last_error = exc

                if exc.status_code == 404 and not endpoint_was_overridden:
                    break

                if exc.status_code == 400:
                    invalid_params = _extract_invalid_params(exc.response_json)
                    if invalid_params and _adapt_video_payload_from_validation(
                        model=model,
                        payload=candidate_payload,
                        invalid_params=invalid_params,
                    ):
                        continue
                raise

        if created is not None:
            break

    if created is None:
        if last_error:
            raise last_error
        raise RuntimeError("Unable to resolve Freepik video endpoint.")

    data = created.get("data") or {}
    task_id = data.get("task_id")
    status = data.get("status")

    if not task_id:
        raise RuntimeError(f"Freepik image-to-video ({model}) did not return a task_id.")

    summary: Dict[str, Any] = {
        "type": "video_generation",
        "provider": "freepik",
        "model": model,
        "task_id": task_id,
        "status": status or "CREATED",
        "video_urls": [],
        "meta": {
            "model_name": model,
            "endpoint_path": resolved_create_path,
            "request_payload": payload,
        },
    }

    if not poll:
        return summary

    resolved_task_path = (task_endpoint_path or "").strip()
    if resolved_task_path:
        if "{task_id}" in resolved_task_path:
            resolved_task_path = resolved_task_path.format(task_id=task_id)
        elif not resolved_task_path.rstrip("/").endswith(task_id):
            resolved_task_path = f"{resolved_task_path.rstrip('/')}/{task_id}"
        poll_paths = [resolved_task_path]
    else:
        default_poll_paths = [
            f"/v1/ai/image-to-video/{model}/{task_id}",
            f"/v1/ai/video/{model}/{task_id}",
        ]
        if model.startswith("kling-v3-omni-"):
            default_poll_paths.append(f"/v1/ai/video/kling-v3-omni/{task_id}")
        preferred = f"{resolved_create_path.rstrip('/')}/{task_id}"
        poll_paths = [preferred] + [p for p in default_poll_paths if p != preferred]

    poll_paths = [p if p.startswith("/") else f"/{p}" for p in poll_paths]
    deadline = asyncio.get_running_loop().time() + poll_timeout_seconds
    last_error = None
    consecutive_404_rounds = 0

    while asyncio.get_running_loop().time() < deadline:
        try:
            task = None
            last_404_error: Optional[Exception] = None
            for poll_path in poll_paths:
                try:
                    task = await _get_json(poll_path)
                    break
                except FreepikAPIError as exc:
                    if exc.status_code == 404:
                        last_404_error = exc
                        continue
                    raise

            if task is None:
                consecutive_404_rounds += 1
                last_error = last_404_error
                await asyncio.sleep(poll_interval_seconds)
                continue

            consecutive_404_rounds = 0
            tdata = task.get("data") or task
            status = tdata.get("status") or status
            summary["status"] = status

            generated = tdata.get("generated") or []
            if status == "COMPLETED":
                urls: List[str] = []
                for item in generated:
                    if isinstance(item, dict):
                        url = item.get("url") or item.get("video_url")
                        if url:
                            urls.append(url)
                    elif isinstance(item, str):
                        urls.append(item)
                summary["video_urls"] = urls
                return summary

            if status == "FAILED":
                fail_msg = tdata.get("error") or tdata.get("message") or tdata.get("failure_reason")
                if fail_msg:
                    summary["error"] = fail_msg if isinstance(fail_msg, str) else str(fail_msg)
                return summary

            await asyncio.sleep(poll_interval_seconds)
            last_error = None
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(poll_interval_seconds)

    if last_error:
        summary["error"] = str(last_error)
    summary["status"] = status or "IN_PROGRESS"
    return summary


async def edit_image(
    prompt: str,
    *,
    reference_images: Optional[List[str]] = None,
    aspect_ratio: str = "square_1_1",
    guidance_scale: float = 2.5,
    seed: Optional[int] = None,
    poll: bool = True,
    poll_timeout_seconds: int = 60,
    poll_interval_seconds: float = 3.0,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "guidance_scale": guidance_scale,
    }

    if reference_images:
        payload["reference_images"] = reference_images[:5]
    if seed is not None:
        payload["seed"] = seed

    created = await _post_json("/v1/ai/text-to-image/seedream-v4-edit", payload)

    data = created.get("data") or {}
    task_id = data.get("task_id")
    status = data.get("status")
    generated = data.get("generated") or []

    if not task_id:
        raise RuntimeError("Freepik Seedream v4 edit did not return a task_id.")

    summary: Dict[str, Any] = {
        "type": "image_edit",
        "provider": "freepik",
        "model": "seedream-v4-edit",
        "task_id": task_id,
        "status": status or "CREATED",
        "image_urls": generated if isinstance(generated, list) else [],
    }

    if not poll:
        return summary

    deadline = asyncio.get_running_loop().time() + poll_timeout_seconds
    last_error: Optional[Exception] = None

    while asyncio.get_running_loop().time() < deadline:
        try:
            task = await _get_json(f"/v1/ai/text-to-image/seedream-v4-edit/{task_id}")
            tdata = task.get("data") or task
            status = tdata.get("status") or status
            summary["status"] = status

            generated = tdata.get("generated") or []
            if status == "COMPLETED":
                urls: List[str] = []
                for item in generated:
                    if isinstance(item, str):
                        urls.append(item)
                    elif isinstance(item, dict):
                        url = item.get("url") or item.get("image_url")
                        if url:
                            urls.append(url)
                summary["image_urls"] = urls
                return summary

            if status == "FAILED":
                fail_msg = tdata.get("error") or tdata.get("message") or tdata.get("failure_reason")
                if fail_msg:
                    summary["error"] = fail_msg if isinstance(fail_msg, str) else str(fail_msg)
                return summary

            await asyncio.sleep(poll_interval_seconds)
            last_error = None
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(poll_interval_seconds)

    if last_error:
        summary["error"] = str(last_error)
    summary["status"] = status or "IN_PROGRESS"
    return summary










