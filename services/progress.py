"""进度跟踪器"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from models.config import ProgressData, Statistics
from models.song import ProcessedSong, ProcessStatus

logger = logging.getLogger(__name__)


class ProgressTracker:
    """进度跟踪器，负责保存和加载进度"""

    def __init__(self, file_path: Path):
        """
        初始化进度跟踪器

        Args:
            file_path: 进度文件路径
        """
        self.file_path = Path(file_path)
        self.data: Optional[ProgressData] = None

    def load(self) -> ProgressData:
        """
        从文件加载进度

        Returns:
            进度数据
        """
        if not self.file_path.exists():
            logger.info("进度文件不存在，创建新进度")
            self.data = ProgressData(
                last_updated=datetime.now().isoformat(),
                statistics=Statistics(),
            )
            return self.data

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data_dict = json.load(f)
                self.data = ProgressData(**data_dict)
                logger.info(f"成功加载进度文件：{len(self.data.processed_songs)} 首已处理")
                return self.data
        except Exception as e:
            logger.error(f"加载进度文件失败: {e}")
            # 备份损坏的文件
            backup_path = self.file_path.with_suffix(".json.backup")
            if self.file_path.exists():
                self.file_path.rename(backup_path)
                logger.warning(f"已将损坏的进度文件备份到: {backup_path}")

            # 创建新进度
            self.data = ProgressData(
                last_updated=datetime.now().isoformat(),
                statistics=Statistics(),
            )
            return self.data

    def save(self):
        """保存进度到文件（原子写入）"""
        if self.data is None:
            logger.warning("没有进度数据，跳过保存")
            return

        # 更新时间戳
        self.data.last_updated = datetime.now().isoformat()

        # 确保目录存在
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        # 原子写入：先写临时文件，再重命名
        temp_path = self.file_path.with_suffix(".json.tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(
                    self.data.model_dump(),
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            # 原子重命名
            temp_path.replace(self.file_path)
            logger.debug("进度已保存")
        except Exception as e:
            logger.error(f"保存进度失败: {e}")
            if temp_path.exists():
                temp_path.unlink()
            raise

    def is_processed(self, md5: str) -> bool:
        """
        检查歌曲是否已处理

        Args:
            md5: 歌曲 MD5

        Returns:
            是否已处理
        """
        if self.data is None:
            return False
        return md5 in self.data.processed_songs

    def is_in_target(self, md5: str) -> bool:
        """
        检查歌曲是否已在目标账号

        Args:
            md5: 歌曲 MD5

        Returns:
            是否在目标账号
        """
        if self.data is None:
            return False
        return md5 in self.data.target_existing_md5s

    def mark_success(self, md5: str, song_name: str, artist: str):
        """
        标记歌曲复制成功

        Args:
            md5: 歌曲 MD5
            song_name: 歌曲名
            artist: 艺术家
        """
        if self.data is None:
            return

        processed = ProcessedSong(
            md5=md5,
            song_name=song_name,
            artist=artist,
            status=ProcessStatus.SUCCESS,
            timestamp=datetime.now().isoformat(),
        )
        self.data.processed_songs[md5] = processed
        self.data.statistics.successfully_copied += 1
        logger.info(f"✓ 复制成功: {song_name} - {artist}")

    def mark_failed(self, md5: str, song_name: str, artist: str, error: str):
        """
        标记歌曲复制失败

        Args:
            md5: 歌曲 MD5
            song_name: 歌曲名
            artist: 艺术家
            error: 错误信息
        """
        if self.data is None:
            return

        processed = ProcessedSong(
            md5=md5,
            song_name=song_name,
            artist=artist,
            status=ProcessStatus.FAILED,
            timestamp=datetime.now().isoformat(),
            error=error,
        )
        self.data.processed_songs[md5] = processed
        self.data.statistics.failed += 1
        logger.error(f"✗ 复制失败: {song_name} - {artist}: {error}")

    def mark_skipped_need_upload(self, md5: str, song_name: str, artist: str):
        """
        标记歌曲需要上传（跳过）

        Args:
            md5: 歌曲 MD5
            song_name: 歌曲名
            artist: 艺术家
        """
        if self.data is None:
            return

        processed = ProcessedSong(
            md5=md5,
            song_name=song_name,
            artist=artist,
            status=ProcessStatus.SKIPPED_NEED_UPLOAD,
            timestamp=datetime.now().isoformat(),
        )
        self.data.processed_songs[md5] = processed
        self.data.statistics.skipped_need_upload += 1
        logger.info(f"⊘ 跳过（需要上传）: {song_name} - {artist}")

    def mark_skipped_already_exists(self, md5: str, song_name: str, artist: str):
        """
        标记歌曲已存在（跳过）

        Args:
            md5: 歌曲 MD5
            song_name: 歌曲名
            artist: 艺术家
        """
        if self.data is None:
            return

        processed = ProcessedSong(
            md5=md5,
            song_name=song_name,
            artist=artist,
            status=ProcessStatus.SKIPPED_ALREADY_EXISTS,
            timestamp=datetime.now().isoformat(),
        )
        self.data.processed_songs[md5] = processed
        self.data.statistics.already_in_target += 1
        logger.debug(f"⊙ 跳过（已存在）: {song_name} - {artist}")

    def set_target_existing_md5s(self, md5s: list[str]):
        """
        设置目标账号已有歌曲的 MD5 列表

        Args:
            md5s: MD5 列表
        """
        if self.data is None:
            return
        self.data.target_existing_md5s = md5s
        logger.info(f"目标账号已有 {len(md5s)} 首歌曲")

    def update_statistics(
        self, total_source: int, already_in_target: int, remaining: int
    ):
        """
        更新统计信息

        Args:
            total_source: 源账号总歌曲数
            already_in_target: 已在目标账号的数量
            remaining: 剩余待处理数量
        """
        if self.data is None:
            return

        self.data.statistics.total_source_songs = total_source
        self.data.statistics.already_in_target = already_in_target
        self.data.statistics.remaining = remaining

    def print_summary(self):
        """打印统计摘要"""
        if self.data is None:
            return

        stats = self.data.statistics
        logger.info("=" * 60)
        logger.info("统计摘要")
        logger.info("=" * 60)
        logger.info(f"源账号总歌曲数: {stats.total_source_songs}")
        logger.info(f"已在目标账号: {stats.already_in_target}")
        logger.info(f"成功复制: {stats.successfully_copied}")
        logger.info(f"跳过（需上传）: {stats.skipped_need_upload}")
        logger.info(f"失败: {stats.failed}")
        logger.info(f"剩余: {stats.remaining}")
        logger.info("=" * 60)
