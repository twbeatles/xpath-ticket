# -*- coding: utf-8 -*-
"""Browser, DOM, and automation constants."""

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

    function isPickerUiElement(target) {
        if (!target || !(target instanceof Element)) return true;
        return (
            target.classList.contains('__picker_info') ||
            target.classList.contains('__picker_tooltip') ||
            target.classList.contains('__picker_btn') ||
            target.id === '__pickerStyle' ||
            !!target.closest('.__picker_tooltip') ||
            !!target.closest('.__picker_info')
        );
    }

    function getHoverTarget() {
        if (lastElement && lastElement.isConnected && !isPickerUiElement(lastElement)) {
            return lastElement;
        }
        try {
            var hovered = document.querySelectorAll(':hover');
            if (!hovered || hovered.length === 0) return null;
            var candidate = hovered[hovered.length - 1];
            if (candidate && !isPickerUiElement(candidate)) {
                return candidate;
            }
        } catch (e) {
            // ignore
        }
        return null;
    }
    
    function xpathLiteral(value) {
        var text = String(value == null ? '' : value);
        if (text.indexOf('"') === -1) return '"' + text + '"';
        if (text.indexOf("'") === -1) return "'" + text + "'";
        var tokens = [];
        var parts = text.split('"');
        for (var i = 0; i < parts.length; i++) {
            if (parts[i]) tokens.push('"' + parts[i] + '"');
            if (i < parts.length - 1) tokens.push("'\"'");
        }
        return tokens.length ? 'concat(' + tokens.join(', ') + ')' : '""';
    }

    function escapeCssIdentifier(value) {
        if (window.CSS && typeof window.CSS.escape === 'function') {
            return window.CSS.escape(value);
        }
        return String(value || '').replace(/[^a-zA-Z0-9_-]/g, function(ch) { return '\\' + ch; });
    }

    // XPath 생성 함수
    function getXPath(element) {
        if (element.id !== '')
            return '//*[@id=' + xpathLiteral(element.id) + ']';
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
    
    // CSS 선택자 생성 함수
    function getCssSelector(el) {
        if (!(el instanceof Element)) return;
        var path = [];
        while (el.nodeType === Node.ELEMENT_NODE) {
            var selector = el.nodeName.toLowerCase();
            if (el.id) {
                selector += '#' + escapeCssIdentifier(el.id);
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
        
        if (isPickerUiElement(target)) return;
            
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
            <div><strong>태그:</strong> ${tag}</div>
            <div><strong>XPath:</strong> ${xpath}</div>
            <div><strong>CSS:</strong> ${css}</div>
            ${text ? `<div><strong>텍스트:</strong> ${text}</div>` : ''}
            <div style="margin-top:5px; font-size:11px; color:#aaa;">(클릭하면 캡처 고정/해제를 전환합니다)</div>
        `;
    }
    
    // 클릭 핸들러
    function onClick(e) {
        // Picker UI 클릭은 무시
        if (isPickerUiElement(e.target)) {
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
        if (!target || !target.isConnected || isPickerUiElement(target)) {
            return false;
        }
        window.__pickerLocked = true;
        if (lastElement && lastElement !== target) {
            lastElement.classList.remove('__picker_highlight');
        }
        target.classList.add('__picker_locked');
        target.classList.remove('__picker_highlight');
        lastElement = target;
        
        var xpath = getXPath(target);
        var css = getCssSelector(target);
        var tag = target.tagName.toLowerCase();
        var text = target.textContent.trim();
        
        // 툴팁 업데이트 (버튼 추가)
        tooltip.className = '__picker_tooltip locked';
        tooltip.innerHTML = `
            <div style="color:#ffd166; margin-bottom:5px;">🔒 고정됨 ('이 요소 사용'을 눌러 선택)</div>
            <div><strong>태그:</strong> ${tag}</div>
            <div style="margin:5px 0; padding:5px; background:rgba(0,0,0,0.3); border-radius:4px;">${xpath}</div>
            <button class="__picker_btn __picker_btn_copy" id="__btnUse">이 요소 사용</button>
            <button class="__picker_btn __picker_btn_unlock" id="__btnUnlock">잠금 해제</button>
        `;
        
        document.getElementById('__btnUse').onclick = function() {
            window.__pickerUseLocked();
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
        info.innerHTML = '🔒 요소가 고정되었습니다. "이 요소 사용"을 클릭하여 선택하세요.';
        return true;
    }

    function lockCurrent() {
        if (window.__pickerLocked && window.__lockedData && window.__lockedData.element && window.__lockedData.element.isConnected) {
            return true;
        }
        var target = getHoverTarget();
        if (!target) {
            info.className = '__picker_info';
            info.innerHTML = '⚠️ 고정할 요소가 없습니다. 브라우저에서 원하는 요소 위에 마우스를 올린 뒤 다시 시도하세요.';
            return false;
        }
        return lock(target);
    }

    function useLocked() {
        if (!window.__lockedData) return false;
        var text = window.__lockedData.text;
        if ((!text || text.length === 0) && window.__lockedData.element && window.__lockedData.element.isConnected) {
            text = (window.__lockedData.element.textContent || '').trim();
        }
        window.__pickerResult = {
            xpath: window.__lockedData.xpath,
            css: window.__lockedData.css,
            tag: window.__lockedData.tag,
            text: text || ''
        };
        return true;
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
        return true;
    }

    // 외부(앱 버튼)에서 호출 가능한 API
    window.__pickerLockCurrent = function() {
        return lockCurrent();
    };
    window.__pickerUnlock = function() {
        return unlock();
    };
    window.__pickerUseLocked = function() {
        return useLocked();
    };
    window.__pickerState = function() {
        return {
            active: !!window.__pickerActive,
            locked: !!window.__pickerLocked,
            hasLocked: !!window.__lockedData
        };
    };

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

# UI 상수
BROWSER_CHECK_INTERVAL = 2000  # ms - 브라우저 연결 상태 확인 주기
SEARCH_DEBOUNCE_MS = 300       # ms - 검색 입력 디바운스
LIVE_PREVIEW_DEBOUNCE_MS = 500  # ms - 라이브 프리뷰 디바운스
DEFAULT_WINDOW_SIZE = (1400, 900)
MAX_FRAME_DEPTH = 5            # 프레임 재귀 탐색 최대 깊이
FRAME_CACHE_DURATION = 2.0     # 프레임 캐시 유효 시간 (초)
VALIDATION_MISS_TTL_SECONDS = 2.0  # Validation miss 캐시 TTL (초)
WORKER_WAIT_TIMEOUT = 2000     # ms - 워커 종료 대기 시간
PICKER_POLL_INTERVAL_MS = 200  # ms - 피커 감시 폴링 주기
PICKER_ACTIVE_CHECK_TICKS = 5  # 폴링 N회마다 활성 상태 체크
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
]

# 탐지 우회 스크립트 (WebDriver/Playwright 흔적 최소화 + fingerprint 위장)
STEALTH_SCRIPT = """
() => {
    const defineGetter = (obj, prop, value) => {
        try {
            Object.defineProperty(obj, prop, {
                get: () => value,
                configurable: true,
            });
        } catch (_) {}
    };

    // 핵심 자동화 플래그 숨김
    defineGetter(navigator, 'webdriver', undefined);
    defineGetter(navigator, 'platform', 'Win32');
    defineGetter(navigator, 'vendor', 'Google Inc.');
    defineGetter(navigator, 'hardwareConcurrency', 8);
    defineGetter(navigator, 'deviceMemory', 8);
    defineGetter(navigator, 'maxTouchPoints', 0);
    defineGetter(navigator, 'languages', ['ko-KR', 'ko', 'en-US', 'en']);

    // Playwright 흔적 제거
    try { delete window.__playwright__binding__; } catch (_) {}
    try { delete window.__pwInitScripts; } catch (_) {}
    try { delete window._playwright; } catch (_) {}

    // Chrome 객체 위장
    if (!window.chrome) {
        Object.defineProperty(window, 'chrome', {
            value: {
                runtime: {},
                app: { isInstalled: false },
                csi: () => ({}),
                loadTimes: () => ({}),
            },
            configurable: true,
        });
    } else if (!window.chrome.runtime) {
        try { window.chrome.runtime = {}; } catch (_) {}
    }

    // plugins / mimeTypes 위장
    const fakePlugins = [
        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
        { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
    ];
    defineGetter(navigator, 'plugins', fakePlugins);
    defineGetter(navigator, 'mimeTypes', [
        { type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format' },
        { type: 'text/pdf', suffixes: 'pdf', description: 'Portable Document Format' },
    ]);

    // Permissions API 위장
    const permissions = navigator.permissions;
    if (permissions && typeof permissions.query === 'function') {
        try {
            const originalQuery = permissions.query.bind(permissions);
            permissions.query = (parameters) => {
                if (parameters && parameters.name === 'notifications') {
                    return Promise.resolve({ state: Notification.permission });
                }
                return originalQuery(parameters);
            };
        } catch (_) {}
    }

    // userAgentData 누락 탐지 완화
    if (!('userAgentData' in navigator)) {
        defineGetter(navigator, 'userAgentData', {
            brands: [
                { brand: 'Chromium', version: '131' },
                { brand: 'Google Chrome', version: '131' },
            ],
            mobile: false,
            platform: 'Windows',
            getHighEntropyValues: async () => ({
                architecture: 'x86',
                model: '',
                platform: 'Windows',
                platformVersion: '10.0.0',
                uaFullVersion: '131.0.0.0',
            }),
        });
    }

    // WebGL 렌더러 위장
    const patchWebGL = (proto) => {
        if (!proto || !proto.getParameter) return;
        const originalGetParameter = proto.getParameter;
        proto.getParameter = function(parameter) {
            // UNMASKED_VENDOR_WEBGL / UNMASKED_RENDERER_WEBGL
            if (parameter === 37445) return 'Intel Inc.';
            if (parameter === 37446) return 'Intel Iris OpenGL Engine';
            return originalGetParameter.call(this, parameter);
        };
    };
    patchWebGL(window.WebGLRenderingContext && window.WebGLRenderingContext.prototype);
    patchWebGL(window.WebGL2RenderingContext && window.WebGL2RenderingContext.prototype);
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
