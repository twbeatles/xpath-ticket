# -*- coding: utf-8 -*-
"""
XPath Explorer Constants & Presets
"""

# 버전 정보
APP_VERSION = "v4.2"
APP_TITLE = f"티켓 사이트 XPath 탐색기 {APP_VERSION}"

# 브라우저 스크립트
PICKER_SCRIPT = '''
(function() {
    // 이미 활성화되어 있으면 무시
    if (window.__pickerActive) return "ALREADY_ACTIVE";
    
    window.__pickerActive = true;
    window.__pickerResult = null;
    window.__pickerLocked = false;  // 선택 고정 상태
    window.__lockedData = null;     // 고정된 요소 정보
    
    // 스타일 추가
    var style = document.createElement('style');
    style.id = '__pickerStyle';
    style.textContent = `
        .__picker_highlight {
            outline: 3px solid #89b4fa !important;
            outline-offset: 2px !important;
            background-color: rgba(137, 180, 250, 0.2) !important;
            cursor: crosshair !important;
        }
        .__picker_locked {
            outline: 4px solid #f9e2af !important;
            outline-offset: 2px !important;
            background-color: rgba(249, 226, 175, 0.25) !important;
        }
        .__picker_tooltip {
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: #1e1e2e;
            color: #cdd6f4;
            padding: 16px 24px;
            border-radius: 12px;
            font-family: 'Pretendard', 'Malgun Gothic', sans-serif;
            font-size: 14px;
            z-index: 2147483647;
            border: 1px solid #89b4fa;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
            max-width: 90%;
            word-break: break-all;
            line-height: 1.5;
            user-select: text !important;
        }
        .__picker_tooltip.locked {
            border-color: #f9e2af;
            background: #181825;
            box-shadow: 0 10px 40px rgba(249, 226, 175, 0.2);
        }
        .__picker_info {
            position: fixed;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%);
            background: #cba6f7;
            color: #1e1e2e;
            padding: 12px 24px;
            border-radius: 50px;
            font-size: 15px;
            font-weight: 700;
            z-index: 2147483647;
            box-shadow: 0 5px 25px rgba(0,0,0,0.3);
        }
        .__picker_info.locked {
            background: #a6e3a1;
            color: #1e1e2e;
        }
        .__picker_btn {
            display: inline-block;
            margin: 8px 8px 0 0;
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.2s;
        }
        .__picker_btn_copy {
            background: #89b4fa;
            color: #1e1e2e;
        }
        .__picker_btn_copy:hover {
            background: #b4befe;
        }
        .__picker_btn_unlock {
            background: #f38ba8;
            color: #1e1e2e;
        }
        .__picker_btn_unlock:hover {
            background: #eba0ac;
        }
    `;
    document.head.appendChild(style);
    
    // 툴팁 생성
    var tooltip = document.createElement('div');
    tooltip.className = '__picker_tooltip';
    tooltip.style.display = 'none';
    document.body.appendChild(tooltip);
    
    // 안내 메시지
    var info = document.createElement('div');
    info.className = '__picker_info';
    info.innerHTML = '🎯 요소 선택 모드 (ESC: 취소, 클릭: 고정/해제)';
    document.body.appendChild(info);
    
    var lastElement = null;
    
    // XPath 생성 함수
    function getXPath(element) {
        if (element.id !== '')
            return '//*[@id="' + element.id + '"]';
        if (element === document.body)
            return '/html/body';
            
        var ix = 0;
        var siblings = element.parentNode.childNodes;
        for (var i = 0; i < siblings.length; i++) {
            var sibling = siblings[i];
            if (sibling === element)
                return getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
            if (sibling.nodeType === 1 && sibling.tagName === element.tagName)
                ix++;
        }
    }
    
    // CSS Selector 생성 함수
    function getCssSelector(el) {
        if (!(el instanceof Element)) return;
        var path = [];
        while (el.nodeType === Node.ELEMENT_NODE) {
            var selector = el.nodeName.toLowerCase();
            if (el.id) {
                selector += '#' + el.id;
                path.unshift(selector);
                break;
            } else {
                var sib = el, nth = 1;
                while (sib = sib.previousElementSibling) {
                    if (sib.nodeName.toLowerCase() == selector)
                        nth++;
                }
                if (nth != 1)
                    selector += ":nth-of-type("+nth+")";
            }
            path.unshift(selector);
            el = el.parentNode;
        }
        return path.join(" > ");
    }
    
    // 마우스 오버 핸들러
    function onMouseOver(e) {
        if (window.__pickerLocked) return;
        
        e.stopPropagation();
        var target = e.target;
        
        if (target.classList.contains('__picker_info') || 
            target.classList.contains('__picker_tooltip') ||
            target.id === '__pickerStyle') return;
            
        if (lastElement) {
            lastElement.classList.remove('__picker_highlight');
        }
        
        target.classList.add('__picker_highlight');
        lastElement = target;
        
        // 정보 업데이트
        var xpath = getXPath(target);
        var css = getCssSelector(target);
        var tag = target.tagName.toLowerCase();
        var text = target.textContent.trim().substring(0, 50);
        if (text.length === 50) text += '...';
        
        tooltip.style.display = 'block';
        tooltip.innerHTML = `
            <div><strong>Tag:</strong> ${tag}</div>
            <div><strong>XPath:</strong> ${xpath}</div>
            <div><strong>CSS:</strong> ${css}</div>
            ${text ? `<div><strong>Text:</strong> ${text}</div>` : ''}
            <div style="margin-top:5px; font-size:11px; color:#aaa;">(Click to lock/unlock capture)</div>
        `;
    }
    
    // 클릭 핸들러
    function onClick(e) {
        // Picker UI 클릭은 무시
        if (e.target.closest('.__picker_tooltip') || e.target.closest('.__picker_info')) {
            // 버튼 클릭 처리 등은 여기서 별도로 하지 않음 (버튼에 이벤트 리스너 추가 방식 권장)
            return;
        }
        
        e.preventDefault();
        e.stopPropagation();
        
        var target = e.target;
        
        if (window.__pickerLocked) {
           // 이미 잠겨있으면 잠금 해제
           unlock();
           return;
        }
        
        // 잠금(선택)
        lock(target);
    }
    
    function lock(target) {
        window.__pickerLocked = true;
        target.classList.add('__picker_locked');
        
        var xpath = getXPath(target);
        var css = getCssSelector(target);
        var tag = target.tagName.toLowerCase();
        var text = target.textContent.trim();
        
        // 툴팁 업데이트 (버튼 추가)
        tooltip.className = '__picker_tooltip locked';
        tooltip.innerHTML = `
            <div style="color:#ffd166; margin-bottom:5px;">🔒 LOCKED (Press 'Use This' to select)</div>
            <div><strong>Tag:</strong> ${tag}</div>
            <div style="margin:5px 0; padding:5px; background:rgba(0,0,0,0.3); border-radius:4px;">${xpath}</div>
            <button class="__picker_btn __picker_btn_copy" id="__btnUse">Use This Element</button>
            <button class="__picker_btn __picker_btn_unlock" id="__btnUnlock">Unlock</button>
        `;
        
        document.getElementById('__btnUse').onclick = function() {
            window.__pickerResult = {
                xpath: xpath,
                css: css,
                tag: tag,
                text: text
            };
        };
        
        document.getElementById('__btnUnlock').onclick = function() {
            unlock();
        };
        
        window.__lockedData = {
            element: target,
            xpath: xpath,
            css: css,
            tag: tag,
            text: text
        };
        
        info.className = '__picker_info locked';
        info.innerHTML = '🔒 요소가 고정되었습니다. "Use This Element"를 클릭하여 선택하세요.';
    }
    
    function unlock() {
        window.__pickerLocked = false;
        if (window.__lockedData && window.__lockedData.element) {
            window.__lockedData.element.classList.remove('__picker_locked');
        }
        window.__lockedData = null;
        
        tooltip.className = '__picker_tooltip';
        info.className = '__picker_info';
        info.innerHTML = '🎯 요소 선택 모드 (ESC: 취소, 클릭: 고정/해제)';
        
        // 마우스 호버 다시 활성화될 때 툴팁 내용 리셋은 onMouseOver에서 처리됨
    }
    
    // 키보드 핸들러 (ESC)
    function onKeyDown(e) {
        if (e.key === 'Escape') {
            if (window.__pickerLocked) {
                unlock();
            } else {
                window.__pickerResult = "CANCELLED";
            }
        }
    }
    
    document.addEventListener('mouseover', onMouseOver, true);
    document.addEventListener('click', onClick, true);
    document.addEventListener('keydown', onKeyDown, true);
    
    // 정리 함수 저장
    window.__pickerCleanup = function() {
        document.removeEventListener('mouseover', onMouseOver, true);
        document.removeEventListener('click', onClick, true);
        document.removeEventListener('keydown', onKeyDown, true);
        
        if (lastElement) lastElement.classList.remove('__picker_highlight');
        if (style.parentNode) style.parentNode.removeChild(style);
        if (tooltip.parentNode) tooltip.parentNode.removeChild(tooltip);
        if (info.parentNode) info.parentNode.removeChild(info);
        
        // 잠금 해제
        if (window.__lockedData && window.__lockedData.element) {
            window.__lockedData.element.classList.remove('__picker_locked');
        }
        
        window.__pickerActive = false;
        window.__pickerLocked = false;
        window.__lockedData = null;
    };
    
    return "STARTED";
})();
'''

