# -*- coding: utf-8 -*-
"""Playwright scan selector assets."""

SCAN_SELECTORS = {
    'button': 'button, [role="button"], input[type="button"], input[type="submit"]',
    'input': 'input:not([type="hidden"]), textarea, select',
    'link': 'a[href]',
    'interactive': 'button, a[href], input:not([type="hidden"]), select, textarea, [onclick], [role="button"]',
    'form': 'form, input, select, textarea',
    'all': '*'
}
