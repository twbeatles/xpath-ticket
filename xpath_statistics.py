# -*- coding: utf-8 -*-
"""
XPath Explorer Statistics Manager
테스트 통계 관리 모듈
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import json
from pathlib import Path


@dataclass
class TestRecord:
    """개별 테스트 기록"""
    item_name: str
    xpath: str
    success: bool
    timestamp: str
    frame_path: str = ""
    error_msg: str = ""


@dataclass 
class ItemStatistics:
    """항목별 통계"""
    name: str
    total_tests: int = 0
    successful_tests: int = 0
    failed_tests: int = 0
    last_test_time: str = ""
    last_success_time: str = ""
    last_failure_time: str = ""
    
    @property
    def success_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return (self.successful_tests / self.total_tests) * 100


class StatisticsManager:
    """테스트 통계 관리자"""
    
    def __init__(self, storage_path: Path = None):
        """
        Args:
            storage_path: 통계 저장 경로 (기본: ~/.xpath_explorer/statistics.json)
        """
        if storage_path is None:
            storage_path = Path.home() / '.xpath_explorer' / 'statistics.json'
        
        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._stats: Dict[str, ItemStatistics] = {}
        self._history: List[TestRecord] = []
        self._load()
    
    def _load(self):
        """통계 데이터 로드"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # 항목별 통계
                for name, stat_data in data.get('stats', {}).items():
                    self._stats[name] = ItemStatistics(**stat_data)
                
                # 히스토리 (최근 500개만)
                for record_data in data.get('history', [])[-500:]:
                    self._history.append(TestRecord(**record_data))
                    
            except Exception as e:
                print(f"통계 로드 실패: {e}")
    
    def _save(self):
        """통계 데이터 저장"""
        try:
            data = {
                'stats': {name: asdict(stat) for name, stat in self._stats.items()},
                'history': [asdict(r) for r in self._history[-500:]]  # 최근 500개만
            }
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"통계 저장 실패: {e}")
    
    def record_test(self, item_name: str, xpath: str, success: bool, 
                    frame_path: str = "", error_msg: str = ""):
        """
        테스트 결과 기록
        
        Args:
            item_name: 항목 이름
            xpath: 테스트한 XPath
            success: 성공 여부
            frame_path: 프레임 경로 (있는 경우)
            error_msg: 에러 메시지 (실패 시)
        """
        now = datetime.now().isoformat()
        
        # 통계 업데이트
        if item_name not in self._stats:
            self._stats[item_name] = ItemStatistics(name=item_name)
        
        stat = self._stats[item_name]
        stat.total_tests += 1
        stat.last_test_time = now
        
        if success:
            stat.successful_tests += 1
            stat.last_success_time = now
        else:
            stat.failed_tests += 1
            stat.last_failure_time = now
        
        # 히스토리 추가
        record = TestRecord(
            item_name=item_name,
            xpath=xpath,
            success=success,
            timestamp=now,
            frame_path=frame_path,
            error_msg=error_msg
        )
        self._history.append(record)
        
        # 자동 저장
        self._save()
    
    def get_item_stats(self, item_name: str) -> Optional[ItemStatistics]:
        """항목별 통계 조회"""
        return self._stats.get(item_name)
    
    def get_all_stats(self) -> Dict[str, ItemStatistics]:
        """전체 통계 반환"""
        return self._stats.copy()
    
    def get_summary(self) -> Dict:
        """전체 요약 통계"""
        total_items = len(self._stats)
        total_tests = sum(s.total_tests for s in self._stats.values())
        total_success = sum(s.successful_tests for s in self._stats.values())
        total_failure = sum(s.failed_tests for s in self._stats.values())
        
        avg_success_rate = 0.0
        if total_tests > 0:
            avg_success_rate = (total_success / total_tests) * 100
        
        return {
            'total_items': total_items,
            'total_tests': total_tests,
            'total_success': total_success,
            'total_failure': total_failure,
            'average_success_rate': avg_success_rate
        }
    
    def get_unstable_items(self, threshold: float = 80.0) -> List[ItemStatistics]:
        """
        불안정한 항목 조회 (성공률이 threshold 미만)
        
        Args:
            threshold: 성공률 기준 (기본 80%)
        """
        unstable = []
        for stat in self._stats.values():
            if stat.total_tests > 0 and stat.success_rate < threshold:
                unstable.append(stat)
        
        # 성공률 낮은 순으로 정렬
        return sorted(unstable, key=lambda x: x.success_rate)
    
    def get_recent_history(self, limit: int = 50) -> List[TestRecord]:
        """최근 테스트 히스토리"""
        return list(reversed(self._history[-limit:]))
    
    def get_item_history(self, item_name: str, limit: int = 20) -> List[TestRecord]:
        """특정 항목의 테스트 히스토리"""
        item_records = [r for r in self._history if r.item_name == item_name]
        return list(reversed(item_records[-limit:]))
    
    def clear_statistics(self):
        """모든 통계 초기화"""
        self._stats.clear()
        self._history.clear()
        self._save()
    
    def clear_item_statistics(self, item_name: str):
        """특정 항목 통계 초기화"""
        if item_name in self._stats:
            del self._stats[item_name]
        self._history = [r for r in self._history if r.item_name != item_name]
        self._save()
