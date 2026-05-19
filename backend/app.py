from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import json
import datetime
import re
import time
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

# 第三方社交媒体爬虫库
try:
    from facebook_scraper import get_posts
    FACEBOOK_AVAILABLE = True
except ImportError:
    FACEBOOK_AVAILABLE = False
    print("[WARN] facebook-scraper not installed, Facebook auto-fetch disabled")

try:
    import instaloader
    INSTALOADER_AVAILABLE = True
except ImportError:
    INSTALOADER_AVAILABLE = False
    print("[WARN] instaloader not installed, Instagram auto-fetch disabled")

# 启动时打印库可用状态
print(f"[INIT] Libraries: facebook={FACEBOOK_AVAILABLE}, instagram={INSTALOADER_AVAILABLE}")

# 检查 Playwright 可用性
try:
    from playwright.sync_api import sync_playwright
    print("[INIT] Playwright available")
except ImportError:
    print("[WARN] Playwright not installed, Threads auto-fetch disabled")

app = Flask(__name__)
CORS(app)

# ── Session 配置 ──────────────────────────────────────
session_direct = requests.Session()
session_direct.trust_env = False
session_direct.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

session_proxy = requests.Session()
session_proxy.trust_env = True
session_proxy.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

# ── 工具函数 ──────────────────────────────────────────

def extract_bvid(url):
    m = re.search(r'(?:bilibili\.com/video/)(BV\w+)', url)
    return m.group(1) if m else None

def extract_bilibili_dynamic_id(url):
    # 支持动态/图文详情页
    m = re.search(r'bilibili\.com/opus/(\d+)', url)
    if m:
        return m.group(1)
    m = re.search(r't\.bilibili\.com/(\d+)', url)
    if m:
        return m.group(1)
    return None

def extract_tweet_id(url):
    m = re.search(r'(?:twitter\.com|x\.com)/\w+/status/(\d+)', url)
    return m.group(1) if m else None

def extract_facebook_post_id(url):
    # 尽可能提取 post id
    m = re.search(r'facebook\.com/.*/posts/(\d+)', url)
    if m:
        return m.group(1)
    m = re.search(r'[?&]fbid=(\d+)', url)
    if m:
        return m.group(1)
    m = re.search(r'fb\.me/(\w+)', url)
    if m:
        return m.group(1)
    return None

def extract_instagram_shortcode(url):
    # 支持 /p/xxx, /reel/xxx, 以及 /username/p/xxx 格式
    m = re.search(r'instagram\.com/(?:[^/]+/)*(?:p|reel)/([^/?]+)', url)
    return m.group(1) if m else None

def extract_threads_post_id(url):
    m = re.search(r'threads\.(?:net|com)/[@\w]+/post/([^/?]+)', url)
    return m.group(1) if m else None

def extract_xiaohongshu_note_id(url):
    m = re.search(r'xiaohongshu\.com/explore/([a-zA-Z0-9]+)', url)
    return m.group(1) if m else None

def format_date(ts_or_str):
    if isinstance(ts_or_str, (int, float)) and ts_or_str > 1000000000:
        return datetime.datetime.fromtimestamp(ts_or_str).strftime('%Y-%m-%d %H:%M')
    if isinstance(ts_or_str, str) and len(ts_or_str) >= 10:
        return ts_or_str[:10]
    return '-'

# ── Bilibili 解析 ─────────────────────────────────────

