# -*- coding: utf-8 -*-
"""
XPath Explorer Diff Analyzer v4.0
XPath 비교 도구 모듈
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import difflib


@dataclass
class DiffResult:
    """XPath 비교 결과"""
    item_name: str
    xpath: str
    status: str  # "unchanged", "modified", "missing", "found"
    old_attrs: Dict[str, str] = field(default_factory=dict)
    new_attrs: Dict[str, str] = field(default_factory=dict)
    changes: List[str] = field(default_factory=list)
    element_count: int = 0
    error_msg: str = ""
    
    @property
    def has_changes(self) -> bool:
        return self.status != "unchanged"
    
    @property
    def status_icon(self) -> str:
        icons = {
            "unchanged": "✅",
            "modified": "⚠️",
            "missing": "❌",
            "found": "🔍"
        }
        return icons.get(self.status, "❓")


@dataclass
class ElementSnapshot:
    """요소 스냅샷 (비교용)"""
    xpath: str
    tag: str
    element_id: str
    element_class: str
    text: str
    attributes: Dict[str, str]
    timestamp: str
    
    def to_dict(self) -> Dict:
        return {
            'xpath': self.xpath,
            'tag': self.tag,
            'id': self.element_id,
            'class': self.element_class,
            'text': self.text,
            'attributes': self.attributes,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ElementSnapshot':
        return cls(
            xpath=data.get('xpath', ''),
            tag=data.get('tag', ''),
            element_id=data.get('id', ''),
            element_class=data.get('class', ''),
            text=data.get('text', ''),
            attributes=data.get('attributes', {}),
            timestamp=data.get('timestamp', '')
        )


class XPathDiffAnalyzer:
    """
    XPath 비交 분석기
    스냅샷 기반으로 요소 변경 사항 추적
    """
    
    MAX_SNAPSHOTS = 100  # 최대 스냅샷 저장 개수
    
    def __init__(self):
        self._snapshots: Dict[str, ElementSnapshot] = {}
        self._snapshot_order: List[str] = []  # 삽입 순서 추적
    
    def save_snapshot(self, item_name: str, element_info: Dict):
        """
        현재 요소 상태 저장 (나중에 비교용)
        크기 제한 적용됨
        
        Args:
            item_name: 항목 이름
            element_info: 요소 정보 딕셔너리
        """
        snapshot = ElementSnapshot(
            xpath=element_info.get('xpath', ''),
            tag=element_info.get('tag', ''),
            element_id=element_info.get('id', ''),
            element_class=element_info.get('class', ''),
            text=element_info.get('text', '')[:100],
            attributes=element_info.get('attributes', {}),
            timestamp=datetime.now().isoformat()
        )
        
        # 기존에 있으면 순서 유지, 없으면 새로 추가
        if item_name not in self._snapshots:
            self._snapshot_order.append(item_name)
        
        self._snapshots[item_name] = snapshot
        
        # 크기 제한 적용
        self._enforce_size_limit()
    
    def _enforce_size_limit(self):
        """스냅샷 크기 제한 강제 (오래된 것부터 제거)"""
        while len(self._snapshots) > self.MAX_SNAPSHOTS:
            if self._snapshot_order:
                oldest_key = self._snapshot_order.pop(0)
                self._snapshots.pop(oldest_key, None)
            else:
                # _snapshot_order가 비어있으면 dict에서 직접 제거
                if self._snapshots:
                    oldest_key = next(iter(self._snapshots))
                    del self._snapshots[oldest_key]
                else:
                    break
    
    def clear_old_snapshots(self, keep_count: int = 50):
        """
        오래된 스냅샷 정리 (수동 호출용)
        
        Args:
            keep_count: 유지할 스냅샷 개수
        """
        while len(self._snapshots) > keep_count:
            if self._snapshot_order:
                oldest_key = self._snapshot_order.pop(0)
                if oldest_key in self._snapshots:
                    del self._snapshots[oldest_key]
    
    def get_snapshot(self, item_name: str) -> Optional[ElementSnapshot]:
        """저장된 스냅샷 조회"""
        return self._snapshots.get(item_name)
    
    def compare_element(
        self, 
        stored_item: Any, 
        current_element_info: Dict
    ) -> DiffResult:
        """
        저장된 항목과 현재 요소 비교
        
        Args:
            stored_item: XPathItem 객체 (저장된 정보)
            current_element_info: 현재 브라우저에서 가져온 요소 정보
        
        Returns:
            DiffResult 객체
        """
        item_name = getattr(stored_item, 'name', 'unknown')
        xpath = getattr(stored_item, 'xpath', '')
        
        # 저장된 속성 (안전한 접근)
        stored_attrs = getattr(stored_item, 'element_attributes', None) or {}
        if not isinstance(stored_attrs, dict):
            stored_attrs = {}
        stored_tag = getattr(stored_item, 'element_tag', '') or ''
        
        # 현재 속성
        current_attrs = current_element_info.get('attributes', {})
        current_tag = current_element_info.get('tag', '')
        current_id = current_element_info.get('id', '')
        current_class = current_element_info.get('class', '')
        current_text = current_element_info.get('text', '')
        
        changes = []
        
        # 요소를 찾지 못한 경우
        if not current_element_info or current_element_info.get('found') == False:
            return DiffResult(
                item_name=item_name,
                xpath=xpath,
                status="missing",
                old_attrs={'tag': stored_tag, **stored_attrs},
                new_attrs={},
                changes=["요소를 찾을 수 없음"],
                error_msg=current_element_info.get('msg', '요소 없음')
            )
        
        # 저장된 정보가 없는 경우 (새로 발견)
        if not stored_tag and not stored_attrs:
            return DiffResult(
                item_name=item_name,
                xpath=xpath,
                status="found",
                old_attrs={},
                new_attrs={
                    'tag': current_tag,
                    'id': current_id,
                    'class': current_class,
                    'text': current_text[:50]
                },
                changes=["새 요소 정보 수집됨"],
                element_count=current_element_info.get('count', 1)
            )
        
        # 태그 변경 확인
        if stored_tag and current_tag and stored_tag.lower() != current_tag.lower():
            changes.append(f"태그 변경: {stored_tag} → {current_tag}")
        
        # ID 변경 확인
        stored_id = stored_attrs.get('id', '')
        if stored_id != current_id:
            if stored_id and not current_id:
                changes.append(f"ID 제거됨: {stored_id}")
            elif not stored_id and current_id:
                changes.append(f"ID 추가됨: {current_id}")
            else:
                changes.append(f"ID 변경: {stored_id} → {current_id}")
        
        # Class 변경 확인
        stored_class = stored_attrs.get('class', '')
        if stored_class != current_class:
            old_classes = set(stored_class.split())
            new_classes = set(current_class.split())
            
            added = new_classes - old_classes
            removed = old_classes - new_classes
            
            if added:
                changes.append(f"class 추가: {', '.join(added)}")
            if removed:
                changes.append(f"class 제거: {', '.join(removed)}")
        
        # 기타 속성 변경
        all_attr_keys = set(stored_attrs.keys()) | set(current_attrs.keys())
        for key in all_attr_keys:
            if key in ['id', 'class']:  # 이미 처리함
                continue
            
            old_val = stored_attrs.get(key, '')
            new_val = current_attrs.get(key, '')
            
            if old_val != new_val:
                if old_val and not new_val:
                    changes.append(f"속성 제거: {key}")
                elif not old_val and new_val:
                    changes.append(f"속성 추가: {key}={new_val[:30]}")
                else:
                    changes.append(f"속성 변경: {key}")
        
        # 결과 판정
        if changes:
            status = "modified"
        else:
            status = "unchanged"
        
        return DiffResult(
            item_name=item_name,
            xpath=xpath,
            status=status,
            old_attrs={'tag': stored_tag, **stored_attrs},
            new_attrs={
                'tag': current_tag,
                'id': current_id,
                'class': current_class,
                **current_attrs
            },
            changes=changes,
            element_count=current_element_info.get('count', 1)
        )
    
    def compare_all(
        self, 
        items: List[Any], 
        browser_manager: Any
    ) -> List[DiffResult]:
        """
        저장된 모든 항목을 현재 페이지와 비교
        
        Args:
            items: XPathItem 리스트
            browser_manager: BrowserManager 인스턴스
        
        Returns:
            DiffResult 리스트
        """
        results = []
        
        for item in items:
            xpath = getattr(item, 'xpath', '')
            if not xpath:
                continue
            
            try:
                # 브라우저에서 현재 요소 정보 가져오기
                current_info = browser_manager.get_element_info(xpath)
                
                if current_info is None:
                    current_info = {'found': False, 'msg': '요소 없음'}
                
            except Exception as e:
                current_info = {'found': False, 'msg': str(e)}
            
            result = self.compare_element(item, current_info)
            results.append(result)
        
        return results
    
    def generate_diff_report(self, results: List[DiffResult]) -> str:
        """비교 결과 리포트 생성"""
        lines = [
            "=" * 50,
            "XPath 비교 분석 리포트",
            f"분석 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 50,
            ""
        ]
        
        # 요약
        total = len(results)
        unchanged = sum(1 for r in results if r.status == "unchanged")
        modified = sum(1 for r in results if r.status == "modified")
        missing = sum(1 for r in results if r.status == "missing")
        
        lines.append(f"📊 요약: 총 {total}개 항목")
        lines.append(f"   ✅ 변경없음: {unchanged}")
        lines.append(f"   ⚠️ 수정됨: {modified}")
        lines.append(f"   ❌ 찾지못함: {missing}")
        lines.append("")
        
        # 상세
        if modified or missing:
            lines.append("-" * 50)
            lines.append("📋 상세 변경 사항")
            lines.append("-" * 50)
            
            for result in results:
                if result.status == "unchanged":
                    continue
                
                lines.append(f"\n{result.status_icon} {result.item_name}")
                lines.append(f"   XPath: {result.xpath[:60]}...")
                lines.append(f"   상태: {result.status}")
                
                if result.changes:
                    for change in result.changes:
                        lines.append(f"   - {change}")
        
        return "\n".join(lines)
    
    def get_xpath_similarity(self, xpath1: str, xpath2: str) -> float:
        """
        두 XPath의 유사도 계산 (0.0 - 1.0)
        """
        if not xpath1 or not xpath2:
            return 0.0
        
        if xpath1 == xpath2:
            return 1.0
        
        # 시퀀스 매칭으로 유사도 계산
        return difflib.SequenceMatcher(None, xpath1, xpath2).ratio()


# 테스트용
if __name__ == "__main__":
    from dataclasses import dataclass
    
    @dataclass
    class MockItem:
        name: str
        xpath: str
        element_tag: str = ""
        element_attributes: Dict = field(default_factory=dict)
    
    analyzer = XPathDiffAnalyzer()
    
    # 테스트 1: 변경 없음
    stored = MockItem(
        name="login_btn",
        xpath="//button[@id='login']",
        element_tag="button",
        element_attributes={'id': 'login', 'class': 'btn primary'}
    )
    current = {
        'found': True,
        'tag': 'button',
        'id': 'login',
        'class': 'btn primary',
        'text': '로그인',
        'attributes': {'id': 'login', 'class': 'btn primary'}
    }
    
    result = analyzer.compare_element(stored, current)
    print(f"=== Test 1: 변경 없음 ===")
    print(f"Status: {result.status_icon} {result.status}")
    print(f"Changes: {result.changes}")
    
    # 테스트 2: Class 변경
    current2 = {
        'found': True,
        'tag': 'button',
        'id': 'login',
        'class': 'btn primary large',  # large 추가
        'text': '로그인',
        'attributes': {'id': 'login', 'class': 'btn primary large'}
    }
    
    result2 = analyzer.compare_element(stored, current2)
    print(f"\n=== Test 2: Class 변경 ===")
    print(f"Status: {result2.status_icon} {result2.status}")
    print(f"Changes: {result2.changes}")
    
    # 테스트 3: 요소 없음
    current3 = {'found': False, 'msg': '요소를 찾을 수 없음'}
    
    result3 = analyzer.compare_element(stored, current3)
    print(f"\n=== Test 3: 요소 없음 ===")
    print(f"Status: {result3.status_icon} {result3.status}")
    print(f"Changes: {result3.changes}")
