# -*- coding: utf-8 -*-
"""Browser and worker timing constants."""

BROWSER_CHECK_INTERVAL = 2000  # ms - 브라우저 연결 상태 확인 주기
SEARCH_DEBOUNCE_MS = 300       # ms - 검색 입력 디바운스
LIVE_PREVIEW_DEBOUNCE_MS = 500  # ms - 라이브 프리뷰 디바운스
DEFAULT_WINDOW_SIZE = (1400, 900)
MAX_FRAME_DEPTH = 5            # 프레임 재귀 탐색 최대 깊이
FRAME_CACHE_DURATION = 2.0     # 프레임 캐시 유효 시간 (초)
VALIDATION_MISS_TTL_SECONDS = 2.0  # Validation miss 캐시 TTL (초)
WORKER_WAIT_TIMEOUT = 2000     # ms - 워커 종료 대기 시간
PICKER_POLL_INTERVAL_MS = 200  # ms - 피커 감시 폴링 주기
PICKER_ACTIVE_CHECK_TICKS = 5  # 폴링 N회마다 활성 상태 체크