# 사이트 프리셋
SITE_PRESETS = {
    "인터파크": {
        "name": "인터파크 티켓 (NOL)",
        "url": "https://tickets.interpark.com",
        "login_url": "https://accounts.interpark.com/login/form/interpark",
        "description": "인터파크 티켓 예매 (야놀자 통합 로그인)",
        "items": [
            # 로그인 (2024년 12월 기준 - Cloudflare Turnstile 보호)
            {"name": "login_id", "xpath": '//input[@name="username"]', "category": "login", "desc": "아이디 입력 (name 속성)"},
            {"name": "login_pw", "xpath": '//input[@name="password"]', "category": "login", "desc": "비밀번호 입력 (name 속성)"},
            {"name": "login_submit", "xpath": '//button[contains(., "로그인")]', "category": "login", "desc": "로그인 버튼 (Cloudflare 인증 후 표시)"},
            {"name": "remember_me", "xpath": '//*[@id="rememberMe"]', "category": "login", "desc": "로그인 상태 유지 체크박스"},
            {"name": "old_login_btn", "xpath": '//button[contains(., "기존 인터파크")]', "category": "login", "desc": "기존 인터파크 계정 로그인 버튼"},
            # 메인 페이지
            {"name": "main_login_btn", "xpath": '//button[contains(@class, "login")]', "category": "main", "desc": "메인 페이지 로그인 버튼"},
            {"name": "search_input", "xpath": '//input[@type="search"]', "category": "main", "desc": "검색 입력창"},
            # 예매
            {"name": "book_button", "xpath": '//a[contains(@class, "is-primary")]', "category": "booking", "desc": "예매하기 버튼"},
            {"name": "book_button_alt", "xpath": '//a[contains(text(), "예매하기")]', "category": "booking", "desc": "예매 버튼 (텍스트)"},
            {"name": "date_area", "xpath": '//*[@id="productSide"]/div/div[1]', "category": "booking", "desc": "날짜 선택 영역"},
            {"name": "round_list", "xpath": '//ul[contains(@class, "roundList")]/li', "category": "booking", "desc": "회차 목록"},
            # 좌석 (iframe 내부)
            {"name": "seat_iframe", "xpath": "//*[@id='ifrmSeat']", "category": "seat", "desc": "좌석 iframe"},
            {"name": "seat_detail_frame", "xpath": "ifrmSeatDetail", "category": "seat", "desc": "좌석상세 iframe (name)"},
            {"name": "seat_area", "xpath": '//*[@id="divSeatArray"]', "category": "seat", "desc": "좌석 배열"},
            {"name": "seat_grade", "xpath": '//*[@id="divGrade"]', "category": "seat", "desc": "좌석 등급"},
            {"name": "next_step", "xpath": '//*[@id="NextStepImage"]', "category": "seat", "desc": "다음단계"},
            {"name": "seat_confirm", "xpath": '//*[@id="btnConfirm"]', "category": "seat", "desc": "좌석 확인"},
            # 캡차
            {"name": "captcha_img", "xpath": "//*[@id='imgCaptcha']", "category": "captcha", "desc": "캡차 이미지"},
            {"name": "captcha_input", "xpath": "//*[@id='txtCaptcha']", "category": "captcha", "desc": "캡차 입력"},
            {"name": "captcha_confirm", "xpath": '//a[contains(text(), "확인")]', "category": "captcha", "desc": "캡차 확인"},
            {"name": "captcha_reload", "xpath": '//a[contains(text(), "새로고침")]', "category": "captcha", "desc": "캡차 새로고침"},
        ]
    },
    "멜론티켓": {
        "name": "멜론티켓",
        "url": "https://ticket.melon.com",
        "login_url": "https://member.melon.com/muid/web/login/login_inform.htm",
        "description": "멜론티켓 예매 (카카오/멜론ID 로그인)",
        "items": [
            # 로그인 (2024년 12월 기준 - 검증됨)
            {"name": "melon_login_btn", "xpath": '//button[contains(@class, "melon")]', "category": "login", "desc": "멜론 ID 로그인 버튼 (폼 표시)"},
            {"name": "login_id", "xpath": '//*[@id="id"]', "category": "login", "desc": "아이디 입력"},
            {"name": "login_pw", "xpath": '//*[@id="pwd"]', "category": "login", "desc": "비밀번호 입력"},
            {"name": "login_submit", "xpath": '//*[@id="btnLogin"]', "category": "login", "desc": "로그인 버튼"},
            {"name": "kakao_login", "xpath": '//button[contains(@class, "kakao")]', "category": "login", "desc": "카카오 로그인 버튼"},
            # 예매
            {"name": "book_button", "xpath": '//a[contains(@class, "btn_book")]', "category": "booking", "desc": "예매하기"},
            {"name": "date_select", "xpath": '//div[contains(@class, "date_select")]', "category": "booking", "desc": "날짜 선택"},
            {"name": "time_select", "xpath": '//ul[contains(@class, "time_list")]/li', "category": "booking", "desc": "시간 선택"},
            # 좌석
            {"name": "seat_frame", "xpath": '//iframe[contains(@id, "seat")]', "category": "seat", "desc": "좌석 iframe"},
            {"name": "seat_area", "xpath": '//*[@id="seatArea"]', "category": "seat", "desc": "좌석 영역"},
            {"name": "next_btn", "xpath": '//button[contains(text(), "다음")]', "category": "seat", "desc": "다음 버튼"},
            {"name": "confirm_btn", "xpath": '//button[contains(text(), "선택완료")]', "category": "seat", "desc": "선택완료 버튼"},
        ]
    },
    "YES24": {
        "name": "YES24 티켓",
        "url": "https://ticket.yes24.com",
        "login_url": "https://www.yes24.com/Templates/FTLogin.aspx",
        "description": "YES24 티켓 예매",
        "items": [
            # 로그인 (2024년 12월 기준 - 검증됨)
            {"name": "login_id", "xpath": '//*[@id="SMemberID"]', "category": "login", "desc": "아이디 입력"},
            {"name": "login_pw", "xpath": '//*[@id="SMemberPassword"]', "category": "login", "desc": "비밀번호 입력"},
            {"name": "login_submit", "xpath": '//*[@id="btnLogin"]', "category": "login", "desc": "로그인 버튼"},
            {"name": "auto_login", "xpath": '//*[@id="chkAutoLogin"]', "category": "login", "desc": "자동 로그인 체크박스"},
            # 예매
            {"name": "book_button", "xpath": '//a[contains(@class, "btn_reserve")]', "category": "booking", "desc": "예매하기"},
            {"name": "calendar", "xpath": '//div[contains(@class, "calendar")]', "category": "booking", "desc": "캘린더"},
            {"name": "date_cell", "xpath": '//td[contains(@class, "sel")]', "category": "booking", "desc": "선택 가능한 날짜"},
            {"name": "time_list", "xpath": '//ul[@class="time-list"]/li', "category": "booking", "desc": "시간 목록"},
            {"name": "round_select", "xpath": '//select[@id="ddlRound"]', "category": "booking", "desc": "회차 선택 드롭다운"},
            # 좌석
            {"name": "seat_iframe", "xpath": '//iframe[@name="ifrmSeat"]', "category": "seat", "desc": "좌석 iframe"},
            {"name": "grade_list", "xpath": '//div[@class="grade-list"]//li', "category": "seat", "desc": "등급 목록"},
            {"name": "seat_available", "xpath": '//div[@title and string-length(@title)>0]', "category": "seat", "desc": "선택 가능한 좌석"},
            {"name": "confirm_btn", "xpath": '//button[contains(text(), "선택완료")]', "category": "seat", "desc": "선택완료"},
        ]
    },
    "티켓링크": {
        "name": "티켓링크 (봇 감지)",
        "url": "https://www.ticketlink.co.kr",
        "login_url": "https://www.ticketlink.co.kr/login",
        "description": "티켓링크 예매 (⚠️ 자동화 도구 감지 - 수동 확인 필요)",
        "items": [
            # 로그인 (봇 감지로 인해 자동화 제한)
            {"name": "login_id", "xpath": '//*[@id="userId"]', "category": "login", "desc": "ID 입력 (봇 감지 주의)"},
            {"name": "login_pw", "xpath": '//*[@id="userPwd"]', "category": "login", "desc": "PW 입력"},
            {"name": "login_submit", "xpath": '//button[@type="submit"]', "category": "login", "desc": "로그인"},
            # 예매
            {"name": "book_button", "xpath": '//a[contains(@class, "btn_book")]', "category": "booking", "desc": "예매"},
            {"name": "date_picker", "xpath": '//div[contains(@class, "datepicker")]', "category": "booking", "desc": "날짜"},
            # 좌석
            {"name": "seat_frame", "xpath": '//iframe[contains(@src, "seat")]', "category": "seat", "desc": "좌석 iframe"},
            {"name": "seat_map", "xpath": '//*[@id="seatMap"]', "category": "seat", "desc": "좌석맵"},
        ]
    },
    "네이버 예약": {
        "name": "네이버 예약",
        "url": "https://booking.naver.com",
        "login_url": "https://nid.naver.com/nidlogin.login",
        "description": "네이버 예약 (공연/전시)",
        "items": [
            # 로그인 (네이버 통합 로그인)
            {"name": "login_id", "xpath": '//*[@id="id"]', "category": "login", "desc": "네이버 아이디"},
            {"name": "login_pw", "xpath": '//*[@id="pw"]', "category": "login", "desc": "네이버 비밀번호"},
            {"name": "login_submit", "xpath": '//*[@id="log.login"]', "category": "login", "desc": "로그인 버튼"},
            # 예매
            {"name": "book_button", "xpath": '//button[contains(text(), "예약하기")]', "category": "booking", "desc": "예약하기 버튼"},
            {"name": "date_select", "xpath": '//div[contains(@class, "calendar")]//button', "category": "booking", "desc": "날짜 선택"},
        ]
    },
    "빈 템플릿": {
        "name": "새 사이트",
        "url": "",
        "login_url": "",
        "description": "사용자 정의 사이트",
        "items": []
    }
}

