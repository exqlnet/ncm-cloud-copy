"""网易云音乐 API 客户端"""

import asyncio
import logging
from typing import Optional
from urllib.parse import quote

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from models.song import (
    CheckUploadResponse,
    PublishResponse,
    Song,
    TokenResponse,
    UploadInfoResponse,
)

logger = logging.getLogger(__name__)


class RateLimiter:
    """简单的限流器"""

    def __init__(self, calls_per_second: float = 2.0):
        self.delay = 1.0 / calls_per_second
        self.last_call = 0.0

    async def acquire(self):
        """等待以符合限流要求"""
        now = asyncio.get_event_loop().time()
        sleep_time = self.delay - (now - self.last_call)
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)
        self.last_call = asyncio.get_event_loop().time()


class NetEaseCloudAPI:
    """网易云音乐 API 客户端"""

    def __init__(self, cookie: str):
        """
        初始化 API 客户端

        Args:
            cookie: 完整的 Cookie 字符串
        """
        self.cookie = cookie
        self.client = httpx.AsyncClient(
            headers={
                "Cookie": cookie,
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=30.0,
            follow_redirects=True,
        )
        self.rate_limiter = RateLimiter(calls_per_second=2.0)

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _request(
        self, method: str, url: str, data: Optional[dict] = None
    ) -> dict:
        """
        发送 HTTP 请求（带重试）

        Args:
            method: HTTP 方法
            url: 请求 URL
            data: 请求数据

        Returns:
            响应 JSON
        """
        await self.rate_limiter.acquire()

        if method.upper() == "POST":
            # 将 dict 转换为 URL 编码的字符串
            if data:
                encoded_data = "&".join(f"{k}={v}" for k, v in data.items())
            else:
                encoded_data = ""
            response = await self.client.post(url, content=encoded_data)
        else:
            response = await self.client.get(url, params=data)

        response.raise_for_status()

        try:
            return response.json()
        except Exception as e:
            logger.error(f"解析 JSON 失败: {response.text}")
            raise

    async def validate_cookie(self) -> bool:
        """
        验证 Cookie 是否有效

        Returns:
            Cookie 是否有效
        """
        try:
            await self.get_cloud_songs(limit=1, offset=0)
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code in [401, 403]:
                logger.error("Cookie 无效或已过期")
                return False
            raise

    async def get_cloud_songs(self, limit: int = 100, offset: int = 0) -> list[Song]:
        """
        获取云盘歌曲列表

        Args:
            limit: 每页数量
            offset: 偏移量

        Returns:
            歌曲列表
        """
        url = "https://music.163.com/api/v1/cloud/get"
        data = {"limit": str(limit), "offset": str(offset)}

        logger.debug(f"获取云盘歌曲: limit={limit}, offset={offset}")
        result = await self._request("POST", url, data)

        songs = []
        if "data" in result and isinstance(result["data"], list):
            for item in result["data"]:
                try:
                    songs.append(Song(**item))
                except Exception as e:
                    logger.warning(f"解析歌曲数据失败: {e}")
                    continue

        logger.info(f"获取到 {len(songs)} 首歌曲（offset={offset}）")
        return songs

    async def fetch_all_cloud_songs(self) -> list[Song]:
        """
        获取所有云盘歌曲（自动分页）

        Returns:
            所有歌曲列表
        """
        all_songs = []
        offset = 0
        limit = 100

        while True:
            batch = await self.get_cloud_songs(limit=limit, offset=offset)
            if not batch:
                break

            all_songs.extend(batch)
            offset += limit

            if len(batch) < limit:
                break  # 最后一页

        logger.info(f"共获取 {len(all_songs)} 首歌曲")
        return all_songs

    async def check_upload(
        self, md5: str, file_size: int, bitrate: int
    ) -> CheckUploadResponse:
        """
        检查文件是否需要上传

        Args:
            md5: 文件 MD5
            file_size: 文件大小
            bitrate: 比特率

        Returns:
            检查结果
        """
        url = "https://interface.music.163.com/api/cloud/upload/check"
        data = {
            "bitrate": str(bitrate),
            "ext": "",
            "songId": "0",
            "version": "1",
            "md5": md5,
            "length": str(file_size),
        }

        logger.debug(f"检查上传: md5={md5[:8]}...")
        result = await self._request("POST", url, data)
        return CheckUploadResponse(**result)

    async def allocate_token(
        self, md5: str, filename: str, filesize: int, bitrate: int, ext: str = "flac"
    ) -> TokenResponse:
        """
        分配 NOS token

        Args:
            md5: 文件 MD5
            filename: 文件名
            filesize: 文件大小
            bitrate: 比特率
            ext: 文件扩展名

        Returns:
            Token 信息
        """
        url = "https://music.163.com/api/nos/token/alloc"
        # URL 编码文件名
        encoded_filename = quote(filename, safe='')
        data = {
            "bucket": "",
            "local": "false",
            "nos_product": "3",
            "type": "audio",
            "ext": ext.upper(),
            "md5": md5,
            "filename": encoded_filename,
        }

        logger.debug(f"分配 token: {filename}")
        result = await self._request("POST", url, data)
        return TokenResponse(**result)

    async def upload_cloud_info(
        self,
        bitrate: int,
        md5: str,
        songid: str,
        filename: str,
        song: str,
        album: str,
        artist: str,
        resource_id: int,
    ) -> UploadInfoResponse:
        """
        上传云盘信息

        Args:
            bitrate: 比特率
            md5: 文件 MD5
            songid: 歌曲 ID（从 check_upload 获取）
            filename: 文件名
            song: 歌曲名
            album: 专辑名
            artist: 艺术家
            resource_id: 资源 ID（从 allocate_token 获取）

        Returns:
            上传信息响应
        """
        url = "https://music.163.com/api/upload/cloud/info/v2"
        data = {
            "bitrate": str(bitrate),
            "md5": md5,
            "songid": songid,
            "filename": quote(filename, safe=''),
            "song": quote(song, safe=''),
            "album": quote(album, safe=''),
            "artist": quote(artist, safe=''),
            "resourceId": str(resource_id),
        }

        logger.debug(f"上传云盘信息: {song} - {artist}")
        result = await self._request("POST", url, data)
        return UploadInfoResponse(**result)

    async def publish_to_cloud(self, songid: int) -> PublishResponse:
        """
        发布到云盘

        Args:
            songid: 歌曲 ID

        Returns:
            发布响应
        """
        url = "https://interface.music.163.com/api/cloud/pub/v2"
        data = {"songid": str(songid)}

        logger.debug(f"发布到云盘: songid={songid}")
        result = await self._request("POST", url, data)
        return PublishResponse(**result)
