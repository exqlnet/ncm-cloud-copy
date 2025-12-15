"""配置和进度相关数据模型"""

from typing import Optional

from pydantic import BaseModel, Field

from models.song import ProcessedSong


class AccountConfig(BaseModel):
    """账号配置"""

    cookie: str
    account_name: Optional[str] = None


class CookieConfig(BaseModel):
    """Cookie 配置"""

    source: AccountConfig
    target: AccountConfig


class Statistics(BaseModel):
    """统计信息"""

    total_source_songs: int = 0
    already_in_target: int = 0
    successfully_copied: int = 0
    skipped_need_upload: int = 0
    failed: int = 0
    remaining: int = 0


class ProgressData(BaseModel):
    """进度数据"""

    version: str = "1.0"
    last_updated: str
    source_account: Optional[str] = None
    target_account: Optional[str] = None
    statistics: Statistics = Field(default_factory=Statistics)
    processed_songs: dict[str, ProcessedSong] = Field(default_factory=dict)
    target_existing_md5s: list[str] = Field(default_factory=list)
