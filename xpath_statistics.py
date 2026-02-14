# -*- coding: utf-8 -*-
"""
XPath Explorer Statistics Manager
테스트 통계 관리 모듈
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import json
from pathlib import Path
import time
from threading import Lock

from xpath_constants import STATISTICS_SAVE_INTERVAL

logger = logging.getLogger('XPathExplorer')


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
        self._last_save_time = 0
        self._save_interval = STATISTICS_SAVE_INTERVAL  # 배치/스로틀링
        self._lock = Lock()  # 스레드 안전성을 위한 Lock
        self._max_history = 500  # 히스토리 최대 크기
        self._load()
    
    def _load(self):
        """통계 데이터 로드"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                with self._lock:
                    # 항목별 통계
                    for name, stat_data in data.get('stats', {}).items():
                        self._stats[name] = ItemStatistics(**stat_data)
                    
                    # 히스토리 (최근 500개만)
                    for record_data in data.get('history', [])[-self._max_history:]:
                        self._history.append(TestRecord(**record_data))
                    
            except json.JSONDecodeError as e:
                logger.error(f"통계 파일 손상, 새로 시작합니다: {e}")
                # 손상된 파일 백업 후 초기화
                try:
                    backup_path = self.storage_path.with_suffix('.json.bak')
                    self.storage_path.rename(backup_path)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"통계 로드 실패: {e}")
    
    def save(self):
        """통계 데이터 즉시 저장 (public)"""
        self._save_internal()

    def _save_internal(self):
        """통계 데이터 저장 (내부용)"""
        try:
            with self._lock:
                data = {
                    'stats': {name: asdict(stat) for name, stat in self._stats.items()},
                    'history': [asdict(r) for r in self._history[-self._max_history:]]  # 최근 500개만
                }
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._last_save_time = time.time()
        except Exception as e:
            logger.error(f"통계 저장 실패: {e}")
            
    def _schedule_save(self):
        """저장 스케줄링 (스로틀링 적용)"""
        now = time.time()
        if now - self._last_save_time > self._save_interval:
            self._save_internal()
    
    def record_test(self, item_name: str, xpath: str, success: bool, 
                    frame_path: str = "", error_msg: str = ""):
        """
        테스트 결과 기록 (스레드 안전)
        
        Args:
            item_name: 항목 이름
            xpath: 테스트한 XPath
            success: 성공 여부
            frame_path: 프레임 경로 (있는 경우)
            error_msg: 에러 메시지 (실패 시)
        """
        now = datetime.now().isoformat()
        
        with self._lock:
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
            
            # 히스토리 추가 (크기 제한 적용)
            record = TestRecord(
                item_name=item_name,
                xpath=xpath,
                success=success,
                timestamp=now,
                frame_path=frame_path,
                error_msg=error_msg
            )
            self._history.append(record)
            
            # 런타임 히스토리 크기 제한
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
        
        # 자동 저장 (스로틀링)
        self._schedule_save()
    
    def get_item_stats(self, item_name: str) -> Optional[ItemStatistics]:
        """항목별 통계 조회 (스레드 안전)"""
        with self._lock:
            return self._stats.get(item_name)
    
    def get_all_stats(self) -> Dict[str, ItemStatistics]:
        """전체 통계 반환 (스레드 안전)"""
        with self._lock:
            return self._stats.copy()
    
    def get_summary(self) -> Dict:
        """전체 요약 통계 (스레드 안전)"""
        with self._lock:
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
        불안정한 항목 조회 (성공률이 threshold 미만, 스레드 안전)
        
        Args:
            threshold: 성공률 기준 (기본 80%)
        """
        with self._lock:
            unstable = []
            for stat in self._stats.values():
                if stat.total_tests > 0 and stat.success_rate < threshold:
                    unstable.append(stat)
        
        # 성공률 낮은 순으로 정렬
        return sorted(unstable, key=lambda x: x.success_rate)
    
    def get_recent_history(self, limit: int = 50) -> List[TestRecord]:
        """최근 테스트 히스토리 (스레드 안전)"""
        with self._lock:
            return list(reversed(self._history[-limit:]))
    
    def get_item_history(self, item_name: str, limit: int = 20) -> List[TestRecord]:
        """특정 항목의 테스트 히스토리 (스레드 안전)"""
        with self._lock:
            item_records = [r for r in self._history if r.item_name == item_name]
            return list(reversed(item_records[-limit:]))
    
    def clear_statistics(self):
        """모든 통계 초기화 (스레드 안전)"""
        with self._lock:
            self._stats.clear()
            self._history.clear()
        self.save()
    
    def clear_item_statistics(self, item_name: str):
        """특정 항목 통계 초기화 (스레드 안전)"""
        with self._lock:
            if item_name in self._stats:
                del self._stats[item_name]
            self._history = [r for r in self._history if r.item_name != item_name]
        self.save()
