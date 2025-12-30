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
    
    def to_dict(self) -> Dict:
        return asdict(self)


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
        items = [XPathItem(**item) for item in data.get('items', [])]
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
