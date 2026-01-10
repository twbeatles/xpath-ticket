# -*- coding: utf-8 -*-
"""
XPath Explorer Configuration
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from datetime import datetime
from xpath_constants import SITE_PRESETS

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
    items: List[XPathItem] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
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
        items = []
        for item_data in data.get('items', []):
            # 하위 호환성: 새 필드가 없는 기존 JSON도 로드 가능하도록
            item = XPathItem(
                name=item_data.get('name', ''),
                xpath=item_data.get('xpath', ''),
                category=item_data.get('category', 'common'),
                description=item_data.get('description', ''),
                css_selector=item_data.get('css_selector', ''),
                is_verified=item_data.get('is_verified', False),
                element_tag=item_data.get('element_tag', ''),
                element_text=item_data.get('element_text', ''),
                found_window=item_data.get('found_window', ''),
                found_frame=item_data.get('found_frame', ''),
                # v3.3 신규 필드 (기본값 처리)
                is_favorite=item_data.get('is_favorite', False),
                tags=item_data.get('tags', []),
                test_count=item_data.get('test_count', 0),
                success_count=item_data.get('success_count', 0),
                last_tested=item_data.get('last_tested', ''),
                sort_order=item_data.get('sort_order', 0),
                # v4.0 신규 필드
                alternatives=item_data.get('alternatives', []),
                element_attributes=item_data.get('element_attributes', {}),
                screenshot_path=item_data.get('screenshot_path', ''),
                ai_generated=item_data.get('ai_generated', False)
            )
            items.append(item)
        return cls(
            name=data.get('name', ''),
            url=data.get('url', ''),
            login_url=data.get('login_url', ''),
            description=data.get('description', ''),
            items=items,
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', '')
        )
    
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
        for item in self.items:
            if item.name == name:
                return item
        return None
    
    def add_or_update(self, item: XPathItem):
        existing = self.get_item(item.name)
        if existing:
            idx = self.items.index(existing)
            self.items[idx] = item
        else:
            self.items.append(item)
        self.updated_at = datetime.now().isoformat()
    
    def remove_item(self, name: str):
        self.items = [item for item in self.items if item.name != name]
        self.updated_at = datetime.now().isoformat()
    
    def get_categories(self) -> List[str]:
        return list(set(item.category for item in self.items))
