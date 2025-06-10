import logging
from typing import TYPE_CHECKING

from .config import settings

if TYPE_CHECKING:
    from .services.report_ingestion_service import ReportIngestionService

logger = logging.getLogger(__name__)

async def trigger_report_ingestion_task(report_ingestion_service: 'ReportIngestionService'):
    """
    異步任務，用於觸發報告擷取服務。
    現在從 .config.settings 讀取資料夾 ID。
    """
    base_log_props = {
        "task_name": "trigger_report_ingestion_task",
        "inbox_folder_id": settings.WOLF_IN_FOLDER_ID,
        "processed_folder_id": settings.WOLF_PROCESSED_FOLDER_ID
    }

    if not settings.WOLF_IN_FOLDER_ID or not settings.WOLF_PROCESSED_FOLDER_ID:
        logger.error(
            "設定中的 WOLF_IN_FOLDER_ID 或 WOLF_PROCESSED_FOLDER_ID 未設定。排程的報告擷取任務無法執行。",
            extra={"props": {**base_log_props, "error": "missing_folder_ids_in_settings"}}
        )
        # No debug log for settings here as it might expose them if they are partially set.
        return

    logger.info(
        f"排程任務觸發：開始從 Drive 資料夾 '{settings.WOLF_IN_FOLDER_ID}' 擷取報告。",
        extra={"props": {**base_log_props, "status": "started"}}
    )
    try:
        # ReportIngestionService methods are expected to do their own detailed logging with context
        success_count, fail_count = await report_ingestion_service.ingest_reports_from_drive_folder(
            inbox_folder_id=settings.WOLF_IN_FOLDER_ID,
            processed_folder_id=settings.WOLF_PROCESSED_FOLDER_ID
        )
        logger.info(
            f"排程任務完成：成功擷取 {success_count} 個報告，失敗 {fail_count} 個。",
            extra={"props": {**base_log_props, "status": "completed", "success_count": success_count, "fail_count": fail_count}}
        )
    except Exception as e:
        logger.error(
            f"排程的報告擷取任務執行時發生未預期錯誤: {e}",
            exc_info=True,
            extra={"props": {**base_log_props, "status": "exception", "error": str(e)}}
        )