def scrape_bilibili_video(bvid):
    api_url = f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}'
    headers = {'Referer': 'https://www.bilibili.com/'}
    try:
        resp = session_direct.get(api_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get('code') != 0 or not data.get('data'):
            return None
        info = data['data']
        stat = info.get('stat', {})
        pub_ts = info.get('pubdate', 0)
        return {
            "title": info.get('title', '未知标题'),
            "likes": stat.get('like', 0),
            "comments": stat.get('reply', 0),
            "shares": stat.get('share', 0),
            "favorites": stat.get('favorite', 0),
            "views": stat.get('view', 0),
            "date": format_date(pub_ts),
            "isError": False
        }
    except Exception as e:
        print(f"[Bilibili Video Error] {e}")
        return None

def scrape_bilibili_dynamic(dynamic_id):
    # 获取动态详情
    api_url = f'https://api.bilibili.com/x/polymer/web-dynamic/v1/detail?id={dynamic_id}'
    headers = {
        'Referer': 'https://t.bilibili.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        resp = session_direct.get(api_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get('code') != 0 or not data.get('data'):
            return None
        item = data['data'].get('item', {})
        modules = item.get('modules', {})
        module_stat = modules.get('module_stat', {})
        stat = module_stat.get('comment', {})
        # 动态的互动数据
        like_info = module_stat.get('like', {})
        comment_info = module_stat.get('comment', {})
        forward_info = module_stat.get('forward', {})

        # 获取标题/内容
        module_dynamic = modules.get('module_dynamic', {})
        desc = module_dynamic.get('desc', {})
        title = desc.get('text', '动态内容')[:50]

        # 发布时间
        module_author = modules.get('module_author', {})
        pub_ts = module_author.get('pub_ts', 0)

        return {
            "title": title or '动态内容',
            "likes": like_info.get('count', 0),
            "comments": comment_info.get('count', 0),
            "shares": forward_info.get('count', 0),
            "favorites": 0,
            "views": 0,
            "date": format_date(pub_ts),
            "isError": False
        }
    except Exception as e:
        print(f"[Bilibili Dynamic Error] {e}")
        return None

def scrape_bilibili(url):
    bvid = extract_bvid(url)
    if bvid:
        return scrape_bilibili_video(bvid)
    dynamic_id = extract_bilibili_dynamic_id(url)
    if dynamic_id:
        return scrape_bilibili_dynamic(dynamic_id)
    return None

# ── X (Twitter) 解析 ──────────────────────────────────

def scrape_twitter(url):
    tweet_id = extract_tweet_id(url)
    if not tweet_id:
        return None

    try:
        # 策略1: 直接抓取推文页面HTML，提取嵌入的互动数据
        resp = session_proxy.get(url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        if resp.status_code != 200:
            return None

        html = resp.text
        
        # 从HTML中提取互动数据
        def extract_field(pattern, default=0):
            m = re.search(pattern, html)
            return int(m.group(1)) if m else default

        likes = extract_field(r'"favorite_count":(\d+)')
        replies = extract_field(r'"reply_count":(\d+)')
        retweets = extract_field(r'"retweet_count":(\d+)')
        quotes = extract_field(r'"quote_count":(\d+)')
        views = extract_field(r'"view_count":(\d+)')

        # 提取推文文本
        text = ''
        text_match = re.search(r'"full_text":"([^"]+)"', html)
        if text_match:
            text = text_match.group(1).encode('utf-8').decode('unicode_escape')

        # 提取发布时间
        created_at = ''
        date_match = re.search(r'"created_at":"([^"]+)"', html)
        if date_match:
            created_at = date_match.group(1)

        # 解析时间
        date_str = '-'
        if created_at:
            try:
                dt = datetime.datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                date_str = dt.strftime('%Y-%m-%d %H:%M')
            except:
                date_str = created_at[:10] if len(created_at) >= 10 else '-'

        # 如果所有数据都是0，说明页面可能没有加载出数据（需要JS渲染）
        if likes == 0 and replies == 0 and retweets == 0 and not text:
            return None

        return {
            "title": (text[:60] + '...') if len(text) > 60 else text or f'Tweet #{tweet_id}',
            "likes": likes,
            "comments": replies,
            "shares": retweets + quotes,
            "favorites": 0,
            "views": views,
            "date": date_str,
            "isError": False
        }
    except Exception as e:
        print(f"[Twitter Error] {e}")
        return None

# ── Facebook 解析 ─────────────────────────────────────

def scrape_facebook(url):
    cookies_path = os.path.join(os.path.dirname(__file__), 'facebook_cookies.txt')

    # 如果没有 cookies，尝试无登录方式（通常会被 Facebook 拦截）
    if not os.path.exists(cookies_path):
        return {
            "title": "Facebook 需要登录",
            "likes": 0, "comments": 0, "shares": 0,
            "favorites": 0, "views": 0, "date": '-',
            "isManual": True, "isError": False,
            "note": "Facebook 需要 cookies 才能抓取。请在浏览器登录 Facebook 后导出 cookies 为 Netscape 格式，保存为 backend/facebook_cookies.txt，然后重启服务。"
        }

    try:
        # 使用 requests + cookies 直接抓取
        from http.cookiejar import MozillaCookieJar

        jar = MozillaCookieJar(cookies_path)
        jar.load()

        fb_session = requests.Session()
        fb_session.cookies = jar
        fb_session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })

        resp = fb_session.get(url, timeout=15, allow_redirects=True)

        if resp.status_code != 200 or 'login' in resp.url:
            return {
                "title": "Facebook cookies 失效",
                "likes": 0, "comments": 0, "shares": 0,
                "favorites": 0, "views": 0, "date": '-',
                "isManual": True, "isError": False,
                "note": "Cookies 可能已过期或需要重新验证。请重新导出 facebook_cookies.txt 并重启服务。"
            }

        html = resp.text

        # 检查是否是错误页面
        if '<title>Error' in html or 'Something went wrong' in html:
            return {
                "title": "Facebook 返回错误",
                "likes": 0, "comments": 0, "shares": 0,
                "favorites": 0, "views": 0, "date": '-',
                "isManual": True, "isError": False,
                "note": "Facebook 返回错误页面。请检查 cookies 是否有效，或稍后重试。"
            }

        # 策略：找到包含帖子反应数据的 script 标签
        # 该 script 包含多个反应类型（大爱、赞、抱抱、哇等），需要求和
        total_reactions = 0
        shares = 0
        comments = 0
        title = 'Facebook 帖子'
        date_str = '-'

        # 从 script 标签中提取（Facebook 将帖子数据放在 script 中）
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
        
        for script in scripts:
            # 找到包含 reaction_count 和 share_count 的 script
            if '"reaction_count"' in script and '"share_count"' in script:
                # 提取所有反应类型的数字（大爱、赞、抱抱、哇等）
                # 这些通常是独立的 reaction_count 条目
                reaction_counts = re.findall(r'"reaction_count":(\d+)', script)
                if reaction_counts:
                    try:
                        nums = [int(x) for x in reaction_counts]
                        # 过滤掉 0 值（有些 block 的 reaction_count 是 0）
                        nums = [x for x in nums if x > 0]
                        if nums:
                            # 求和得到总反应数
                            total_reactions = sum(nums)
                    except:
                        pass
                
                # 提取分享数（i18n_share_count 更可靠）
                i18n_shares = re.findall(r'"i18n_share_count":"([^"]+)"', script)
                if i18n_shares:
                    try:
                        # 过滤掉非数字的值，取第一个有效的
                        for val in i18n_shares:
                            clean = val.replace(',', '').replace('\u00a0', '')
                            if clean.isdigit():
                                shares = int(clean)
                                break
                    except:
                        pass
                
                # 如果 i18n 没有，尝试纯数字
                if shares == 0:
                    share_counts = re.findall(r'"share_count":(\d+)', script)
                    if share_counts:
                        try:
                            nums = [int(x) for x in share_counts if int(x) > 0]
                            if nums:
                                shares = nums[0]
                        except:
                            pass
                
                # 提取评论数
                i18n_comments = re.findall(r'"i18n_comment_count":"([^"]+)"', script)
                if i18n_comments:
                    try:
                        for val in i18n_comments:
                            clean = val.replace(',', '').replace('\u00a0', '')
                            if clean.isdigit():
                                comments = int(clean)
                                break
                    except:
                        pass
                
                if comments == 0:
                    comment_counts = re.findall(r'"comment_count":(\d+)', script)
                    if comment_counts:
                        try:
                            nums = [int(x) for x in comment_counts if int(x) > 0]
                            if nums:
                                comments = nums[0]
                        except:
                            pass
                
                # 只处理第一个匹配的 script（通常包含主帖子数据）
                break
        
        # 如果 script 中没有找到评论数，尝试从全局 HTML 中提取中文格式 "X 条评论"
        if comments == 0:
            cn_comments = re.findall(r'(\d+)\s*条评论', html)
            if cn_comments:
                try:
                    nums = [int(x) for x in cn_comments if int(x) > 0]
                    if nums:
                        comments = nums[0]
                except:
                    pass

        # 如果 script 中没有找到数据，回退到全局搜索
        if total_reactions == 0:
            i18n_reactions = re.findall(r'"i18n_reaction_count":"([^"]+)"', html)
            if i18n_reactions:
                try:
                    nums = []
                    for x in set(i18n_reactions):
                        clean = x.replace(',', '').replace('\u00a0', '')
                        if clean.isdigit():
                            nums.append(int(clean))
                    if nums:
                        total_reactions = max(nums)
                except:
                    pass

        if shares == 0:
            i18n_shares = re.findall(r'"i18n_share_count":"([^"]+)"', html)
            if i18n_shares:
                try:
                    for val in i18n_shares:
                        clean = val.replace(',', '').replace('\u00a0', '')
                        if clean.isdigit():
                            shares = int(clean)
                            break
                except:
                    pass

        # 提取帖子文本
        text_matches = re.findall(r'"text":"([^"]{20,500})"', html)
        skip_keywords = ['Meta AI', 'terms', 'agree', 'Remember password', '记住密码', '下次使用', 'Comments are turned off', '评论功能已关闭']
        for text in text_matches:
            if not any(kw in text for kw in skip_keywords):
                try:
                    decoded = text.encode('utf-8').decode('unicode_escape')
                    title = decoded[:80]
                    break
                except:
                    title = text[:80]
                    break
        
        # 如果还是没找到，尝试从 title 标签获取
        if title == 'Facebook 帖子':
            title_match = re.search(r'<title>([^<]+)</title>', html)
            if title_match:
                page_title = title_match.group(1)
                # 移除 "- Facebook" 或 "- Page Name" 后缀
                page_title = re.sub(r'\s*-\s*Facebook.*$', '', page_title)
                page_title = re.sub(r'\s*\.\.\..*$', '', page_title)
                if len(page_title) > 10:
                    title = page_title[:80]

        # 提取发布时间
        time_match = re.search(r'"created_time":(\d+)', html)
        if time_match:
            try:
                ts = int(time_match.group(1))
                date_str = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
            except:
                pass

        if date_str == '-':
            time_match = re.search(r'"publish_time":(\d+)', html)
            if time_match:
                try:
                    ts = int(time_match.group(1))
                    date_str = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
                except:
                    pass

        return {
            "title": title,
            "likes": total_reactions,
            "comments": comments,
            "shares": shares,
            "favorites": 0,
            "views": 0,
            "date": date_str,
            "isError": False,
            "source": "facebook-html"
        }
    except Exception as e:
        print(f"[Facebook Error] {e}")
        return {
            "title": "Facebook 抓取失败",
            "likes": 0, "comments": 0, "shares": 0,
            "favorites": 0, "views": 0, "date": '-',
            "isManual": True, "isError": False,
            "note": f"抓取错误: {str(e)[:100]}。请检查 cookies 文件或手动填入数据。"
        }

# ── Instagram 解析 ────────────────────────────────────

def scrape_instagram(url):
    shortcode = extract_instagram_shortcode(url)
    if not shortcode:
        return None

    print(f"[Instagram Debug] INSTALOADER_AVAILABLE={INSTALOADER_AVAILABLE}, shortcode={shortcode}")

    if not INSTALOADER_AVAILABLE:
        return {
            "title": f"Instagram 帖子 {shortcode}",
            "likes": 0, "comments": 0, "shares": 0,
            "favorites": 0, "views": 0, "date": '-',
            "isManual": True, "isError": False,
            "note": "pip install instaloader 后重启服务即可自动获取"
        }

    try:
        print("[Instagram Debug] Creating Instaloader instance...")
        # 使用 instaloader 获取帖子数据
        L = instaloader.Instaloader()
        # 禁用输出干扰
        L.context.log = lambda *args, **kwargs: None
        L.context.error = lambda *args, **kwargs: None

        print(f"[Instagram Debug] Fetching post from shortcode: {shortcode}")
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        print(f"[Instagram Debug] Post fetched. Likes={post.likes}, Comments={post.comments}")

        # 获取发布时间
        date_str = '-'
        if post.date:
            date_str = post.date.strftime('%Y-%m-%d %H:%M')

        # 标题/说明
        title = post.caption[:80] if post.caption else f'Instagram 帖子 {shortcode}'

        return {
            "title": title,
            "likes": post.likes,
            "comments": post.comments,
            "shares": 0,  # Instagram 不公开分享数
            "favorites": 0,
            "views": post.video_view_count if post.is_video else 0,
            "date": date_str,
            "isError": False,
            "source": "instaloader"
        }
    except Exception as e:
        import traceback
        print(f"[Instagram Error] {e}")
        print(traceback.format_exc())
        return {
            "title": f"Instagram 帖子 {shortcode}",
            "likes": 0, "comments": 0, "shares": 0,
            "favorites": 0, "views": 0, "date": '-',
            "isManual": True, "isError": False,
            "note": f"instaloader 错误: {str(e)[:100]}。请手动填入互动数据。"
        }

# ── Threads 解析 ──────────────────────────────────────

def scrape_threads(url):
    post_id = extract_threads_post_id(url)
    if not post_id:
        return None

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "title": f"Threads 帖子 {post_id}",
            "likes": 0, "comments": 0, "shares": 0,
            "favorites": 0, "views": 0, "date": '-',
            "isManual": True, "isError": False,
            "note": "pip install playwright 后重启服务即可自动获取"
        }

    try:
        print(f"[Threads Debug] Starting scrape for {post_id}")
        with sync_playwright() as p:
            print("[Threads Debug] Playwright started")
            browser = p.chromium.launch(headless=True)
            print("[Threads Debug] Browser launched")
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            print(f"[Threads Debug] Navigating to {url}")
            page.goto(url, wait_until="networkidle", timeout=30000)
            print("[Threads Debug] Page loaded")

            try:
                page.wait_for_selector("[data-pressable-container=true]", timeout=10000)
                print("[Threads Debug] Pressable container found")
            except:
                print("[Threads Debug] Pressable container NOT found (timeout)")

            html = page.content()
            print(f"[Threads Debug] HTML length: {len(html)}")
            browser.close()
            print("[Threads Debug] Browser closed")

        # Extract thread data from data-sjs scripts
        scripts = re.findall(r'<script[^>]*data-sjs[^>]*>(.*?)</script>', html, re.DOTALL)
        print(f"[Threads Debug] Found {len(scripts)} data-sjs scripts")
        thread_items = None
        for i, s in enumerate(scripts):
            if '"thread_items"' in s:
                print(f"[Threads Debug] Script {i} contains 'thread_items'")
                try:
                    data = json.loads(s)
                    # Recursively find thread_items
                    def find_threads(obj):
                        if isinstance(obj, dict):
                            for k, v in obj.items():
                                if k == "thread_items":
                                    return v
                                result = find_threads(v)
                                if result is not None:
                                    return result
                        elif isinstance(obj, list):
                            for item in obj:
                                result = find_threads(item)
                                if result is not None:
                                    return result
                        return None
                    thread_items = find_threads(data)
                    if thread_items:
                        print(f"[Threads Debug] Found thread_items with {len(thread_items)} items")
                        break
                except Exception as parse_err:
                    print(f"[Threads Debug] Script {i} JSON parse error: {parse_err}")
                    continue

        if not thread_items:
            print("[Threads Debug] No thread_items found in any script")
            # Save first 500 chars of HTML for debugging
            print(f"[Threads Debug] HTML preview: {html[:500]}")
            return {
                "title": f"Threads 帖子 {post_id}",
                "likes": 0, "comments": 0, "shares": 0,
                "favorites": 0, "views": 0, "date": '-',
                "isManual": True, "isError": False,
                "note": "无法从页面提取帖子数据，帖子可能不存在或需要登录。"
            }

        # Parse first thread item (main post)
        main_item = thread_items[0] if isinstance(thread_items, list) and len(thread_items) > 0 else None
        if not main_item or not isinstance(main_item, dict):
            return {
                "title": f"Threads 帖子 {post_id}",
                "likes": 0, "comments": 0, "shares": 0,
                "favorites": 0, "views": 0, "date": '-',
                "isManual": True, "isError": False,
                "note": "帖子数据结构异常。"
            }

        post = main_item.get("post", {})

        # 检测是否是转发/引用帖，如果是则优先取原帖数据
        app_info = post.get("text_post_app_info", {}) or {}
        share_info = app_info.get("share_info", {}) or {}
        quoted = share_info.get("quoted_post", {}) or {}

        # 如果存在 quoted_post 且有实质内容，用原帖；否则用当前帖
        if quoted and quoted.get("caption"):
            src_post = quoted
            is_repost = True
        else:
            src_post = post
            is_repost = False

        likes = src_post.get("like_count", 0) or 0
        caption = src_post.get("caption", {}) or {}
        title = caption.get("text", "") if isinstance(caption, dict) else ""

        # Reply count
        src_app_info = src_post.get("text_post_app_info", {}) or {}
        comments = src_app_info.get("direct_reply_count", 0) or 0

        # Timestamp
        taken_at = src_post.get("taken_at", 0)
        date_str = "-"
        if taken_at:
            try:
                date_str = datetime.datetime.fromtimestamp(int(taken_at)).strftime("%Y-%m-%d %H:%M")
            except:
                pass

        # Username for title fallback
        user = src_post.get("user", {}) or {}
        username = user.get("username", "") if isinstance(user, dict) else ""

        if not title:
            title = f"Threads by @{username}" if username else f"Threads 帖子 {post_id}"

        # Shares: repost_count + quote_count
        shares = (src_app_info.get("repost_count", 0) or 0) + (src_app_info.get("quote_count", 0) or 0)

        return {
            "title": title[:80] if title else f"Threads 帖子 {post_id}",
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "favorites": 0,
            "views": 0,
            "date": date_str,
            "isError": False,
            "source": "threads-playwright" + ("-repost" if is_repost else "")
        }
    except Exception as e:
        import traceback
        print(f"[Threads Error] {e}")
        print(traceback.format_exc())
        return {
            "title": f"Threads 帖子 {post_id}",
            "likes": 0, "comments": 0, "shares": 0,
            "favorites": 0, "views": 0, "date": '-',
            "isManual": True, "isError": False,
            "note": f"Playwright 抓取错误: {str(e)[:100]}。请检查 playwright 是否已安装。"
        }

