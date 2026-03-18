"""Higgsfield API client for image and video generation."""

import asyncio
import os
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

HIGGSFIELD_MODEL_ALIASES: dict[str, str] = {
    # DOP "preview" is no longer accepted in path enum; map to valid default.
    "higgsfield-ai/dop/preview": "higgsfield-ai/dop/standard",
}


class HiggsfieldAPIError(RuntimeError):
    def __init__(self, status_code: int, response_text: str, details: str | None = None):
        self.status_code = status_code
        self.response_text = response_text
        self.details = details
        suffix = f" | {details}" if details else ""
        super().__init__(f"Higgsfield API error {status_code}: {response_text[:240]}{suffix}")


def _clean_env(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().strip('"').strip("'")
    return cleaned or None


def _base_url() -> str:
    return _clean_env(os.getenv("HIGGSFIELD_BASE_URL")) or "https://platform.higgsfield.ai"


def _auth_values() -> list[str]:
    token = _clean_env(os.getenv("HIGGSFIELD_API_TOKEN"))
    api_id = _clean_env(os.getenv("HIGGSFIELD_API_ID"))
    key = _clean_env(os.getenv("HIGGSFIELD_API_KEY"))
    secret = _clean_env(os.getenv("HIGGSFIELD_API_SECRET"))

    values: list[str] = []
    if token:
        values.append(token)
    if api_id and key:
        values.append(f"{api_id}:{key}")
    if key and secret:
        values.append(f"{key}:{secret}")
    if key:
        values.append(key)
    if api_id:
        values.append(api_id)

    dedup = list(dict.fromkeys(values))
    if not dedup:
        raise RuntimeError(
            "HIGGSFIELD credentials are missing. Provide HIGGSFIELD_API_TOKEN or "
            "HIGGSFIELD_API_KEY (+ HIGGSFIELD_API_SECRET)."
        )
    return dedup


def _header_variants() -> list[tuple[str, dict[str, str]]]:
    variants: list[tuple[str, dict[str, str]]] = []
    for val in _auth_values():
        variants.append(
            (
                "authorization-key",
                {
                    "Authorization": f"Key {val}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        )
        variants.append(
            (
                "authorization-bearer",
                {
                    "Authorization": f"Bearer {val}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        )
        variants.append(
            (
                "x-api-key",
                {
                    "x-api-key": val,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        )

    out: list[tuple[str, dict[str, str]]] = []
    seen: set[str] = set()
    for name, hdr in variants:
        marker = "|".join(f"{k}:{v}" for k, v in sorted(hdr.items()))
        if marker in seen:
            continue
        seen.add(marker)
        out.append((name, hdr))
    return out


async def _request(method: str, path: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    url = f"{_base_url().rstrip('/')}{path}"
    errors: list[str] = []

    async with httpx.AsyncClient(timeout=120.0) as client:
        for auth_name, headers in _header_variants():
            response = await client.request(method, url, json=payload, headers=headers)
            body = response.text

            if response.status_code < 400:
                return response.json()

            # Explicit billing failure from upstream; stop retrying variants.
            if response.status_code in {402, 403} and "not enough credits" in body.lower():
                raise HiggsfieldAPIError(
                    response.status_code,
                    body,
                    details=(
                        "Your Higgsfield account has insufficient credits. "
                        "Top up credits in Higgsfield and retry."
                    ),
                )

            # Try other auth styles for auth-ish/opaque errors.
            if response.status_code in {401, 403, 500}:
                errors.append(f"{auth_name}:{response.status_code}:{body[:120]}")
                continue

            raise HiggsfieldAPIError(
                response.status_code,
                body,
                details=f"url={url} auth={auth_name}",
            )

    raise HiggsfieldAPIError(
        500,
        "All auth variants failed",
        details=f"url={url} attempts={'; '.join(errors)}",
    )


async def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return await _request("POST", path, payload)


async def _get(path: str) -> Dict[str, Any]:
    return await _request("GET", path)


async def submit_generation(model_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    model = HIGGSFIELD_MODEL_ALIASES.get(model_id.strip(), model_id.strip()).strip("/")
    if not model:
        raise RuntimeError("model_id is required")

    path = f"/{model}"

    # Most Higgsfield models expect direct payload.
    try:
        return await _post(path, args)
    except HiggsfieldAPIError as exc:
        # If provider returns enum mismatch on app_model_slug, retry with standard slug.
        if exc.status_code == 422 and "app_model_slug" in (exc.response_text or "") and model.startswith("higgsfield-ai/dop/"):
            fallback_model = "higgsfield-ai/dop/standard"
            if model != fallback_model:
                return await _post(f"/{fallback_model}", args)
        raise
    except Exception:
        # Fallback for model variants expecting wrapped args.
        return await _post(path, {"args": args})


async def get_request_status(request_id: str) -> Dict[str, Any]:
    rid = request_id.strip()
    if not rid:
        raise RuntimeError("request_id is required")
    return await _get(f"/requests/{rid}/status")


async def cancel_request(request_id: str) -> Dict[str, Any]:
    rid = request_id.strip()
    if not rid:
        raise RuntimeError("request_id is required")
    return await _post(f"/requests/{rid}/cancel", {})

def _collect_media_urls(node: Any) -> tuple[list[str], list[str]]:
    image_urls: set[str] = set()
    video_urls: set[str] = set()

    def walk(value: Any, parent_key: str = "") -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                walk(v, str(k).lower())
            return
        if isinstance(value, list):
            for item in value:
                walk(item, parent_key)
            return
        if not isinstance(value, str) or not value.startswith("http"):
            return

        u = value.lower()
        if any(x in parent_key for x in ("video", "clip", "movie")) or u.endswith((".mp4", ".webm", ".mov", ".mkv", ".avi")):
            video_urls.add(value)
            return
        image_urls.add(value)

    walk(node)
    return sorted(image_urls), sorted(video_urls)


def _extract_error_text(node: Any) -> str | None:
    if isinstance(node, dict):
        for key in ("error", "message", "detail", "reason"):
            val = node.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        for v in node.values():
            found = _extract_error_text(v)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _extract_error_text(item)
            if found:
                return found
    return None


async def wait_for_request(
    request_id: str,
    *,
    timeout_seconds: int = 300,
    poll_interval_seconds: float = 3.0,
) -> Dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    last: Dict[str, Any] = {}
    while asyncio.get_running_loop().time() < deadline:
        last = await get_request_status(request_id)
        status = str(last.get("status") or "").lower()
        if status in {"completed", "failed", "error", "canceled", "cancelled", "nsfw"}:
            return last
        await asyncio.sleep(poll_interval_seconds)

    return {"status": "timeout", "request_id": request_id, "last_response": last}


async def generate_image(
    prompt: str,
    *,
    model_id: str = "higgsfield-ai/soul/standard",
    aspect_ratio: Optional[str] = None,
    seed: Optional[int] = None,
    extra_args: Optional[Dict[str, Any]] = None,
    poll: bool = True,
    poll_timeout_seconds: int = 300,
    poll_interval_seconds: float = 3.0,
) -> Dict[str, Any]:
    args: Dict[str, Any] = {"prompt": prompt}
    if aspect_ratio:
        args["aspect_ratio"] = aspect_ratio
    if seed is not None:
        args["seed"] = seed
    if extra_args:
        args.update(extra_args)

    created = await submit_generation(model_id=model_id, args=args)
    request_id = created.get("request_id")
    if not request_id:
        raise RuntimeError("Higgsfield did not return request_id")

    summary: Dict[str, Any] = {
        "type": "image_generation",
        "provider": "higgsfield",
        "model_id": model_id,
        "request_id": request_id,
        "status": created.get("status") or "queued",
        "response": created,
        "output": None,
        "image_urls": [],
        "meta": {"args": args},
    }

    if not poll:
        return summary

    final = await wait_for_request(
        request_id,
        timeout_seconds=poll_timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
    summary["status"] = final.get("status") or summary["status"]
    summary["output"] = final.get("output")
    summary["response"] = final

    image_urls, _ = _collect_media_urls(final)
    if image_urls:
        summary["image_urls"] = image_urls

    status_l = str(summary.get("status") or "").lower()
    if status_l in {"failed", "error", "nsfw", "timeout", "canceled", "cancelled"}:
        summary["error"] = _extract_error_text(final) or f"Higgsfield request ended with status={summary['status']}"

    return summary


async def generate_video(
    image_url: str,
    prompt: str,
    *,
    model_id: str = "higgsfield-ai/dop/standard",
    extra_args: Optional[Dict[str, Any]] = None,
    poll: bool = True,
    poll_timeout_seconds: int = 300,
    poll_interval_seconds: float = 3.0,
) -> Dict[str, Any]:
    args: Dict[str, Any] = {
        "prompt": prompt,
        "image_url": image_url,
        "image": image_url,
    }
    if extra_args:
        args.update(extra_args)

    created = await submit_generation(model_id=model_id, args=args)
    request_id = created.get("request_id")
    if not request_id:
        raise RuntimeError("Higgsfield did not return request_id")

    summary: Dict[str, Any] = {
        "type": "video_generation",
        "provider": "higgsfield",
        "model_id": model_id,
        "request_id": request_id,
        "status": created.get("status") or "queued",
        "response": created,
        "output": None,
        "video_urls": [],
        "meta": {"args": args},
    }

    if not poll:
        return summary

    final = await wait_for_request(
        request_id,
        timeout_seconds=poll_timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
    summary["status"] = final.get("status") or summary["status"]
    summary["output"] = final.get("output")
    summary["response"] = final

    image_urls, _ = _collect_media_urls(final)
    if image_urls:
        summary["image_urls"] = image_urls

    status_l = str(summary.get("status") or "").lower()
    if status_l in {"failed", "error", "nsfw", "timeout", "canceled", "cancelled"}:
        summary["error"] = _extract_error_text(final) or f"Higgsfield request ended with status={summary['status']}"

    return summary
