"""复制服务 - 核心业务逻辑"""

import asyncio
import logging
from typing import Optional

import httpx

from api.client import NetEaseCloudAPI
from models.song import ProcessStatus, Song
from services.progress import ProgressTracker

logger = logging.getLogger(__name__)


# 常见错误码说明
ERROR_CODE_MESSAGES = {
    401: "未授权，Cookie 可能已过期",
    403: "禁止访问，Cookie 可能无效",
    429: "请求过于频繁，触发限流",
    500: "服务器内部错误",
    502: "网关错误",
    503: "服务暂时不可用",
    523: "源站不可达（可能是限流或临时错误）",
}


class CopyService:
    """复制服务，负责将源账号的歌曲复制到目标账号"""

    def __init__(
        self,
        source_api: NetEaseCloudAPI,
        target_api: NetEaseCloudAPI,
        progress: ProgressTracker,
        batch_size: int = 10,
    ):
        """
        初始化复制服务

        Args:
            source_api: 源账号 API 客户端
            target_api: 目标账号 API 客户端
            progress: 进度跟踪器
            batch_size: 批处理大小（每N首歌保存一次进度）
        """
        self.source_api = source_api
        self.target_api = target_api
        self.progress = progress
        self.batch_size = batch_size
        self.processed_count = 0

    async def copy_all_songs(self):
        """复制所有歌曲（主流程）"""
        logger.info("开始获取源账号歌曲列表...")
        source_songs = await self.source_api.fetch_all_cloud_songs()
        logger.info(f"源账号共有 {len(source_songs)} 首歌曲")

        logger.info("开始获取目标账号歌曲列表...")
        target_songs = await self.target_api.fetch_all_cloud_songs()
        logger.info(f"目标账号共有 {len(target_songs)} 首歌曲")

        # 提取目标账号已有歌曲的 MD5
        target_md5s = [song.privateCloud.md5 for song in target_songs]
        self.progress.set_target_existing_md5s(target_md5s)

        # 筛选需要复制的歌曲
        songs_to_copy = []
        for song in source_songs:
            md5 = song.privateCloud.md5

            # 检查是否已在目标账号
            if self.progress.is_in_target(md5):
                self.progress.mark_skipped_already_exists(
                    md5, song.privateCloud.song, song.privateCloud.artist
                )
                continue

            # 检查是否已处理
            if self.progress.is_processed(md5):
                logger.debug(f"跳过已处理: {song.privateCloud.song}")
                continue

            songs_to_copy.append(song)

        # 更新统计
        already_in_target = len([s for s in source_songs if self.progress.is_in_target(s.privateCloud.md5)])
        self.progress.update_statistics(
            total_source=len(source_songs),
            already_in_target=already_in_target,
            remaining=len(songs_to_copy),
        )

        logger.info(f"需要复制 {len(songs_to_copy)} 首歌曲")

        if not songs_to_copy:
            logger.info("没有需要复制的歌曲")
            self.progress.print_summary()
            return

        # 复制歌曲
        for idx, song in enumerate(songs_to_copy, 1):
            logger.info(f"\n[{idx}/{len(songs_to_copy)}] 处理: {song.privateCloud.song} - {song.privateCloud.artist}")

            try:
                await self.copy_single_song(song)
            except Exception as e:
                logger.error(f"复制失败: {e}")
                self.progress.mark_failed(
                    song.privateCloud.md5,
                    song.privateCloud.song,
                    song.privateCloud.artist,
                    str(e),
                )

            self.processed_count += 1

            # 批量保存进度
            if self.processed_count % self.batch_size == 0:
                logger.info(f"保存进度... (已处理 {self.processed_count} 首)")
                self.progress.save()

        # 最后保存一次
        self.progress.save()
        logger.info("\n所有歌曲处理完成！")
        self.progress.print_summary()

    async def copy_single_song(self, song: Song):
        """
        复制单首歌曲

        Args:
            song: 要复制的歌曲

        Raises:
            Exception: 复制过程中的错误
        """
        pc = song.privateCloud
        md5 = pc.md5

        # Step 1: 检查是否需要上传
        check_resp = await self.target_api.check_upload(
            md5=md5, file_size=pc.fileSize, bitrate=pc.bitrate
        )

        if check_resp.needUpload:
            # 需要真正上传文件，跳过
            logger.info(f"需要上传文件，跳过: {pc.song}")
            self.progress.mark_skipped_need_upload(md5, pc.song, pc.artist)
            return

        logger.debug(f"文件已存在服务器，songId: {check_resp.songId}")

        # Step 2: 分配 token（获取 resourceId）
        # 提取文件扩展名
        ext = pc.fileName.split(".")[-1] if "." in pc.fileName else "flac"

        token_resp = await self.target_api.allocate_token(
            md5=md5,
            filename=pc.fileName,
            filesize=pc.fileSize,
            bitrate=pc.bitrate,
            ext=ext,
        )

        resource_id = token_resp.result.resourceId
        logger.debug(f"获取 resourceId: {resource_id}")

        # Step 3: 上传云盘信息
        upload_resp = await self.target_api.upload_cloud_info(
            bitrate=pc.bitrate,
            md5=md5,
            songid=check_resp.songId,
            filename=pc.fileName,
            song=pc.song,
            album=pc.album,
            artist=pc.artist,
            resource_id=resource_id,
        )

        if upload_resp.code != 200:
            code_desc = ERROR_CODE_MESSAGES.get(upload_resp.code, "未知错误")
            error_msg = f"上传云盘信息失败: code={upload_resp.code} ({code_desc})"
            if upload_resp.message:
                error_msg += f", message={upload_resp.message}"

            # 如果是限流错误，等待一下
            if upload_resp.code in [429, 523]:
                logger.warning(f"{error_msg}，等待 5 秒后继续...")
                await asyncio.sleep(5)

            raise Exception(error_msg)

        logger.debug(f"上传云盘信息成功，songId: {upload_resp.songId}")

        # Step 4: 发布到云盘
        if upload_resp.privateCloud and upload_resp.privateCloud.songId:
            final_song_id = upload_resp.privateCloud.songId
        else:
            # 尝试使用响应中的 songId
            final_song_id = int(upload_resp.songId) if upload_resp.songId else None

        if not final_song_id:
            raise Exception("无法获取最终 songId")

        publish_resp = await self.target_api.publish_to_cloud(final_song_id)

        if publish_resp.code != 200:
            # 格式化错误信息
            code_desc = ERROR_CODE_MESSAGES.get(publish_resp.code, "未知错误")
            error_msg = f"发布到云盘失败: code={publish_resp.code} ({code_desc})"
            if publish_resp.message:
                error_msg += f", message={publish_resp.message}"

            # 如果是限流错误，等待后重试
            if publish_resp.code in [429, 523]:
                logger.warning(f"{error_msg}，等待 5 秒后继续...")
                await asyncio.sleep(5)

            logger.warning(error_msg)
            raise Exception(error_msg)

        # 标记成功
        self.progress.mark_success(md5, pc.song, pc.artist)
