# Freepik + Higgsfield Models and API Testing (Docs-Sourced)

Last updated: 2026-03-17

This document is compiled from official docs pages only (no model guesses).

## 1) Freepik: documented generation model endpoints

Source used: `https://docs.freepik.com/llms-full.txt`

### Count summary (documented endpoints)
- `text-to-image`: 15
- `image-to-video`: 41
- `text-to-video`: 8
- `video`: 14
- `mystic` endpoint: 1 (`POST /v1/ai/mystic`)

Notes:
- Some names appear in multiple categories (for example `ltx-2-pro` in both `text-to-video` and `image-to-video`).
- Unique model-name slugs across generation categories = 73; with `mystic` endpoint included, total documented generation endpoints/slugs = 74.

### Text-to-image (15)
- flux-2-pro
- flux-2-turbo
- flux-dev
- flux-kontext-pro
- flux-pro-v1-1
- hyperflux
- runway
- seedream
- seedream-v4
- seedream-v4-5
- seedream-v4-5-edit
- seedream-v4-edit
- seedream-v5-lite
- seedream-v5-lite-edit
- z-image

### Image-to-video (41)
- kling-elements-pro
- kling-elements-std
- kling-o1-pro
- kling-o1-pro-video-reference
- kling-o1-std
- kling-o1-std-video-reference
- kling-pro
- kling-std
- kling-v2
- kling-v2-1-master
- kling-v2-1-pro
- kling-v2-1-std
- kling-v2-5-pro
- kling-v2-6-pro
- ltx-2-fast
- ltx-2-pro
- minimax-hailuo-02-1080p
- minimax-hailuo-02-768p
- minimax-hailuo-2-3-1080p
- minimax-hailuo-2-3-1080p-fast
- minimax-hailuo-2-3-768p
- minimax-hailuo-2-3-768p-fast
- minimax-live
- pixverse-v5
- pixverse-v5-transition
- runway-4-5
- runway-gen4-turbo
- seedance-lite-1080p
- seedance-lite-480p
- seedance-lite-720p
- seedance-pro-1080p
- seedance-pro-480p
- seedance-pro-720p
- wan-2-5-i2v-1080p
- wan-2-5-i2v-480p
- wan-2-5-i2v-720p
- wan-v2-2-480p
- wan-v2-2-580p
- wan-v2-2-720p
- wan-v2-6-1080p
- wan-v2-6-720p

### Text-to-video (8)
- ltx-2-fast
- ltx-2-pro
- runway-4-5
- wan-2-5-t2v-1080p
- wan-2-5-t2v-480p
- wan-2-5-t2v-720p
- wan-v2-6-1080p
- wan-v2-6-720p

### Video (14)
- kling-v2-6-motion-control-pro
- kling-v2-6-motion-control-std
- kling-v3-motion-control-pro
- kling-v3-motion-control-std
- kling-v3-omni-pro
- kling-v3-omni-std
- kling-v3-pro
- kling-v3-std
- omni-human-1-5
- runway-act-two
- seedance-1-5-pro-1080p
- seedance-1-5-pro-480p
- seedance-1-5-pro-720p
- vfx

### Mystic
- endpoint: `POST /v1/ai/mystic`

## 2) Higgsfield: models explicitly listed in docs pages

Sources used:
- `https://docs.higgsfield.ai/guides/images.md`
- `https://docs.higgsfield.ai/guides/video.md`
- `https://docs.higgsfield.ai/how-to/introduction.md`

### Explicit model IDs listed in docs (7)
- higgsfield-ai/soul/standard
- reve/text-to-image
- bytedance/seedream/v4/edit
- higgsfield-ai/dop/preview
- higgsfield-ai/dop/standard
- bytedance/seedance/v1/pro/image-to-video
- kling-video/v2.1/pro/image-to-video

Important: Higgsfield docs explicitly say "And many more..." and direct users to Models Gallery (`https://cloud.higgsfield.ai/explore`). So the full set is account/gallery-driven and not fully enumerated in public docs markdown.

## 3) How to test APIs (curl)

## Freepik direct API (provider endpoint)

Text-to-image example:
```bash
curl -X POST "https://api.freepik.com/v1/ai/text-to-image/flux-dev" \
  -H "x-freepik-api-key: YOUR_FREEPIK_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"fashion portrait, studio light","aspect_ratio":"9:16"}'
```

Get task status example:
```bash
curl -X GET "https://api.freepik.com/v1/ai/text-to-image/flux-dev/{task_id}" \
  -H "x-freepik-api-key: YOUR_FREEPIK_KEY"
```

## Higgsfield direct API (provider endpoint)

Image generation example:
```bash
curl -X POST "https://platform.higgsfield.ai/higgsfield-ai/soul/standard" \
  -H "Authorization: Key {api_key}:{api_key_secret}" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"prompt":"fashion portrait, studio light","aspect_ratio":"9:16","resolution":"720p"}'
```

Status polling example:
```bash
curl -X GET "https://platform.higgsfield.ai/requests/{request_id}/status" \
  -H "Authorization: Key {api_key}:{api_key_secret}" \
  -H "Accept: application/json"
```

## Test through this FastAPI project (your local server)

Start server:
```bash
uvicorn app.main:app --reload --port 8000
```

Freepik route:
```bash
curl -X POST "http://127.0.0.1:8000/v1/freepik/generate-image" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"fashion portrait","model_name":"flux-dev","aspect_ratio":"9:16","poll":false}'
```

Higgsfield route:
```bash
curl -X POST "http://127.0.0.1:8000/v1/higgsfield/generate-image" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"fashion portrait","model_id":"higgsfield-ai/soul/standard","aspect_ratio":"9:16","poll":false}'
```

## 4) Source links
- Freepik docs index: https://docs.freepik.com/llms.txt
- Freepik full docs dump: https://docs.freepik.com/llms-full.txt
- Higgsfield docs index: https://docs.higgsfield.ai/llms.txt
- Higgsfield images guide: https://docs.higgsfield.ai/guides/images
- Higgsfield video guide: https://docs.higgsfield.ai/guides/video
- Higgsfield API intro: https://docs.higgsfield.ai/how-to/introduction
- Higgsfield models gallery (for additional models): https://cloud.higgsfield.ai/explore
