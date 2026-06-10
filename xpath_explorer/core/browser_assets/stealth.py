# -*- coding: utf-8 -*-
"""Playwright stealth assets."""

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
