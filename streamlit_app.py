import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any

import httpx
import streamlit as st

API_BASE_DEFAULT = "http://127.0.0.1:8000"
DEFAULT_IMAGE_URL = "https://d3u0tzju9qaucj.cloudfront.net/49383509-d21f-4835-962a-7467c3c7a063/d7b4a329-e3b0-49c4-b473-2d998b232fc9.png"

PROMPT_TO_IMAGE_MODELS: list[dict[str, Any]] = [
    {"label": "flux-2-pro (freepik)", "provider": "freepik", "kind": "image", "id": "flux-2-pro"},
    {"label": "flux-2-turbo (freepik)", "provider": "freepik", "kind": "image", "id": "flux-2-turbo"},
    {"label": "flux-dev (freepik)", "provider": "freepik", "kind": "image", "id": "flux-dev"},
    {"label": "flux-pro-v1-1 (freepik)", "provider": "freepik", "kind": "image", "id": "flux-pro-v1-1"},
    {"label": "seedream-v5-lite (freepik)", "provider": "freepik", "kind": "image", "id": "seedream-v5-lite"},
    {"label": "runway (freepik)", "provider": "freepik", "kind": "image", "id": "runway"},
    {"label": "higgsfield-ai/soul/standard (higgsfield)", "provider": "higgsfield", "kind": "image", "id": "higgsfield-ai/soul/standard"},
]

IMAGE_TO_VIDEO_MODELS: list[dict[str, Any]] = [
    {"label": "kling-v2-6-pro (freepik)", "provider": "freepik", "kind": "video", "id": "kling-v2-6-pro"},
    {"label": "kling-v3-pro (freepik, preferred upgrade)", "provider": "freepik", "kind": "video", "id": "kling-v3-pro"},
    {"label": "runway-gen4-turbo (freepik)", "provider": "freepik", "kind": "video", "id": "runway-gen4-turbo"},
    {"label": "minimax-hailuo-2-3-1080p (freepik)", "provider": "freepik", "kind": "video", "id": "minimax-hailuo-2-3-1080p"},
    {"label": "ltx-2-pro (freepik)", "provider": "freepik", "kind": "video", "id": "ltx-2-pro"},
    {"label": "wan-v2-6-1080p (freepik)", "provider": "freepik", "kind": "video", "id": "wan-v2-6-1080p"},
    {"label": "seedance-1-5-pro-1080p (freepik)", "provider": "freepik", "kind": "video", "id": "seedance-1-5-pro-1080p"},
]

EDIT_MODELS: list[dict[str, Any]] = [
    {"label": "seedream-v4-edit (freepik)", "provider": "freepik", "kind": "image", "id": "seedream-v4-edit", "needs_image": True},
    {"label": "seedream-v4-5-edit (freepik)", "provider": "freepik", "kind": "image", "id": "seedream-v4-5-edit", "needs_image": True},
    {"label": "seedream-v5-lite-edit (freepik)", "provider": "freepik", "kind": "image", "id": "seedream-v5-lite-edit", "needs_image": True},
    # {"label": "gpt-1.5 (freepik)", "provider": "freepik", "kind": "image", "id": "gpt-1.5", "needs_image": True},
    # {"label": "gpt-1.5-high (freepik)", "provider": "freepik", "kind": "image", "id": "gpt-1.5-high", "needs_image": True},
    {"label": "flux-kontext-pro (freepik)", "provider": "freepik", "kind": "image", "id": "flux-kontext-pro", "needs_image": True},
    {"label": "higgsfield-ai/soul/reference (higgsfield)", "provider": "higgsfield", "kind": "image", "id": "higgsfield-ai/soul/reference", "needs_image": True},
]


def _safe_json_loads(raw: str) -> dict[str, Any] | None:
    import json

    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except Exception:
        return None
    return None


def _find_model(models: list[dict[str, Any]], label: str) -> dict[str, Any]:
    for model in models:
        if model["label"] == label:
            return model
    return models[0]


def freepik_video_aspect_options(model: str) -> list[str]:
    m = (model or "").lower()
    if any(x in m for x in ["kling", "minimax", "runway", "pixverse", "wan", "ltx", "seedance"]):
        return ["16:9", "9:16", "1:1", "widescreen_16_9", "portrait_9_16", "square_1_1"]
    return ["widescreen_16_9", "portrait_9_16", "square_1_1", "16:9", "9:16", "1:1"]



