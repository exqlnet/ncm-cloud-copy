"""网易云音乐云盘复制工具 - CLI 入口"""

import asyncio
import json
import logging
import signal
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from api.client import NetEaseCloudAPI
from models.config import CookieConfig
from services.copy_service import CopyService
from services.progress import ProgressTracker
from utils.logger import setup_logger

app = typer.Typer(help="网易云音乐云盘复制工具")
console = Console()
logger = logging.getLogger(__name__)

# 全局变量，用于信号处理
progress_tracker: ProgressTracker = None


def signal_handler(sig, frame):
    """信号处理器：优雅关闭"""
    console.print("\n\n[yellow]收到中断信号，正在保存进度...[/yellow]")
    if progress_tracker:
        progress_tracker.save()
        console.print("[green]进度已保存[/green]")
    sys.exit(0)


@app.command()
def copy(
    config_file: Path = typer.Option(
        "config/cookies.json",
        "--config",
        "-c",
        help="Cookie 配置文件路径",
    ),
    progress_file: Path = typer.Option(
        "data/progress.json",
        "--progress",
        "-p",
        help="进度文件路径",
    ),
    batch_size: int = typer.Option(
        10,
        "--batch-size",
        "-b",
        help="批处理大小（每 N 首歌保存一次进度）",
    ),
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        "-l",
        help="日志级别（DEBUG/INFO/WARNING/ERROR）",
    ),
):
    """
    复制源账号的云盘歌曲到目标账号

    需要先在 config/cookies.json 中配置两个账号的 Cookie
    """
    # 设置日志
    level = getattr(logging, log_level.upper(), logging.INFO)
    setup_logger(level=level)

    # 显示欢迎信息
    console.print(
        Panel.fit(
            "[bold cyan]网易云音乐云盘复制工具[/bold cyan]\n"
            "将源账号的云盘歌曲复制到目标账号",
            border_style="cyan",
        )
    )

    # 检查配置文件
    if not config_file.exists():
        console.print(f"[red]错误: 配置文件不存在: {config_file}[/red]")
        console.print(f"[yellow]请参考 config/cookies.json.example 创建配置文件[/yellow]")
        raise typer.Exit(1)

    # 加载配置
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config_data = json.load(f)
            config = CookieConfig(**config_data)
        logger.info("配置文件加载成功")
    except Exception as e:
        console.print(f"[red]错误: 加载配置文件失败: {e}[/red]")
        raise typer.Exit(1)

    # 注册信号处理器
    global progress_tracker
    progress_tracker = ProgressTracker(progress_file)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 运行复制任务
    asyncio.run(run_copy(config, progress_tracker, batch_size))


async def run_copy(
    config: CookieConfig,
    progress: ProgressTracker,
    batch_size: int,
):
    """
    运行复制任务

    Args:
        config: Cookie 配置
        progress: 进度跟踪器
        batch_size: 批处理大小
    """
    # 加载进度
    progress.load()

    # 初始化 API 客户端
    source_api = NetEaseCloudAPI(config.source.cookie)
    target_api = NetEaseCloudAPI(config.target.cookie)

    try:
        # 验证 Cookie
        console.print("[cyan]正在验证 Cookie...[/cyan]")

        source_valid = await source_api.validate_cookie()
        if not source_valid:
            console.print("[red]错误: 源账号 Cookie 无效或已过期[/red]")
            return

        target_valid = await target_api.validate_cookie()
        if not target_valid:
            console.print("[red]错误: 目标账号 Cookie 无效或已过期[/red]")
            return

        console.print("[green]✓ Cookie 验证成功[/green]\n")

        # 设置账号名称
        if config.source.account_name:
            progress.data.source_account = config.source.account_name
        if config.target.account_name:
            progress.data.target_account = config.target.account_name

        # 创建复制服务
        copy_service = CopyService(
            source_api=source_api,
            target_api=target_api,
            progress=progress,
            batch_size=batch_size,
        )

        # 开始复制
        console.print("[bold green]开始复制歌曲...[/bold green]\n")
        await copy_service.copy_all_songs()

        console.print("\n[bold green]✓ 复制完成！[/bold green]")

    except Exception as e:
        logger.error(f"复制过程中发生错误: {e}", exc_info=True)
        console.print(f"\n[red]错误: {e}[/red]")
        raise
    finally:
        # 关闭客户端
        await source_api.close()
        await target_api.close()


@app.command()
def status(
    progress_file: Path = typer.Option(
        "data/progress.json",
        "--progress",
        "-p",
        help="进度文件路径",
    ),
):
    """查看当前复制进度"""
    if not progress_file.exists():
        console.print("[yellow]还没有进度记录[/yellow]")
        return

    tracker = ProgressTracker(progress_file)
    tracker.load()
    tracker.print_summary()


if __name__ == "__main__":
    app()
