#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)-12s] [%(levelname)-5s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("YouTubeClient")


class YouTubeClient:
    def __init__(self):
        log.info("YouTube-Client initialisiert (Stub).")

    def connect(self):
        pass

    def post(self, text: str):
        log.info("[YouTube-POST] %s", text)
