# -*- coding: utf-8 -*-
"""UI-facing constants and label helpers."""

# UI 상수
BROWSER_CHECK_INTERVAL = 2000  # ms - 브라우저 연결 상태 확인 주기
SEARCH_DEBOUNCE_MS = 300       # ms - 검색 입력 디바운스
LIVE_PREVIEW_DEBOUNCE_MS = 500  # ms - 라이브 프리뷰 디바운스
DEFAULT_WINDOW_SIZE = (1400, 900)
CATEGORY_LABELS = {
    "login": "로그인",
    "booking": "예매",
    "seat": "좌석",
    "captcha": "캡차",
    "popup": "팝업",
    "common": "공통",
    "main": "메인",
    "payment": "결제",
    "district": "구역",
    "window": "창",
}

CATEGORY_LABEL_TO_VALUE = {label: value for value, label in CATEGORY_LABELS.items()}


def category_to_label(value: str) -> str:
    """카테고리 내부값을 한글 표시명으로 변환."""
    return CATEGORY_LABELS.get(value, value)


def category_to_value(label_or_value: str) -> str:
    """카테고리 표시명/내부값을 내부값으로 정규화."""
    return CATEGORY_LABEL_TO_VALUE.get(label_or_value, label_or_value)
