# -*- coding: utf-8 -*-
"""
XPath Explorer Configuration
"""

from dataclasses import dataclass, field, asdict
from typing import Any, List, Dict, Optional
from datetime import datetime
from xpath_explorer.core.constants import SITE_PRESETS

CONFIG_SCHEMA_VERSION = 3


def _coerce_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y", "on"}:
            return True
        if lowered in {"false", "0", "no", "n", "off", ""}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return int(value)
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_str_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [_coerce_str(item).strip() for item in value if _coerce_str(item).strip()]
    if isinstance(value, tuple):
        return [_coerce_str(item).strip() for item in value if _coerce_str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _coerce_str_dict(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {_coerce_str(key): _coerce_str(val) for key, val in value.items()}


@dataclass
class XPathItem:
    """XPath 항목"""
    name: str
    xpath: str
    category: str
    description: str = ""
    css_selector: str = ""
    is_verified: bool = False
    element_tag: str = ""
    element_text: str = ""
    found_window: str = ""
    found_window_title: str = ""
    found_window_url: str = ""
    found_frame: str = ""
    # v3.3 신규 필드
    is_favorite: bool = False                    # 즐겨찾기 (#6)
    tags: List[str] = field(default_factory=list)  # 태그 (#6)
    test_count: int = 0                          # 테스트 횟수 (#14)
    success_count: int = 0                       # 성공 횟수 (#14)
    last_tested: str = ""                        # 마지막 테스트 시간 (#14)
    sort_order: int = 0                          # 정렬 순서 (#13)
    # v4.0 신규 필드
    alternatives: List[str] = field(default_factory=list)  # 대안 XPath 목록
    element_attributes: Dict[str, str] = field(default_factory=dict)  # 저장된 속성
    screenshot_path: str = ""                    # 스크린샷 경로
    ai_generated: bool = False                   # AI 생성 여부
    source_engine: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @property
    def success_rate(self) -> float:
        """성공률 계산"""
        if self.test_count == 0:
            return 0.0
        return (self.success_count / self.test_count) * 100
    
    def record_test(self, success: bool):
        """테스트 결과 기록"""
        self.test_count += 1
        if success:
            self.success_count += 1
        self.last_tested = datetime.now().isoformat()


@dataclass
class SiteConfig:
    """사이트 설정"""
    name: str
    url: str
    login_url: str = ""
    description: str = ""
    schema_version: int = CONFIG_SCHEMA_VERSION
    items: List[XPathItem] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    _item_index: Dict[str, int] = field(default_factory=dict, init=False, repr=False)
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.rebuild_index()
    
    def to_dict(self) -> Dict:
        return {
            'schema_version': CONFIG_SCHEMA_VERSION,
            'name': self.name,
            'url': self.url,
            'login_url': self.login_url,
            'description': self.description,
            'items': [item.to_dict() for item in self.items],
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SiteConfig':
        """
        딕셔너리에서 SiteConfig 생성 (예외 처리 포함)
        
        Args:
            data: 설정 딕셔너리
            
        Returns:
            SiteConfig 객체
            
        Raises:
            ValueError: 데이터 형식이 잘못된 경우
        """
        if not isinstance(data, dict):
            raise ValueError(f"SiteConfig.from_dict: dict 타입이 필요하지만 {type(data).__name__} 타입이 전달되었습니다")
        
        try:
            items = []
            seen_names = set()
            raw_items = data.get('items', [])
            if raw_items is None:
                raw_items = []
            if not isinstance(raw_items, list):
                raise ValueError(
                    f"SiteConfig.from_dict: items must be a list, got {type(raw_items).__name__}"
                )
            for i, item_data in enumerate(raw_items):
                if not isinstance(item_data, dict):
                    raise ValueError(f"항목 {i}: dict 타입이 필요하지만 {type(item_data).__name__} 타입입니다")

                item_name = _coerce_str(item_data.get('name', '')).strip()
                item_xpath = _coerce_str(item_data.get('xpath', '')).strip()
                if not item_name:
                    raise ValueError(f"Item {i}: name is required")
                if not item_xpath:
                    raise ValueError(f"Item {i} ({item_name}): xpath is required")
                if item_name in seen_names:
                    raise ValueError(f"Duplicate item name in config: {item_name}")
                seen_names.add(item_name)
                
                # 하위 호환성: 새 필드가 없는 기존 JSON도 로드 가능하도록
                item = XPathItem(
                    name=item_name,
                    xpath=item_xpath,
                    category=_coerce_str(item_data.get('category', 'common'), 'common') or 'common',
                    description=_coerce_str(item_data.get('description', '')),
                    css_selector=_coerce_str(item_data.get('css_selector', '')),
                    is_verified=_coerce_bool(item_data.get('is_verified', False)),
                    element_tag=_coerce_str(item_data.get('element_tag', '')),
                    element_text=_coerce_str(item_data.get('element_text', '')),
                    found_window=_coerce_str(item_data.get('found_window', '')),
                    found_window_title=_coerce_str(item_data.get('found_window_title', '')),
                    found_window_url=_coerce_str(item_data.get('found_window_url', '')),
                    found_frame=_coerce_str(item_data.get('found_frame', '')),
                    # v3.3 신규 필드 (기본값 처리)
                    is_favorite=_coerce_bool(item_data.get('is_favorite', False)),
                    tags=_coerce_str_list(item_data.get('tags', [])),
                    test_count=max(0, _coerce_int(item_data.get('test_count', 0), 0)),
                    success_count=max(0, _coerce_int(item_data.get('success_count', 0), 0)),
                    last_tested=_coerce_str(item_data.get('last_tested', '')),
                    sort_order=_coerce_int(item_data.get('sort_order', 0), 0),
                    # v4.0 신규 필드
                    alternatives=_coerce_str_list(item_data.get('alternatives', [])),
                    element_attributes=_coerce_str_dict(item_data.get('element_attributes', {})),
                    screenshot_path=_coerce_str(item_data.get('screenshot_path', '')),
                    ai_generated=_coerce_bool(item_data.get('ai_generated', False)),
                    source_engine=_coerce_str(item_data.get('source_engine', '')),
                )
                if item.success_count > item.test_count:
                    item.success_count = item.test_count
                items.append(item)
            
            return cls(
                name=_coerce_str(data.get('name', '')),
                url=_coerce_str(data.get('url', '')),
                login_url=_coerce_str(data.get('login_url', '')),
                description=_coerce_str(data.get('description', '')),
                schema_version=_coerce_int(data.get('schema_version', 1), 1),
                items=items,
                created_at=_coerce_str(data.get('created_at', '')),
                updated_at=_coerce_str(data.get('updated_at', ''))
            )
        except KeyError as e:
            raise ValueError(f"SiteConfig.from_dict: 필수 필드가 누락되었습니다 - {e}")
        except TypeError as e:
            raise ValueError(f"SiteConfig.from_dict: 데이터 형식 오류 - {e}")
    
    @classmethod
    def from_preset(cls, preset_name: str) -> 'SiteConfig':
        preset = SITE_PRESETS.get(preset_name, SITE_PRESETS["빈 템플릿"])
        items = [
            XPathItem(
                name=item["name"],
                xpath=item["xpath"],
                category=item["category"],
                description=item.get("desc", "")
            )
            for item in preset.get("items", [])
        ]
        return cls(
            name=preset["name"],
            url=preset["url"],
            login_url=preset.get("login_url", ""),
            description=preset.get("description", ""),
            items=items
        )
    
    def get_item(self, name: str) -> Optional[XPathItem]:
        idx = self._item_index.get(name)
        if idx is None:
            return None
        if 0 <= idx < len(self.items) and self.items[idx].name == name:
            return self.items[idx]
        # 외부에서 items를 직접 수정한 경우 대비
        self.rebuild_index()
        idx = self._item_index.get(name)
        if idx is not None and 0 <= idx < len(self.items):
            return self.items[idx]
        return None
    
    def add_or_update(self, item: XPathItem):
        idx = self._item_index.get(item.name)
        if idx is not None and 0 <= idx < len(self.items):
            self.items[idx] = item
        else:
            self.items.append(item)
            self._item_index[item.name] = len(self.items) - 1
            self.updated_at = datetime.now().isoformat()
            return
        self.rebuild_index()
        self.updated_at = datetime.now().isoformat()
    
    def remove_item(self, name: str):
        idx = self._item_index.get(name)
        if idx is None:
            return
        if 0 <= idx < len(self.items):
            self.items.pop(idx)
        self.rebuild_index()
        self.updated_at = datetime.now().isoformat()
    
    def get_categories(self) -> List[str]:
        return list(set(item.category for item in self.items))

    def replace_items(self, items: List[XPathItem]):
        """항목 리스트 전체 교체 후 인덱스 재구축."""
        self.items = list(items)
        self.rebuild_index()
        self.updated_at = datetime.now().isoformat()

    def rebuild_index(self):
        """name -> index 인덱스를 재구축."""
        self._item_index = {item.name: idx for idx, item in enumerate(self.items)}
