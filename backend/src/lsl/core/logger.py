from __future__ import annotations

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(pathname)s:%(lineno)d %(message)s"


def configure_logging(*, level: int = logging.INFO) -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=level,
            format=LOG_FORMAT,
        )
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    formatter = logging.Formatter(LOG_FORMAT)
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)