def freepik_image_aspect_options(model: str) -> list[str]:
    # Use documented symbolic keys; backend can further adapt per-model choices.
    return [
        "square_1_1",
        "widescreen_16_9",
        "social_story_9_16",
        "classic_4_3",
        "traditional_3_4",
        "standard_3_2",
        "portrait_2_3",
    ]


def higgsfield_image_aspect_options() -> list[str]:
    return ["9:16", "16:9", "4:3", "3:4", "1:1", "2:3", "3:2"]


def _normalize_aspect_ratio(provider: str, aspect_ratio: str) -> str:
    if provider != "higgsfield":
        return aspect_ratio

    mapping = {
        "square_1_1": "1:1",
        "widescreen_16_9": "16:9",
        "social_story_9_16": "9:16",
        "classic_4_3": "4:3",
        "traditional_3_4": "3:4",
        "standard_3_2": "3:2",
        "portrait_2_3": "2:3",
    }
    return mapping.get((aspect_ratio or "").strip(), aspect_ratio)


def freepik_model_needs_input_image(model: str) -> bool:
    m = (model or "").lower()
    return ("kontext" in m) or m.endswith("-edit") or ("edit" in m)


def higgsfield_model_needs_image_input(model: str) -> bool:
    m = (model or "").lower()
    return ("seedream" in m and "edit" in m) or m.endswith("/edit") or m.endswith("/reference")


def _run_one_model(
    api_base: str,
    model_cfg: dict[str, Any],
    prompt: str,
    source_image_url: str,
    aspect_ratio: str,
    extra_raw: str,
    duration_seconds: int,
    camera_fixed: bool,
    poll: bool = True,
) -> dict[str, Any]:
    provider = model_cfg["provider"]
    model_id = model_cfg["id"]
    kind = model_cfg["kind"]
    normalized_aspect_ratio = _normalize_aspect_ratio(provider, aspect_ratio)
    extra_data = _safe_json_loads(extra_raw) or {}

    if provider == "freepik" and kind == "image":
        if model_cfg.get("needs_image") or freepik_model_needs_input_image(model_id):
            src = source_image_url.strip()
            if src and "input_image" not in extra_data:
                extra_data["input_image"] = src
            if src and "reference_images" not in extra_data:
                extra_data["reference_images"] = [src]
        payload = {
            "prompt": prompt,
            "model_name": model_id,
            "aspect_ratio": normalized_aspect_ratio,
            "poll": poll,
            "extra_payload": extra_data,
        }
        return call_api(api_base, "/v1/freepik/generate-image", payload)

    if provider == "freepik" and kind == "video":
        payload = {
            "image": source_image_url,
            "prompt": prompt,
            "model_name": model_id,
            "aspect_ratio": normalized_aspect_ratio,
            "duration_seconds": duration_seconds,
            "camera_fixed": camera_fixed,
            "poll": poll,
            "extra_payload": extra_data,
        }
        return call_api(api_base, "/v1/freepik/generate-video", payload)

    if provider == "higgsfield" and kind == "image":
        if model_cfg.get("needs_image") or higgsfield_model_needs_image_input(model_id):
            if source_image_url.strip() and "image_urls" not in extra_data:
                print("extra_data", source_image_url)
                extra_data["image_urls"] = [source_image_url.strip()]
        payload = {
            "prompt": prompt,
            "model_id": model_id,
            "aspect_ratio": normalized_aspect_ratio,
            "poll": poll,
            "extra_args": extra_data,
        }
        return call_api(api_base, "/v1/higgsfield/generate-image", payload)

    raise RuntimeError(f"Unsupported model routing for model={model_id}")