# ── 小红书 解析 ───────────────────────────────────────

def scrape_xiaohongshu(url):
    note_id = extract_xiaohongshu_note_id(url)
    # 小红书没有公开 API
    return {
        "title": f"小红书笔记 {note_id or ''}",
        "likes": 0,
        "comments": 0,
        "shares": 0,
        "favorites": 0,
        "views": 0,
        "date": '-',
        "isManual": True,
        "isError": False,
        "note": "小红书暂无公开 API。请手动填入互动数据。"
    }

# ── 路由 ──────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "version": "1.0.0",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "platforms": {
            "bilibili": True,
            "twitter": True,
            "facebook": True,
            "instagram": INSTALOADER_AVAILABLE,
            "threads": True,
            "xiaohongshu": False
        }
    })


@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    queries = data.get('queries', [])
    results = []

    for query in queries:
        platform = query.get('platform', '').strip().lower()
        url = query.get('url', '').strip()
        if not url:
            continue

        result = None
        if platform == 'bilibili':
            result = scrape_bilibili(url)
        elif platform == 'twitter':
            result = scrape_twitter(url)
        elif platform == 'facebook':
            result = scrape_facebook(url)
        elif platform == 'instagram':
            result = scrape_instagram(url)
        elif platform == 'threads':
            result = scrape_threads(url)
        elif platform == 'xiaohongshu':
            result = scrape_xiaohongshu(url)

        if result:
            result['platform'] = platform
            result['url'] = url
            results.append(result)
        else:
            results.append({
                "platform": platform,
                "url": url,
                "title": "解析失败",
                "likes": 0,
                "comments": 0,
                "shares": 0,
                "favorites": 0,
                "views": 0,
                "date": "-",
                "isError": True
            })

        time.sleep(0.3)

    return jsonify(results)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5003))
    print(f">>> Backend started: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
