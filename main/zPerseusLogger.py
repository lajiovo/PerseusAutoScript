"""
==================== 使用教程 ====================
1. 基本逻辑：
   - 导入本模块后，会自动全局重定向 sys.stdout (普通 print) 为 [INFO] 级别日志。
   - 重定向 sys.stderr (如未捕获的报错/异常) 为 [ERROR] 级别日志。
   - 如果存在 loguru 则优先调用 loguru 进行日志记录；若不存在则回退到标准的 logging 方案，并补齐 loguru 独有但 logging 默认没有的日志等级（TRACE=5, VERBOSE=15, NOTICE=25, SUCCESS=35, FATAL=60），同时报错 error 但不影响程序继续。

2. 常用用法：
   - 普通打印 (INFO 级别)：
     print("这是一条普通消息")  
     --> 输出: 2026-08-22 10:00:00 - [INFO] - 这条是普通消息

   - 打印警告/其他级别 (推荐方式)：
     import logging
     logging.warning("这是一条警告消息")
     logging.debug("这是一条调试消息")

   - 方便的快捷函数 (像 print 一样输出警告)：
     logger_print("这是一条警告消息", level="warning")
     logger_print("发生重大错误！", level="critical")
==================================================
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler

# ==================== 配置区 ====================
from zConfig import get_config

# 配置区
LOG_DIR = get_config("logger.log_dir", default="logs")
LOG_FILE_NAME = get_config("logger.log_file_name", default="app.log")
MAX_BYTES = get_config("logger.max_bytes", default=512 * 1024)
BACKUP_COUNT = get_config("logger.backup_count", default=10)
# ================================================

# 尝试导入 loguru
try:
    from loguru import logger as loguru_logger
    HAS_LOGURU = True
except Exception as e:
    HAS_LOGURU = False
    err_msg = f"[zPerseusLogger Error] 尝试导入 loguru 失败，已降级为 standard logging: {e}"
    try:
        logging.error(err_msg)
    except Exception:
        sys.stderr.write(err_msg + "\n")

if HAS_LOGURU:
    class LoguruWriter:
        def __init__(self, level="INFO"):
            self.level = level
            self._buffer = ""

        def write(self, message):
            if not message:
                return 0

            # 统一转换为 str
            if isinstance(message, bytes):
                message = message.decode("utf-8", errors="replace")
            elif not isinstance(message, str):
                message = str(message)

            self._buffer += message

            # 按行输出
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)

                if line.strip():
                    loguru_logger.opt(depth=1).log(
                        self.level,
                        line.strip()
                    )

            return len(message)

        def flush(self):
            if self._buffer.strip():
                loguru_logger.opt(depth=1).log(
                    self.level,
                    self._buffer.strip()
                )
            self._buffer = ""

        def isatty(self):
            return False

        @property
        def encoding(self):
            return "utf-8"

    if not isinstance(sys.stdout, LoguruWriter):
        os.makedirs(LOG_DIR, exist_ok=True)
        log_path = os.path.join(LOG_DIR, LOG_FILE_NAME)

        try:
            loguru_logger.remove()
        except Exception:
            pass

        if sys.__stdout__ is not None:
            loguru_logger.add(
                sys.__stdout__,
                format="[{level}] {message}",
                level="INFO"
            )

        class SafeRotatingFileHandler(RotatingFileHandler):
            def doRollover(self):
                try:
                    super().doRollover()
                except Exception:
                    pass

        loguru_logger.add(
            log_path,
            rotation=MAX_BYTES,
            retention=BACKUP_COUNT,
            encoding="utf-8",
            format="{time:YYYY-MM-DD HH:mm:ss} - [{level}] - {message}",
            level="DEBUG"
        )

        sys.stdout = LoguruWriter("INFO")
        sys.stderr = LoguruWriter("ERROR")

    logger = loguru_logger

    def logger_print(message, level="warning"):
        """
        可选的快捷打印函数：通过 loguru 输出
        支持级别: 'trace', 'debug', 'info', 'success', 'warning' (或 'warn'), 'error', 'critical' / 'fatal', 等
        """
        lvl = str(level).lower()
        if lvl == 'warn':
            lvl = 'warning'
        
        try:
            if hasattr(loguru_logger, lvl):
                getattr(loguru_logger, lvl)(message)
            else:
                loguru_logger.info(message)
        except Exception as e:
            loguru_logger.error(f"[zPerseusLogger Error] logger_print 异常: {e}")
            loguru_logger.info(message)

else:
    TRACE_LEVEL = 5
    VERBOSE_LEVEL = 15
    NOTICE_LEVEL = 25
    SUCCESS_LEVEL = 35
    FATAL_LEVEL = 60

    logging.addLevelName(TRACE_LEVEL, "TRACE")
    logging.addLevelName(VERBOSE_LEVEL, "VERBOSE")
    logging.addLevelName(NOTICE_LEVEL, "NOTICE")
    logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")
    logging.addLevelName(FATAL_LEVEL, "FATAL")

    def _log_trace(self, message, *args, **kwargs):
        if self.isEnabledFor(TRACE_LEVEL):
            self._log(TRACE_LEVEL, message, args, **kwargs)

    def _log_verbose(self, message, *args, **kwargs):
        if self.isEnabledFor(VERBOSE_LEVEL):
            self._log(VERBOSE_LEVEL, message, args, **kwargs)

    def _log_notice(self, message, *args, **kwargs):
        if self.isEnabledFor(NOTICE_LEVEL):
            self._log(NOTICE_LEVEL, message, args, **kwargs)

    def _log_success(self, message, *args, **kwargs):
        if self.isEnabledFor(SUCCESS_LEVEL):
            self._log(SUCCESS_LEVEL, message, args, **kwargs)

    def _log_fatal(self, message, *args, **kwargs):
        if self.isEnabledFor(FATAL_LEVEL):
            self._log(FATAL_LEVEL, message, args, **kwargs)

    setattr(logging.Logger, "trace", _log_trace)
    setattr(logging.Logger, "verbose", _log_verbose)
    setattr(logging.Logger, "notice", _log_notice)
    setattr(logging.Logger, "success", _log_success)
    setattr(logging.Logger, "fatal", _log_fatal)

    setattr(logging, "trace", lambda msg, *args, **kwargs: logging.getLogger("GlobalPrintLogger").trace(msg, *args, **kwargs))
    setattr(logging, "verbose", lambda msg, *args, **kwargs: logging.getLogger("GlobalPrintLogger").verbose(msg, *args, **kwargs))
    setattr(logging, "notice", lambda msg, *args, **kwargs: logging.getLogger("GlobalPrintLogger").notice(msg, *args, **kwargs))
    setattr(logging, "success", lambda msg, *args, **kwargs: logging.getLogger("GlobalPrintLogger").success(msg, *args, **kwargs))
    setattr(logging, "fatal", lambda msg, *args, **kwargs: logging.getLogger("GlobalPrintLogger").fatal(msg, *args, **kwargs))

    class LoggerWriter:
        """把 print 的输出转发给 logging 处理器"""
        def __init__(self, logger_func):
            self.logger_func = logger_func
            self._buffer = ''

        def write(self, message):
            self._buffer += message
            while '\n' in self._buffer:
                line, self._buffer = self._buffer.split('\n', 1)
                if line.strip():
                    self.logger_func(line)

        def flush(self):
            if self._buffer.strip():
                self.logger_func(self._buffer)
                self._buffer = ''

    if not isinstance(sys.stdout, LoggerWriter):
        os.makedirs(LOG_DIR, exist_ok=True)
        log_path = os.path.join(LOG_DIR, LOG_FILE_NAME)

        logger = logging.getLogger("GlobalPrintLogger")
        logger.setLevel(logging.INFO)
        logger.propagate = False

        if sys.__stdout__ is not None:
            console_handler = logging.StreamHandler(sys.__stdout__)
            console_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
            logger.addHandler(console_handler)

        class SafeRotatingFileHandler(RotatingFileHandler):
            def doRollover(self):
                try:
                    super().doRollover()
                except Exception:
                    pass

        file_handler = SafeRotatingFileHandler(
            filename=log_path,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s'))
        logger.addHandler(file_handler)

        sys.stdout = LoggerWriter(logger.info)
        sys.stderr = LoggerWriter(logger.error)

    def logger_print(message, level="warning"):
        """
        可选的快捷打印函数：像 print 一样输出警告、调试或严重错误日志
        支持级别: 'trace', 'debug', 'verbose', 'info', 'notice', 'success', 'warning' (或 'warn'), 'error', 'critical', 'fatal'
        """
        lvl_map = {
            'trace': logger.trace,
            'debug': logger.debug,
            'verbose': logger.verbose,
            'info': logger.info,
            'notice': logger.notice,
            'success': logger.success,
            'warning': logger.warning,
            'warn': logger.warning,
            'error': logger.error,
            'critical': logger.critical,
            'fatal': logger.fatal
        }
        log_func = lvl_map.get(str(level).lower(), logger.warning)
        log_func(message)

if HAS_LOGURU:
    print("[Success]Loguru启动成功")
