"""歌曲相关数据模型"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ProcessStatus(str, Enum):
    """处理状态"""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED_NEED_UPLOAD = "skipped_need_upload"
    SKIPPED_ALREADY_EXISTS = "skipped_already_exists"
    PENDING = "pending"


class PrivateCloud(BaseModel):
    """云盘歌曲信息"""

    id: Optional[int] = None
    userId: Optional[int] = None
    songId: int
    md5: str
    song: str
    artist: str
    album: str
    bitrate: int
    fileName: str
    fileSize: int
    addTime: Optional[int] = None
    version: Optional[int] = None
    status: Optional[int] = None


class SimpleSongArtist(BaseModel):
    """艺术家信息"""

    id: int
    name: str


class SimpleSongAlbum(BaseModel):
    """专辑信息"""

    id: int
    name: str
    picUrl: Optional[str] = None


class SimpleSong(BaseModel):
    """歌曲详细信息"""

    name: str
    id: int
    ar: list[SimpleSongArtist]
    al: SimpleSongAlbum
    dt: int  # 时长（毫秒）


class Song(BaseModel):
    """完整歌曲信息（包含云盘和详细信息）"""

    privateCloud: PrivateCloud
    simpleSong: Optional[dict[str, Any]] = None  # 可选的详细信息


class CheckUploadResponse(BaseModel):
    """检查上传响应"""

    songId: str
    needUpload: bool
    code: int
    resourceId: Optional[int] = None


class TokenResult(BaseModel):
    """Token 分配结果"""

    bucket: str
    token: str
    outerUrl: Optional[str] = None
    docId: str
    objectKey: str
    resourceId: int


class TokenResponse(BaseModel):
    """Token 分配响应"""

    code: int
    message: Optional[str] = None
    result: TokenResult


class UploadInfoPrivateCloud(BaseModel):
    """上传信息中的云盘数据"""

    songId: int
    pcId: int
    songName: str
    addTime: int
    bitrate: int
    fileSize: int
    fileName: str


class UploadInfoResponse(BaseModel):
    """上传云盘信息响应"""

    privateCloud: Optional[UploadInfoPrivateCloud] = None
    code: int
    exists: Optional[bool] = None
    songId: Optional[str] = None
    message: Optional[str] = None


class PublishPrivateCloud(BaseModel):
    """发布响应中的云盘数据"""

    pcId: int
    songId: int
    songName: str
    artist: str
    bitrate: int
    fileSize: int
    fileName: str


class PublishResponse(BaseModel):
    """发布到云盘响应"""

    privateCloud: Optional[PublishPrivateCloud] = None
    code: int
    message: Optional[str] = None


class ProcessedSong(BaseModel):
    """已处理歌曲记录"""

    md5: str
    song_name: str
    artist: str
    status: ProcessStatus
    timestamp: str
    error: Optional[str] = None
