import re
from typing import Any

import httpx
import streamlit as st

API_BASE_DEFAULT = "http://127.0.0.1:8000"
DEFAULT_IMAGE_URL = "https://d3u0tzju9qaucj.cloudfront.net/49383509-d21f-4835-962a-7467c3c7a063/d7b4a329-e3b0-49c4-b473-2d998b232fc9.png"

FREEPIK_LLM_FULL_URL = "https://docs.freepik.com/llms-full.txt"
HIGGSFIELD_IMAGES_URL = "https://docs.higgsfield.ai/guides/images.md"
HIGGSFIELD_VIDEO_URL = "https://docs.higgsfield.ai/guides/video.md"

# Fallback lists if docs fetch fails.
FREEPIK_IMAGE_MODELS_FALLBACK = [
    "flux-2-pro",
    "flux-2-turbo",
    "flux-dev",
    "flux-kontext-pro",
    "flux-pro-v1-1",
    "hyperflux",
    "runway",
    "seedream",
    "seedream-v4",
    "seedream-v4-5",
    "seedream-v4-5-edit",
    "seedream-v4-edit",
    "seedream-v5-lite",
    "seedream-v5-lite-edit",
    "z-image",
]

FREEPIK_VIDEO_MODELS_FALLBACK = [
    "kling-v2-6-pro",
    "kling-v2-5-pro",
    "kling-v2-1-pro",
    "minimax-hailuo-2-3-1080p",
    "runway-gen4-turbo",
    "seedance-pro-1080p",
    "seedance-lite-1080p",
    "wan-2-5-i2v-1080p",
    "wan-v2-6-1080p",
    "pixverse-v5",
]

HIGGSFIELD_IMAGE_MODELS_FALLBACK = [
    "higgsfield-ai/soul/standard",
    "reve/text-to-image",
    "bytedance/seedream/v4/edit",
]

