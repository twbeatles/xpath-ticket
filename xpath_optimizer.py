# -*- coding: utf-8 -*-
"""
XPath Explorer Optimizer v4.0
XPath 자동 최적화 및 대안 생성 모듈
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
import re


@dataclass
class XPathAlternative:
    """XPath 대안"""
    xpath: str
    strategy: str  # "id", "class", "text", "ancestor", "relative", "attributes"
    robustness_score: float  # 0-100 안정성 점수
    description: str


class XPathOptimizer:
    """XPath 자동 최적화 및 대안 생성기"""
    
    def __init__(self):
        # 안정성 점수 가중치
        self.strategy_weights = {
            "id": 95,       # ID 기반 - 가장 안정적
            "data-attr": 90, # data-* 속성 기반
            "name": 85,     # name 속성 기반
            "class": 70,    # class 기반
            "text": 65,     # 텍스트 기반
            "ancestor": 60, # 부모-자식 관계 기반
            "relative": 50, # 상대 경로 기반
            "attributes": 45, # 기타 속성 조합
            "index": 30,    # 인덱스 기반 - 가장 취약
        }
    
    def _escape_xpath_text(self, text: str) -> str:
        """
        XPath 문자열에서 따옴표 이스케이프
        
        두 종류의 따옴표가 모두 포함된 경우 concat 함수 사용
        """
        if not text:
            return '""'
        
        if '"' in text and "'" in text:
            # 둘 다 있으면 concat 사용 (수정된 버전)
            parts = []
            for i, segment in enumerate(text.split('"')):
                if segment:
                    parts.append(f'"{segment}"')
                if i < text.count('"'):
                    parts.append("'\"'")
            return 'concat(' + ', '.join(parts) + ')'
        elif '"' in text:
            # 큰따옴표만 있으면 작은따옴표로 감싸기
            return f"'{text}'"
        else:
            # 기본: 큰따옴표로 감싸기
            return f'"{text}"'
    
    def generate_alternatives(self, element_info: Dict) -> List[XPathAlternative]:
        """
        요소 정보를 바탕으로 여러 XPath 대안 생성
        
        Args:
            element_info: {
                'tag': str,
                'id': str,
                'name': str,
                'class': str,
                'text': str,
                'attributes': dict,
                'parent_tag': str,
                'parent_id': str,
                'parent_class': str,
                'index': int,  # 형제 중 순서
                'original_xpath': str
            }
        
        Returns:
            List[XPathAlternative]: 안정성 점수 순으로 정렬된 대안 목록
        """
        alternatives = []
        tag = element_info.get('tag', '*').lower()
        elem_id = element_info.get('id', '')
        elem_name = element_info.get('name', '')
        elem_class = element_info.get('class', '')
        elem_text = element_info.get('text', '')
        attrs = element_info.get('attributes', {})
        parent_tag = element_info.get('parent_tag', '')
        parent_id = element_info.get('parent_id', '')
        parent_class = element_info.get('parent_class', '')
        index = element_info.get('index', 0)
        
        # 1. ID 기반 (가장 안정적)
        if elem_id:
            alternatives.append(XPathAlternative(
                xpath=f'//{tag}[@id="{elem_id}"]',
                strategy="id",
                robustness_score=self.strategy_weights["id"],
                description=f"ID 속성 사용: {elem_id}"
            ))
            # 축약형 ID
            alternatives.append(XPathAlternative(
                xpath=f'//*[@id="{elem_id}"]',
                strategy="id",
                robustness_score=self.strategy_weights["id"] - 2,
                description=f"ID만 사용 (태그 무관)"
            ))
        
        # 2. data-* 속성 기반
        for attr_name, attr_value in attrs.items():
            if attr_name.startswith('data-') and attr_value:
                alternatives.append(XPathAlternative(
                    xpath=f'//{tag}[@{attr_name}="{attr_value}"]',
                    strategy="data-attr",
                    robustness_score=self.strategy_weights["data-attr"],
                    description=f"data 속성 사용: {attr_name}"
                ))
        
        # 3. name 속성 기반
        if elem_name:
            alternatives.append(XPathAlternative(
                xpath=f'//{tag}[@name="{elem_name}"]',
                strategy="name",
                robustness_score=self.strategy_weights["name"],
                description=f"name 속성 사용: {elem_name}"
            ))
        
        # 4. Class 기반
        if elem_class:
            classes = elem_class.split()
            
            # 전체 class 일치
            if len(classes) == 1:
                alternatives.append(XPathAlternative(
                    xpath=f'//{tag}[@class="{elem_class}"]',
                    strategy="class",
                    robustness_score=self.strategy_weights["class"],
                    description=f"정확한 class 일치"
                ))
            
            # contains로 주요 class 매칭
            for cls in classes[:3]:  # 처음 3개 클래스만
                if len(cls) > 3 and not cls.startswith('_'):  # 의미 있는 클래스만
                    alternatives.append(XPathAlternative(
                        xpath=f'//{tag}[contains(@class, "{cls}")]',
                        strategy="class",
                        robustness_score=self.strategy_weights["class"] - 5,
                        description=f"class 포함: {cls}"
                    ))
        
        # 5. 텍스트 기반
        if elem_text and len(elem_text.strip()) > 0:
            text = elem_text.strip()
            escaped_text = self._escape_xpath_text(text)
            
            # 정확한 텍스트 일치 (짧은 경우)
            if len(text) <= 30:
                alternatives.append(XPathAlternative(
                    xpath=f'//{tag}[text()={escaped_text}]',
                    strategy="text",
                    robustness_score=self.strategy_weights["text"],
                    description="정확한 텍스트 일치"
                ))
            
            # 텍스트 포함 (긴 경우)
            short_text = text[:20] if len(text) > 20 else text
            short_escaped = self._escape_xpath_text(short_text)
            alternatives.append(XPathAlternative(
                xpath=f'//{tag}[contains(text(), {short_escaped})]',
                strategy="text",
                robustness_score=self.strategy_weights["text"] - 5,
                description=f"텍스트 포함: {short_text}..."
            ))
            
            # normalize-space 사용
            alternatives.append(XPathAlternative(
                xpath=f'//{tag}[normalize-space()={escaped_text}]',
                strategy="text",
                robustness_score=self.strategy_weights["text"] - 3,
                description="정규화된 텍스트 일치"
            ))
        
        # 6. 부모-자식 관계 (Ancestor) 기반
        if parent_id:
            alternatives.append(XPathAlternative(
                xpath=f'//*[@id="{parent_id}"]//{tag}',
                strategy="ancestor",
                robustness_score=self.strategy_weights["ancestor"] + 10,
                description=f"부모 ID 기준: #{parent_id}"
            ))
            
            if elem_class:
                first_class = elem_class.split()[0]
                alternatives.append(XPathAlternative(
                    xpath=f'//*[@id="{parent_id}"]//{tag}[contains(@class, "{first_class}")]',
                    strategy="ancestor",
                    robustness_score=self.strategy_weights["ancestor"] + 5,
                    description=f"부모 ID + class 조합"
                ))
        
        if parent_tag and parent_class:
            first_parent_class = parent_class.split()[0]
            alternatives.append(XPathAlternative(
                xpath=f'//{parent_tag}[contains(@class, "{first_parent_class}")]//{tag}',
                strategy="ancestor",
                robustness_score=self.strategy_weights["ancestor"],
                description=f"부모 태그+class 기준"
            ))
        
        # 7. 여러 속성 조합
        if len(attrs) >= 2:
            # 의미 있는 속성만 필터링
            meaningful_attrs = {k: v for k, v in attrs.items() 
                              if v and k not in ['style', 'onclick', 'onmouseover'] 
                              and len(v) < 50}
            
            if len(meaningful_attrs) >= 2:
                attr_conditions = [f'@{k}="{v}"' for k, v in list(meaningful_attrs.items())[:2]]
                alternatives.append(XPathAlternative(
                    xpath=f'//{tag}[{" and ".join(attr_conditions)}]',
                    strategy="attributes",
                    robustness_score=self.strategy_weights["attributes"],
                    description="다중 속성 조합"
                ))
        
        # 8. 인덱스 기반 (마지막 수단)
        if index > 0:
            alternatives.append(XPathAlternative(
                xpath=f'(//{tag})[{index}]',
                strategy="index",
                robustness_score=self.strategy_weights["index"],
                description=f"인덱스 기반: {index}번째"
            ))
        
        # 9. 원본 XPath 추가 (있는 경우)
        original = element_info.get('original_xpath', '')
        if original and not any(alt.xpath == original for alt in alternatives):
            alternatives.append(XPathAlternative(
                xpath=original,
                strategy="original",
                robustness_score=50,  # 중간 점수
                description="Picker로 캡처된 원본 XPath"
            ))
        
        # 안정성 점수로 정렬 (높은 순)
        alternatives.sort(key=lambda x: x.robustness_score, reverse=True)
        
        return alternatives
    
    def optimize_xpath(self, xpath: str) -> str:
        """
        XPath 최적화 (불필요한 부분 제거)
        
        예: /html/body/div[1]/div[2]/button → //button[@id="submit"] (ID가 있는 경우)
        """
        optimized = xpath
        
        # /html/body 시작 부분 제거
        if optimized.startswith('/html/body'):
            optimized = optimized.replace('/html/body', '', 1)
            if not optimized.startswith('//'):
                optimized = '/' + optimized
        
        # [1] 불필요한 첫 번째 인덱스 제거 (선택적)
        # optimized = re.sub(r'\[1\](?=/)', '', optimized)
        
        return optimized
    
    def simplify_xpath(self, xpath: str, element_info: Dict) -> Optional[str]:
        """
        XPath를 더 간단한 형태로 변환 시도
        
        Returns:
            간소화된 XPath 또는 None (불가능한 경우)
        """
        elem_id = element_info.get('id', '')
        tag = element_info.get('tag', '*').lower()
        
        # ID가 있으면 가장 간단한 형태로
        if elem_id:
            return f'//{tag}[@id="{elem_id}"]'
        
        # name이 있으면 그 다음
        elem_name = element_info.get('name', '')
        if elem_name:
            return f'//{tag}[@name="{elem_name}"]'
        
        return None
    
    def calculate_robustness(self, xpath: str) -> int:
        """
        XPath의 안정성 점수 계산 (0-100)
        
        높은 점수 = 사이트 변경에 강함
        """
        score = 50  # 기본 점수
        
        # ID 사용 시 높은 점수
        if '@id=' in xpath:
            score += 40
        
        # data-* 속성 사용
        if 'data-' in xpath and '@' in xpath:
            score += 30
        
        # name 속성 사용
        if '@name=' in xpath:
            score += 25
        
        # text() 사용
        if 'text()' in xpath or 'normalize-space()' in xpath:
            score += 15
        
        # class 사용
        if '@class' in xpath or "contains(@class" in xpath:
            score += 10
        
        # 인덱스 사용 시 감점
        index_count = len(re.findall(r'\[\d+\]', xpath))
        score -= index_count * 10
        
        # 긴 경로 감점
        depth = xpath.count('/')
        if depth > 10:
            score -= (depth - 10) * 2
        
        return max(0, min(100, score))


# 테스트용
if __name__ == "__main__":
    optimizer = XPathOptimizer()
    
    # 테스트 요소 정보
    test_element = {
        'tag': 'button',
        'id': 'submit-btn',
        'name': '',
        'class': 'btn btn-primary submit-button',
        'text': '로그인',
        'attributes': {
            'type': 'submit',
            'data-action': 'login'
        },
        'parent_tag': 'form',
        'parent_id': 'login-form',
        'parent_class': 'auth-form',
        'index': 1,
        'original_xpath': '/html/body/div/form/button'
    }
    
    alternatives = optimizer.generate_alternatives(test_element)
    
    print("=== XPath 대안 목록 ===")
    for alt in alternatives:
        print(f"[{alt.robustness_score:3.0f}점] {alt.strategy:12s} | {alt.xpath}")
        print(f"         {alt.description}")
        print()
