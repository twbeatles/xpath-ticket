# -*- coding: utf-8 -*-
"""
XPath Explorer History Manager v4.0
Undo/Redo 히스토리 관리 모듈
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from copy import deepcopy
from threading import RLock  # RLock으로 변경하여 재진입 가능하도록 함
import json

from xpath_constants import HISTORY_MAX_SIZE


@dataclass
class HistoryState:
    """히스토리 스냅샷"""
    items_snapshot: List[Dict]  # 전체 항목의 딕셔너리 리스트
    timestamp: str
    action: str  # "add", "update", "delete", "batch_update"
    item_name: str  # 변경된 주요 항목
    description: str = ""  # 변경 설명
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'HistoryState':
        return cls(**data)


class HistoryManager:
    """Undo/Redo 히스토리 관리자 (스레드 안전)"""
    
    def __init__(self, max_history: int = HISTORY_MAX_SIZE):
        """
        Args:
            max_history: 최대 히스토리 저장 개수
        """
        self._undo_stack: List[HistoryState] = []
        self._redo_stack: List[HistoryState] = []
        self._max_history = max_history
        self._current_state: Optional[List[Dict]] = None
        self._lock = RLock()  # RLock으로 변경하여 재진입 가능 (데드락 방지)
    
    def initialize(self, items: List[Any]):
        """
        초기 상태 설정 (앱 시작 시 호출)
        
        Args:
            items: XPathItem 객체 리스트
        """
        with self._lock:
            self._current_state = self._items_to_dicts(items)
            self._undo_stack.clear()
            self._redo_stack.clear()
    
    def push_state(self, items: List[Any], action: str, item_name: str, description: str = ""):
        """
        현재 상태를 히스토리에 저장 (변경 전 호출)
        
        Args:
            items: 현재 XPathItem 객체 리스트
            action: "add", "update", "delete", "batch_update"
            item_name: 변경된 항목 이름
            description: 변경 설명
        """
        with self._lock:
            # 이전 상태를 스택에 저장
            if self._current_state is not None:
                state = HistoryState(
                    items_snapshot=deepcopy(self._current_state),
                    timestamp=datetime.now().isoformat(),
                    action=action,
                    item_name=item_name,
                    description=description
                )
                self._undo_stack.append(state)
                
                # 최대 개수 제한
                if len(self._undo_stack) > self._max_history:
                    self._undo_stack.pop(0)
            
            # 현재 상태 업데이트
            self._current_state = self._items_to_dicts(items)
            
            # 새 변경이 발생하면 redo 스택 초기화
            self._redo_stack.clear()
    
    def undo(self) -> Optional[List[Dict]]:
        """
        실행 취소
        
        Returns:
            이전 상태의 항목 딕셔너리 리스트 또는 None
        """
        with self._lock:
            if not self.can_undo():
                return None
            
            # 현재 상태를 redo 스택에 저장
            if self._current_state is not None:
                redo_state = HistoryState(
                    items_snapshot=deepcopy(self._current_state),
                    timestamp=datetime.now().isoformat(),
                    action="redo_point",
                    item_name="",
                    description="Redo point"
                )
                self._redo_stack.append(redo_state)
            
            # 이전 상태 복원
            prev_state = self._undo_stack.pop()
            self._current_state = deepcopy(prev_state.items_snapshot)
            
            return self._current_state
    
    def redo(self) -> Optional[List[Dict]]:
        """
        다시 실행
        
        Returns:
            다음 상태의 항목 딕셔너리 리스트 또는 None
        """
        with self._lock:
            if not self.can_redo():
                return None
            
            # 현재 상태를 undo 스택에 저장
            if self._current_state is not None:
                undo_state = HistoryState(
                    items_snapshot=deepcopy(self._current_state),
                    timestamp=datetime.now().isoformat(),
                    action="undo_point",
                    item_name="",
                    description="Undo point"
                )
                self._undo_stack.append(undo_state)
            
            # 다음 상태 복원
            next_state = self._redo_stack.pop()
            self._current_state = deepcopy(next_state.items_snapshot)
            
            return self._current_state
    
    def can_undo(self) -> bool:
        """Undo 가능 여부"""
        with self._lock:
            return len(self._undo_stack) > 0
    
    def can_redo(self) -> bool:
        """Redo 가능 여부"""
        with self._lock:
            return len(self._redo_stack) > 0
    
    def get_undo_description(self) -> str:
        """다음 Undo 동작 설명"""
        with self._lock:
            if len(self._undo_stack) > 0:
                state = self._undo_stack[-1]
                return f"{state.action}: {state.item_name}"
            return ""
    
    def get_redo_description(self) -> str:
        """다음 Redo 동작 설명"""
        with self._lock:
            if len(self._redo_stack) > 0:
                state = self._redo_stack[-1]
                return f"Redo: {state.item_name}"
            return ""
    
    def get_history_list(self, limit: int = 20) -> List[Dict]:
        """
        최근 히스토리 목록 반환
        
        Returns:
            [{timestamp, action, item_name, description}, ...]
        """
        with self._lock:
            history = []
            for state in reversed(self._undo_stack[-limit:]):
                history.append({
                    'timestamp': state.timestamp,
                    'action': state.action,
                    'item_name': state.item_name,
                    'description': state.description
                })
            return history
    
    def clear(self):
        """히스토리 초기화"""
        with self._lock:
            self._undo_stack.clear()
            self._redo_stack.clear()
    
    def _items_to_dicts(self, items: List[Any]) -> List[Dict]:
        """XPathItem 객체 리스트를 딕셔너리 리스트로 변환 (메모리 최적화)"""
        # 메모리 절약을 위해 대용량 필드 제외
        EXCLUDE_FIELDS = {'alternatives', 'element_attributes', 'screenshot_path'}
        
        result = []
        for item in items:
            if hasattr(item, 'to_dict'):
                item_dict = item.to_dict()
                # 대용량 필드 제외
                optimized = {k: v for k, v in item_dict.items() if k not in EXCLUDE_FIELDS}
                result.append(optimized)
            elif hasattr(item, '__dict__'):
                item_dict = dict(item.__dict__)
                optimized = {k: v for k, v in item_dict.items() if k not in EXCLUDE_FIELDS}
                result.append(optimized)
            else:
                result.append(dict(item))
        return result
    
    @property
    def undo_count(self) -> int:
        """Undo 가능 횟수"""
        with self._lock:
            return len(self._undo_stack)
    
    @property
    def redo_count(self) -> int:
        """Redo 가능 횟수"""
        with self._lock:
            return len(self._redo_stack)


# 테스트용
if __name__ == "__main__":
    from dataclasses import dataclass
    
    @dataclass
    class MockItem:
        name: str
        xpath: str
        
        def to_dict(self):
            return {'name': self.name, 'xpath': self.xpath}
    
    # 테스트
    manager = HistoryManager(max_history=10)
    
    items = [MockItem("item1", "//div[1]")]
    manager.initialize(items)
    
    print("=== Initial State ===")
    print(f"Undo: {manager.can_undo()}, Redo: {manager.can_redo()}")
    
    # 항목 추가
    manager.push_state(items, "add", "item2", "새 항목 추가")
    items.append(MockItem("item2", "//div[2]"))
    print("\n=== After Add ===")
    print(f"Undo: {manager.can_undo()}, Redo: {manager.can_redo()}")
    print(f"Undo desc: {manager.get_undo_description()}")
    
    # 항목 수정
    manager.push_state(items, "update", "item1", "XPath 변경")
    items[0] = MockItem("item1", "//div[@id='new']")
    print("\n=== After Update ===")
    print(f"Undo count: {manager.undo_count}")
    
    # Undo
    restored = manager.undo()
    print("\n=== After Undo ===")
    print(f"Restored items: {restored}")
    print(f"Can redo: {manager.can_redo()}")
    
    # Redo
    restored = manager.redo()
    print("\n=== After Redo ===")
    print(f"Restored items: {restored}")