HIGGSFIELD_VIDEO_MODELS_FALLBACK = [
    "higgsfield-ai/dop/standard",
    "higgsfield-ai/dop/lite",
    "higgsfield-ai/dop/turbo",
    "bytedance/seedance/v1/pro/image-to-video",
    "kling-video/v2.1/pro/image-to-video",
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


@st.cache_data(ttl=1800)
def fetch_freepik_models() -> tuple[list[str], list[str], str]:
    try:
        text = httpx.get(FREEPIK_LLM_FULL_URL, timeout=30).text
        image_models = sorted(set(re.findall(r"post /v1/ai/text-to-image/([a-zA-Z0-9._-]+)", text)))
        video_models = sorted(set(re.findall(r"post /v1/ai/image-to-video/([a-zA-Z0-9._-]+)", text)))
        if image_models and video_models:
            return image_models, video_models, "live-docs"
    except Exception:
        pass
    return FREEPIK_IMAGE_MODELS_FALLBACK, FREEPIK_VIDEO_MODELS_FALLBACK, "fallback"


@st.cache_data(ttl=1800)
def fetch_higgsfield_models() -> tuple[list[str], list[str], str]:
    try:
        image_doc = httpx.get(HIGGSFIELD_IMAGES_URL, timeout=30).text
        video_doc = httpx.get(HIGGSFIELD_VIDEO_URL, timeout=30).text

        image_models = set(re.findall(r"`([a-z0-9-]+/[a-z0-9.-]+(?:/[a-z0-9./-]+)?)`", image_doc))
        image_models.update(re.findall(r"https://platform\\.higgsfield\\.ai/([a-z0-9-]+/[a-z0-9./-]+)", image_doc))

        video_models = set(re.findall(r"`([a-z0-9-]+/[a-z0-9.-]+(?:/[a-z0-9./-]+)?)`", video_doc))
        video_models.update(re.findall(r"https://platform\\.higgsfield\\.ai/([a-z0-9-]+/[a-z0-9./-]+)", video_doc))

        image_models = {m for m in image_models if not m.startswith("requests/")}
        video_models = {m for m in video_models if not m.startswith("requests/")}

        image_sorted = sorted(m for m in image_models if ("text-to-image" in m or "soul" in m or "seedream" in m or "reve" in m))
        video_sorted = sorted(m for m in video_models if ("video" in m or "dop" in m or "seedance" in m or "kling" in m))

        if image_sorted and video_sorted:
            return image_sorted, video_sorted, "live-docs"
    except Exception:
        pass

    return HIGGSFIELD_IMAGE_MODELS_FALLBACK, HIGGSFIELD_VIDEO_MODELS_FALLBACK, "fallback"


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


def freepik_model_needs_input_image(model: str) -> bool:
    m = (model or "").lower()
    return ("kontext" in m) or m.endswith("-edit") or ("edit" in m)


def higgsfield_model_needs_image_input(model: str) -> bool:
    m = (model or "").lower()
    return ("seedream" in m and "edit" in m) or m.endswith("/edit")
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


def show_result(result: dict[str, Any]) -> None:
    status = str(result.get("status") or "").strip()
    task_id = result.get("task_id") or result.get("request_id")
    if status or task_id:
        st.info(f"status={status or '-'} | task_id={task_id or '-'}")

    explicit_error = result.get("error")
    response_obj = result.get("response") if isinstance(result.get("response"), dict) else {}
    nested_error = None
    if isinstance(response_obj, dict):
        nested_error = response_obj.get("error") or response_obj.get("message") or response_obj.get("detail")

    if explicit_error:
        st.error(str(explicit_error))
    elif nested_error and str(status).lower() in {"failed", "error", "nsfw", "timeout", "canceled", "cancelled"}:
        st.error(str(nested_error))

    image_urls, video_urls = _collect_urls(result)

    if image_urls:
        for u in image_urls:
            st.image(u, use_container_width=True)

    if video_urls:
        for u in video_urls:
            st.video(u)

    if not image_urls and not video_urls:
        st.warning("No media URL yet. Generation is likely still processing.")


def main() -> None:
    st.set_page_config(page_title="Freepik + Higgsfield Tester", layout="wide")
    st.title("Freepik + Higgsfield Model Tester")

    st.caption("Model dropdowns are loaded from internet docs when possible.")

    api_base = st.text_input("FastAPI Base URL", value=API_BASE_DEFAULT)

    freepik_image_models, freepik_video_models, freepik_src = fetch_freepik_models()
    higgsfield_image_models, higgsfield_video_models, higgsfield_src = fetch_higgsfield_models()

    col1, col2 = st.columns(2)
    col1.info(f"Freepik models source: {freepik_src} | image={len(freepik_image_models)} video={len(freepik_video_models)}")
    col2.info(f"Higgsfield models source: {higgsfield_src} | image={len(higgsfield_image_models)} video={len(higgsfield_video_models)}")

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "Freepik: generate-image",
            "Freepik: generate-video",
            "Higgsfield: generate-image",
            "Higgsfield: generate-video",
        ]
    )

    with tab1:
        model = st.selectbox("Freepik image model", freepik_image_models, key="f_img_model")
        prompt = st.text_area("Prompt", value="fashion portrait, studio light", key="f_img_prompt")
        img_aspect_options = freepik_image_aspect_options(model)
        aspect_ratio = st.selectbox("Aspect ratio", img_aspect_options, index=0, key="f_img_ar")
        input_image_url = st.text_input("Input image URL (required for kontext/edit models)", value=DEFAULT_IMAGE_URL, key="f_img_input")
        poll = st.checkbox("Poll", value=True, key="f_img_poll")
        extra_raw = st.text_area("extra_payload (JSON object, optional)", value="{}", key="f_img_extra")

        if freepik_model_needs_input_image(model) and not input_image_url.strip():
            st.warning("This model generally needs input image. Add Input image URL.")

        if st.button("Run Freepik Image", key="run_f_img"):
            extra_payload = _safe_json_loads(extra_raw) or {}
            if input_image_url.strip() and "input_image" not in extra_payload:
                extra_payload["input_image"] = input_image_url.strip()

            payload = {
                "prompt": prompt,
                "model_name": model,
                "aspect_ratio": aspect_ratio or None,
                "poll": poll,
                "extra_payload": extra_payload,
            }
            with st.spinner("Calling API..."):
                try:
                    result = call_api(api_base, "/v1/freepik/generate-image", payload)
                    show_result(result)
                except Exception as exc:
                    st.error(str(exc))

    with tab2:
        model = st.selectbox("Freepik video model", freepik_video_models, key="f_vid_model")
        prompt = st.text_area("Prompt", value="camera slowly pans left", key="f_vid_prompt")
        image_url = st.text_input("Source image URL", value=DEFAULT_IMAGE_URL, key="f_vid_img")

        aspect_options = freepik_video_aspect_options(model)
        aspect_ratio = st.selectbox("Aspect ratio", aspect_options, index=0, key="f_vid_ar")
        duration_seconds = st.selectbox("Duration (seconds)", [5, 10], index=0, key="f_vid_duration")
        camera_fixed = st.checkbox("Camera fixed", value=False, key="f_vid_camera_fixed")
        poll = st.checkbox("Poll", value=True, key="f_vid_poll")
        poll_timeout_seconds = st.number_input("Poll timeout (sec)", min_value=30, max_value=1800, value=600, step=30, key="f_vid_timeout")
        poll_interval_seconds = st.number_input("Poll interval (sec)", min_value=1.0, max_value=30.0, value=3.0, step=0.5, key="f_vid_interval")
        extra_raw = st.text_area("extra_payload (JSON object, optional)", value="{}", key="f_vid_extra")

        if st.button("Run Freepik Video", key="run_f_vid"):
            if not image_url.strip():
                st.error("Source image URL is required")
            else:
                payload = {
                    "image": image_url,
                    "prompt": prompt,
                    "model_name": model,
                    "aspect_ratio": aspect_ratio or None,
                    "duration_seconds": int(duration_seconds),
                    "camera_fixed": bool(camera_fixed),
                    "poll": poll,
                    "poll_timeout_seconds": int(poll_timeout_seconds),
                    "poll_interval_seconds": float(poll_interval_seconds),
                    "extra_payload": _safe_json_loads(extra_raw) or {},
                }
                with st.spinner("Calling API..."):
                    try:
                        result = call_api(api_base, "/v1/freepik/generate-video", payload)
                        show_result(result)
                    except Exception as exc:
                        st.error(str(exc))

    with tab3:
        model = st.selectbox("Higgsfield image model", higgsfield_image_models, key="h_img_model")
        prompt = st.text_area("Prompt", value="fashion portrait, studio light", key="h_img_prompt")
        aspect_ratio = st.text_input("Aspect ratio", value="9:16", key="h_img_ar")
        needs_edit_image = higgsfield_model_needs_image_input(model)
        edit_image_url = ""
        if needs_edit_image:
            edit_image_url = st.text_input(
                "Edit source image URL",
                value=DEFAULT_IMAGE_URL,
                key="h_img_edit_src",
                help="Required for edit models like bytedance/seedream/v4/edit.",
            )
        poll = st.checkbox("Poll", value=True, key="h_img_poll")
        extra_raw = st.text_area("extra_args (JSON object, optional)", value="{}", key="h_img_extra")

        if st.button("Run Higgsfield Image", key="run_h_img"):
            extra_args = _safe_json_loads(extra_raw) or {}
            if needs_edit_image:
                src = (edit_image_url or DEFAULT_IMAGE_URL).strip()
                if src and "image_urls" not in extra_args:
                    extra_args["image_urls"] = [src]

            payload = {
                "prompt": prompt,
                "model_id": model,
                "aspect_ratio": aspect_ratio or None,
                "poll": poll,
                "extra_args": extra_args,
            }
            with st.spinner("Calling API..."):
                try:
                    result = call_api(api_base, "/v1/higgsfield/generate-image", payload)
                    show_result(result)
                except Exception as exc:
                    st.error(str(exc))

    with tab4:
        model = st.selectbox("Higgsfield video model", higgsfield_video_models, key="h_vid_model")
        prompt = st.text_area("Prompt", value="camera slowly pans left", key="h_vid_prompt")
        image_url = st.text_input("Source image URL", value=DEFAULT_IMAGE_URL, key="h_vid_img")
        poll = st.checkbox("Poll", value=True, key="h_vid_poll")
        poll_timeout_seconds = st.number_input("Poll timeout (sec)", min_value=30, max_value=1800, value=600, step=30, key="h_vid_timeout")
        poll_interval_seconds = st.number_input("Poll interval (sec)", min_value=1.0, max_value=30.0, value=3.0, step=0.5, key="h_vid_interval")
        extra_raw = st.text_area("extra_args (JSON object, optional)", value="{}", key="h_vid_extra")

        if st.button("Run Higgsfield Video", key="run_h_vid"):
            if not image_url.strip():
                st.error("Source image URL is required")
            else:
                payload = {
                    "image_url": image_url,
                    "prompt": prompt,
                    "model_id": model,
                    "poll": poll,
                    "poll_timeout_seconds": int(poll_timeout_seconds),
                    "poll_interval_seconds": float(poll_interval_seconds),
                    "extra_args": _safe_json_loads(extra_raw) or {},
                }
                with st.spinner("Calling API..."):
                    try:
                        result = call_api(api_base, "/v1/higgsfield/generate-video", payload)
                        show_result(result)
                    except Exception as exc:
                        st.error(str(exc))


if __name__ == "__main__":
    main()




