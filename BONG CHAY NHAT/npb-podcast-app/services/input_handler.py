"""
Input Handler — Process 4 input sources for story translation.
Sources: paste text, file import (.txt/.md), YouTube subtitle, web crawl.
"""

import os
import re
from dataclasses import dataclass, field


@dataclass
class InputResult:
    """Result from any input source."""
    title: str
    text: str
    source_type: str  # paste / file / youtube / web
    source_url: str = None
    metadata: dict = field(default_factory=dict)


def handle_paste(text: str, title: str = "") -> InputResult:
    """Handle pasted text input."""
    text = text.strip()
    if not text:
        raise ValueError("Nội dung không được để trống")
    if not title:
        # Use first line or first 50 chars as title
        first_line = text.split("\n")[0].strip()
        title = first_line[:50] if first_line else "Untitled"
    return InputResult(title=title, text=text, source_type="paste")


def handle_file(file_path: str) -> InputResult:
    """Handle file import (.txt, .md)."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File không tồn tại: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in (".txt", ".md"):
        raise ValueError(f"Chỉ hỗ trợ file .txt và .md, nhận được: {ext}")

    # Try multiple encodings
    text = None
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "euc-kr", "cp949", "latin-1"):
        try:
            with open(file_path, "r", encoding=encoding) as f:
                text = f.read()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if text is None:
        raise ValueError("Không thể đọc file — encoding không được hỗ trợ")

    text = text.strip()
    if not text:
        raise ValueError("File rỗng")

    title = os.path.splitext(os.path.basename(file_path))[0]
    return InputResult(title=title, text=text, source_type="file")


def handle_youtube(url: str) -> InputResult:
    """Handle YouTube URL — extract subtitle via yt-dlp.
    Requires ytdlp_manager to be available.
    """
    from services.ytdlp_manager import extract_subtitle, get_video_info

    # Validate URL
    if not re.match(r"https?://(www\.)?(youtube\.com|youtu\.be)/", url):
        raise ValueError("URL YouTube không hợp lệ")

    info = get_video_info(url)
    result = extract_subtitle(url)

    title = info.get("title", "YouTube Video") if info else "YouTube Video"
    text = result.get("text", "")
    if not text:
        raise ValueError("Không tìm thấy subtitle cho video này")

    return InputResult(
        title=title,
        text=text,
        source_type="youtube",
        source_url=url,
        metadata={
            "duration": info.get("duration_string", "") if info else "",
            "subtitle_lang": result.get("lang", ""),
        },
    )


def handle_web(url: str) -> InputResult:
    """Handle web URL — crawl and extract main content."""
    import requests
    from bs4 import BeautifulSoup

    if not url.startswith(("http://", "https://")):
        raise ValueError("URL không hợp lệ — phải bắt đầu bằng http:// hoặc https://")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"

    soup = BeautifulSoup(resp.text, "lxml")

    # Remove unwanted elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside",
                     "iframe", "noscript", "form", "button"]):
        tag.decompose()

    # Try to find main content
    content = None

    # Strategy 1: <article> tag
    article = soup.find("article")
    if article:
        content = article

    # Strategy 2: main content div
    if not content:
        for selector in ["main", '[role="main"]', ".content", ".post-content",
                         ".article-content", ".entry-content", "#content"]:
            found = soup.select_one(selector)
            if found:
                content = found
                break

    # Strategy 3: largest div with most <p> tags
    if not content:
        divs = soup.find_all("div")
        best_div = None
        max_p = 0
        for div in divs:
            p_count = len(div.find_all("p"))
            if p_count > max_p:
                max_p = p_count
                best_div = div
        if best_div and max_p >= 3:
            content = best_div

    # Fallback: body
    if not content:
        content = soup.body or soup

    # Extract text
    paragraphs = content.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6"])
    text_parts = []
    for p in paragraphs:
        t = p.get_text(strip=True)
        if t and len(t) > 10:
            text_parts.append(t)

    if not text_parts:
        # Fallback: get all text
        text = content.get_text(separator="\n", strip=True)
    else:
        text = "\n\n".join(text_parts)

    text = text.strip()
    if not text:
        raise ValueError("Không thể trích xuất nội dung từ URL này")

    # Title
    title_tag = soup.find("title")
    h1_tag = soup.find("h1")
    title = ""
    if h1_tag:
        title = h1_tag.get_text(strip=True)
    elif title_tag:
        title = title_tag.get_text(strip=True)
    if not title:
        title = url.split("/")[-1] or "Web Content"

    return InputResult(
        title=title[:100],
        text=text,
        source_type="web",
        source_url=url,
    )
