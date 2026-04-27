import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/tags", tags=["Tags"])

PREF_FILE = Path("data/user_preferences.json")

def load_preferences():
    if not PREF_FILE.exists():
        return {"tags": []}
    with open(PREF_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_preferences(data):
    PREF_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PREF_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

class CreateTagRequest(BaseModel):
    name: str = Field(..., description="태그 이름")

@router.get("", summary="전체 태그 목록 조회")
async def list_tags():
    data = load_preferences()
    return {"tags": data.get("tags", [])}

@router.post("", summary="새 태그 생성")
async def create_tag(req: CreateTagRequest):
    data = load_preferences()
    tags = data.get("tags", [])
    if req.name not in tags:
        tags.append(req.name)
        data["tags"] = tags
        save_preferences(data)
    return {"tags": data["tags"]}

@router.delete("/{tag_name:path}", summary="태그 삭제")
async def delete_tag(tag_name: str):
    data = load_preferences()
    tags = data.get("tags", [])
    if tag_name in tags:
        tags.remove(tag_name)
        data["tags"] = tags
        save_preferences(data)
        
    # 모든 채널에서도 해당 태그 제거
    from app.main import get_recorder_service
    service = get_recorder_service()
    service.remove_tag_from_all_channels(tag_name)
        
    return {"status": "ok", "deleted": tag_name}

class UpdateChannelTagsRequest(BaseModel):
    tags: list[str] = Field(..., description="적용할 태그 목록")

@router.patch("/channel/{channel_id:path}", summary="개별 채널의 태그 업데이트")
async def update_channel_tags(channel_id: str, req: UpdateChannelTagsRequest):
    from app.main import get_recorder_service
    from app.api.stream import _to_composite_key
    
    service = get_recorder_service()
    composite_key = _to_composite_key(channel_id)
    
    try:
        service.set_channel_tags(composite_key, req.tags)
        return {"status": "ok", "tags": req.tags}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