def _section_smoke_test(
    api_base: str,
    models: list[dict[str, Any]],
    prompt: str,
    source_image_url: str,
    aspect_ratio: str,
    poll: bool = True,
) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    failure_statuses = {"failed", "error", "nsfw", "timeout", "canceled", "cancelled", "rejected", "expired"}
    for model_cfg in models:
        started = time.perf_counter()
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            result = _run_one_model(
                api_base=api_base,
                model_cfg=model_cfg,
                prompt=prompt,
                source_image_url=source_image_url,
                aspect_ratio=aspect_ratio,
                extra_raw="{}",
                duration_seconds=5,
                camera_fixed=False,
                poll=poll,
            )
            image_urls, video_urls = _collect_urls(result)
            top_image_urls = result.get("image_urls") if isinstance(result.get("image_urls"), list) else []
            top_video_urls = result.get("video_urls") if isinstance(result.get("video_urls"), list) else []
            image_urls = sorted({*image_urls, *[u for u in top_image_urls if isinstance(u, str)]})
            video_urls = sorted({*video_urls, *[u for u in top_video_urls if isinstance(u, str)]})
            status = str(result.get("status") or "-")
            status_l = status.lower()
            error_text = str(result.get("error") or "").strip()
            ok = status_l not in failure_statuses and not error_text
            if model_cfg["kind"] == "video" and status_l in {"completed", "success", "succeeded", "done", "finished"} and not video_urls:
                ok = False
                if not error_text:
                    error_text = "Generation completed but no video URL was returned."
            if model_cfg["kind"] == "image" and status_l in {"completed", "success", "succeeded", "done", "finished"} and not image_urls:
                ok = False
                if not error_text:
                    error_text = "Generation completed but no image URL was returned."

            report.append(
                {
                    "model": model_cfg["id"],
                    "provider": model_cfg["provider"],
                    "ok": ok,
                    "status": status,
                    "response_time_ms": result.get("_response_time_ms", round((time.perf_counter() - started) * 1000.0, 2)),
                    "image_urls": _stringify_urls(image_urls),
                    "video_urls": _stringify_urls(video_urls),
                    "error": error_text,
                }
            )
        except Exception as exc:
            report.append(
                {
                    "model": model_cfg["id"],
                    "provider": model_cfg["provider"],
                    "ok": False,
                    "status": "error",
                    "response_time_ms": round((time.perf_counter() - started) * 1000.0, 2),
                    "image_urls": "-",
                    "video_urls": "-",
                    "error": str(exc),
                }
            )
    return report
def _collect_urls(obj: Any) -> tuple[list[str], list[str]]:
    image_urls: set[str] = set()
    video_urls: set[str] = set()

    image_hints = {"image", "images", "image_url", "image_urls", "thumbnail", "thumbnails", "photo", "photos"}
    video_hints = {"video", "videos", "video_url", "video_urls", "clip", "clips", "movie"}

    def walk(node: Any, parent_keys: list[str]) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, parent_keys + [str(k).lower()])
            return
        if isinstance(node, list):
            for item in node:
                walk(item, parent_keys)
            return
        if not (isinstance(node, str) and node.startswith("http")):
            return

        lower_url = node.lower()
        key_ctx = " ".join(parent_keys)

        if any(h in key_ctx for h in image_hints):
            image_urls.add(node)
            return
        if any(h in key_ctx for h in video_hints):
            video_urls.add(node)
            return

        if lower_url.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")):
            image_urls.add(node)
            return
        if lower_url.endswith((".mp4", ".webm", ".mov", ".mkv", ".avi")):
            video_urls.add(node)
            return

        if "generate-image" in key_ctx or "image_generation" in key_ctx:
            image_urls.add(node)
            return

        image_urls.add(node)

    if isinstance(obj, dict):
        top_images = obj.get("image_urls")
        top_videos = obj.get("video_urls")
        if isinstance(top_images, list):
            image_urls.update(u for u in top_images if isinstance(u, str) and u.startswith("http"))
        if isinstance(top_videos, list):
            video_urls.update(u for u in top_videos if isinstance(u, str) and u.startswith("http"))

    walk(obj, [])
    return sorted(image_urls), sorted(video_urls)


