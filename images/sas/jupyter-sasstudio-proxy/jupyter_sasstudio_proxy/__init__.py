import os
import logging

logger = logging.getLogger(__name__)
logger.setLevel("INFO")

def setup_sasstudio():
  def _get_cmd():
    return [
      "bash",
      "-c",
      "/usr/local/SASHome/studioconfig/sasstudio.sh start && cat"
    ]

  return {
    "command": _get_cmd,
    "timeout": 60,
    "port": 38080,
    "launcher_entry": {
      "title": "SAS Studio"
    },
  }
