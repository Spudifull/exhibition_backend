import logging.config
from colorlog import ColoredFormatter

SUCCESS_LEVEL_NAME = 25
logging.addLevelName(SUCCESS_LEVEL_NAME, "SUCCESS")


def success(self, message, *args, **kws) -> None:
    if self.isEnabledFor(SUCCESS_LEVEL_NAME):
        self._log(SUCCESS_LEVEL_NAME, message, args, **kws)


logging.Logger.success = success

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "color": {
            "()": "colorlog.ColoredFormatter",
            "format": "%(asctime)s %(log_color)s%(levelname)-8s%(reset)s %(log_color)s%(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "log_colors": {
                "DEBUG": "cyan",
                "INFO": "white",
                "WARNING": "yellow",
                "CRITICAL": "red",
                "SUCCESS": "bold_green",
            }
        }
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "stream": "ext://sys.stdout",
            "formatter": "color",
        }
    },
    "loggers": {
        "": {
            "handlers": ["stdout"],
            "level": "DEBUG",
            "propagate": False
        }
    },
}