def with_api_timing(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        started = time.perf_counter()
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            result = func(*args, **kwargs)
            elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
            if isinstance(result, dict):
                result["_api_timestamp"] = timestamp
                result["_response_time_ms"] = elapsed_ms
            return result
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
            raise RuntimeError(
                f"{exc} | response_time_ms={elapsed_ms} | timestamp_utc={timestamp}"
            ) from exc

    return wrapper


def _stringify_urls(values: list[str]) -> str:
    return ", ".join(values) if values else "-"


@with_api_timing
def call_api(api_base: str, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}{endpoint}"
    response = httpx.post(url, json=payload, timeout=600)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = response.text
        try:
            err_json = response.json()
            if isinstance(err_json, dict) and "detail" in err_json:
                detail = str(err_json["detail"])
        except Exception:
            pass
        raise RuntimeError(f"{response.status_code} error from {endpoint}: {detail}") from exc
    return response.json()


def show_result(result: dict[str, Any], expected_media: str = "any") -> None:
    status = str(result.get("status") or "").strip()
    task_id = result.get("task_id") or result.get("request_id")
    response_time_ms = result.get("_response_time_ms")
    api_timestamp = result.get("_api_timestamp")
    if status or task_id:
        st.info(
            f"status={status or '-'} | task_id={task_id or '-'} | "
            f"response_time_ms={response_time_ms if response_time_ms is not None else '-'} | "
            f"timestamp_utc={api_timestamp or '-'}"
        )

    explicit_error = result.get("error")
    response_obj = result.get("response") if isinstance(result.get("response"), dict) else {}
    nested_error = None
    if isinstance(response_obj, dict):
        nested_error = response_obj.get("error") or response_obj.get("message") or response_obj.get("detail")

    has_error = False
    if explicit_error:
        st.error(str(explicit_error))
        has_error = True
    elif nested_error and str(status).lower() in {"failed", "error", "nsfw", "timeout", "canceled", "cancelled"}:
        st.error(str(nested_error))
        has_error = True

    image_urls, video_urls = _collect_urls(result)

    show_images = expected_media in {"any", "image"}
    show_videos = expected_media in {"any", "video"}

    if show_images and image_urls:
        st.caption(f"image_urls: {', '.join(image_urls)}")
        for u in image_urls:
            st.image(u, use_container_width=True)

    if show_videos and video_urls:
        st.caption(f"video_urls: {', '.join(video_urls)}")
        for u in video_urls:
            st.video(u)

    has_any_media = (show_images and bool(image_urls)) or (show_videos and bool(video_urls))
    if not has_any_media and not has_error:
        st.warning("No media URL yet. Generation is likely still processing.")


def main() -> None:
    st.set_page_config(page_title="Image/Video/Edit Model Tester", layout="wide")
    st.title("Model Tester: Prompt-to-Image, Image-to-Video, Edit")

    api_base = st.text_input("FastAPI Base URL", value=API_BASE_DEFAULT)
    default_source_image = st.text_input("Default source image URL", value=DEFAULT_IMAGE_URL)

    tab1, tab2, tab3 = st.tabs(
        [
            "Image Models (Prompt-to-Image)",
            "Image-to-Video Models",
            "Edit Models (Image Editing / Style)",
        ]
    )

    with tab1:
        selected_label = st.selectbox("Model", [m["label"] for m in PROMPT_TO_IMAGE_MODELS], key="img_models_select")
        model_cfg = _find_model(PROMPT_TO_IMAGE_MODELS, selected_label)
        prompt = st.text_area("Prompt", value="A futuristic eco-friendly city at sunrise, ultra detailed", key="img_models_prompt")
        img_ar_options = (
            higgsfield_image_aspect_options()
            if model_cfg["provider"] == "higgsfield"
            else freepik_image_aspect_options(model_cfg["id"])
        )
        aspect_ratio = st.selectbox("Aspect ratio", img_ar_options, index=0, key="img_models_ar")
        extra_raw = st.text_area("Extra JSON payload/args", value="{}", key="img_models_extra")
        st.caption(f"Provider: {model_cfg['provider']} | Model ID: {model_cfg['id']}")

        if st.button("Run Selected Image Model", key="run_img_model"):
            with st.spinner("Calling API..."):
                try:
                    result = _run_one_model(
                        api_base=api_base,
                        model_cfg=model_cfg,
                        prompt=prompt,
                        source_image_url=default_source_image,
                        aspect_ratio=aspect_ratio,
                        extra_raw=extra_raw,
                        duration_seconds=5,
                        camera_fixed=False,
                    )
                    show_result(result, expected_media="image")
                except Exception as exc:
                    st.error(str(exc))

        poll_for_media = st.checkbox(
            "Wait for media URLs (slower)",
            value=True,
            key="check_all_image_models_poll",
        )
        if st.button("Check All Image Models", key="check_all_image_models"):
            with st.spinner("Running smoke checks for all prompt-to-image models..."):
                rows = _section_smoke_test(
                    api_base=api_base,
                    models=PROMPT_TO_IMAGE_MODELS,
                    prompt=prompt,
                    source_image_url=default_source_image,
                    aspect_ratio=aspect_ratio,
                    poll=bool(poll_for_media),
                )
            st.dataframe(rows, use_container_width=True)

    with tab2:
        selected_label = st.selectbox("Model", [m["label"] for m in IMAGE_TO_VIDEO_MODELS], key="i2v_models_select")
        model_cfg = _find_model(IMAGE_TO_VIDEO_MODELS, selected_label)
        prompt = st.text_area("Motion prompt", value="camera slowly pans left", key="i2v_models_prompt")
        image_url = st.text_input("Source image URL", value=default_source_image, key="i2v_models_source")
        aspect_ratio = st.selectbox("Aspect ratio", freepik_video_aspect_options(model_cfg["id"]), index=0, key="i2v_models_ar")
        duration_seconds = st.selectbox("Duration (seconds)", [5, 10], index=0, key="i2v_models_duration")
        camera_fixed = st.checkbox("Camera fixed", value=False, key="i2v_models_camera_fixed")
        extra_raw = st.text_area("Extra JSON payload", value="{}", key="i2v_models_extra")
        st.caption(f"Provider: {model_cfg['provider']} | Model ID: {model_cfg['id']}")

        if st.button("Run Selected Image-to-Video Model", key="run_i2v_model"):
            if not image_url.strip():
                st.error("Source image URL is required.")
            else:
                with st.spinner("Calling API..."):
                    try:
                        result = _run_one_model(
                            api_base=api_base,
                            model_cfg=model_cfg,
                            prompt=prompt,
                            source_image_url=image_url,
                            aspect_ratio=aspect_ratio,
                            extra_raw=extra_raw,
                            duration_seconds=int(duration_seconds),
                            camera_fixed=bool(camera_fixed),
                        )
                        show_result(result, expected_media="video")
                    except Exception as exc:
                        st.error(str(exc))

        poll_for_media = st.checkbox(
            "Wait for media URLs (slower)",
            value=True,
            key="check_all_i2v_models_poll",
        )
        if st.button("Check All Image-to-Video Models", key="check_all_i2v_models"):
            if not image_url.strip():
                st.error("Source image URL is required.")
            else:
                with st.spinner("Running smoke checks for all image-to-video models..."):
                    rows = _section_smoke_test(
                        api_base=api_base,
                        models=IMAGE_TO_VIDEO_MODELS,
                        prompt=prompt,
                        source_image_url=image_url,
                        aspect_ratio=aspect_ratio,
                        poll=bool(poll_for_media),
                    )
                st.dataframe(rows, use_container_width=True)

    with tab3:
        selected_label = st.selectbox("Model", [m["label"] for m in EDIT_MODELS], key="edit_models_select")
        model_cfg = _find_model(EDIT_MODELS, selected_label)
        prompt = st.text_area("Edit/style prompt", value="change style to cinematic fashion editorial", key="edit_models_prompt")
        image_url = st.text_input("Input image URL", value=default_source_image, key="edit_models_source")
        edit_ar_options = (
            higgsfield_image_aspect_options()
            if model_cfg["provider"] == "higgsfield"
            else freepik_image_aspect_options(model_cfg["id"])
        )
        aspect_ratio = st.selectbox("Aspect ratio", edit_ar_options, index=0, key="edit_models_ar")
        extra_raw = st.text_area("Extra JSON payload/args", value="{}", key="edit_models_extra")
        st.caption(f"Provider: {model_cfg['provider']} | Model ID: {model_cfg['id']}")

        if st.button("Run Selected Edit Model", key="run_edit_model"):
            if not image_url.strip():
                st.error("Input image URL is required.")
            else:
                with st.spinner("Calling API..."):
                    try:
                        result = _run_one_model(
                            api_base=api_base,
                            model_cfg=model_cfg,
                            prompt=prompt,
                            source_image_url=image_url,
                            aspect_ratio=aspect_ratio,
                            extra_raw=extra_raw,
                            duration_seconds=5,
                            camera_fixed=False,
                        )
                        show_result(result, expected_media="image")
                    except Exception as exc:
                        st.error(str(exc))

        poll_for_media = st.checkbox(
            "Wait for media URLs (slower)",
            value=True,
            key="check_all_edit_models_poll",
        )
        if st.button("Check All Edit Models", key="check_all_edit_models"):
            if not image_url.strip():
                st.error("Input image URL is required.")
            else:
                with st.spinner("Running smoke checks for all edit models..."):
                    rows = _section_smoke_test(
                        api_base=api_base,
                        models=EDIT_MODELS,
                        prompt=prompt,
                        source_image_url=image_url,
                        aspect_ratio=aspect_ratio,
                        poll=bool(poll_for_media),
                    )
                st.dataframe(rows, use_container_width=True)


if __name__ == "__main__":
    main()