# =============================================================================
# Playwright & 탐지 우회 관련 상수
# =============================================================================

# UI 상수
BROWSER_CHECK_INTERVAL = 2000  # ms - 브라우저 연결 상태 확인 주기
SEARCH_DEBOUNCE_MS = 300       # ms - 검색 입력 디바운스
DEFAULT_WINDOW_SIZE = (1400, 900)
MAX_FRAME_DEPTH = 5            # 프레임 재귀 탐색 최대 깊이
FRAME_CACHE_DURATION = 2.0     # 프레임 캐시 유효 시간 (초)
WORKER_WAIT_TIMEOUT = 2000     # ms - 워커 종료 대기 시간

# 통계 및 히스토리 설정
HISTORY_MAX_SIZE = 50          # Undo/Redo 최대 저장 개수
STATISTICS_SAVE_INTERVAL = 5.0 # 통계 저장 간격 (초)

# 실제 브라우저 User-Agent 목록 (2026년 1월 기준 업데이트)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
]

# 탐지 우회 스크립트 (WebDriver 플래그 숨김, fingerprint 위장)
STEALTH_SCRIPT = """
() => {
    // WebDriver 플래그 제거
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });
    
    // Chrome 속성 추가 (자동화 도구 탐지 우회)
    window.chrome = {
        runtime: {},
        loadTimes: function() {},
        csi: function() {},
        app: {}
    };
    
    // Permissions 위장
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );
    
    // Languages 설정
    Object.defineProperty(navigator, 'languages', {
        get: () => ['ko-KR', 'ko', 'en-US', 'en']
    });
    
    // 플러그인 위장
    Object.defineProperty(navigator, 'plugins', {
        get: () => [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
            { name: 'Native Client', filename: 'internal-nacl-plugin' }
        ]
    });
    
    // Canvas fingerprint 랜덤화
    const originalGetContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type, attributes) {
        const context = originalGetContext.call(this, type, attributes);
        if (type === '2d') {
            const originalGetImageData = context.getImageData;
            context.getImageData = function(x, y, width, height) {
                const imageData = originalGetImageData.call(this, x, y, width, height);
                // 약간의 노이즈 추가
                for (let i = 0; i < imageData.data.length; i += 4) {
                    imageData.data[i] = Math.max(0, Math.min(255, imageData.data[i] + (Math.random() * 2 - 1)));
                }
                return imageData;
            };
        }
        return context;
    };
    
    // WebGL 렌더러 위장
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) return 'Intel Inc.';
        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
        return getParameter.call(this, parameter);
    };
    
    // Headless 탐지 우회
    Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: () => 8
    });
    
    Object.defineProperty(navigator, 'deviceMemory', {
        get: () => 8
    });
}
"""

# 스캔할 요소 셀렉터
SCAN_SELECTORS = {
    'button': 'button, [role="button"], input[type="button"], input[type="submit"]',
    'input': 'input:not([type="hidden"]), textarea, select',
    'link': 'a[href]',
    'interactive': 'button, a[href], input:not([type="hidden"]), select, textarea, [onclick], [role="button"]',
    'form': 'form, input, select, textarea',
    'all': '*'
}
