---
name: browser
description: 'Browse web pages and capture screenshots using Chrome DevTools. Use when asked to open websites, navigate to URLs, or take screenshots of web pages.'
metadata:
  version: '1'
---

# Browser Skill

Browse web pages and capture screenshots using Chrome DevTools.

## Available Tools

- `navigate_page` - Navigate to a URL
- `take_screenshot` - Capture a screenshot of the current page
- `new_page` - Open a new browser tab
- `list_pages` - List open browser tabs

## Workflow

1. **Navigate** to the target URL using `navigate_page`
2. **Screenshot** the page using `take_screenshot`
3. **Analyze** captured screenshots with `look_at` for visual analysis

## Tips

- Use `take_screenshot` with `fullPage: true` to capture entire page layouts
- Navigate to specific states before capturing (e.g., after login, after interactions)
- Capture multiple viewport sizes for responsive design review
- Use `list_pages` to see all open tabs and switch between them
