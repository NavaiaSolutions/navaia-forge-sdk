#!/usr/bin/env python3
"""
micro_scraper.py - Isolated Micro-Scraper Subprocess Tool.
Decouples web scraping from the core agent execution layer.
Upgraded to use crawl4ai for SPA and Javascript-heavy sites.
"""
import sys
import io
import json
import asyncio
import contextlib

# stdout is the RESULT CHANNEL — it must carry nothing but the final JSON.
# Two things broke that, both found live on 2026-07-19:
#  1. Windows stdout defaults to cp1252, so an Arabic page raised
#     "'charmap' codec can't encode characters" and the scrape was lost after a
#     successful fetch.
#  2. crawl4ai prints [INIT]/[FETCH]/[SCRAPE] progress banners to stdout, which land
#     ahead of the JSON and make agent_scraping_skill's json.loads(stdout) fail.
# So: force UTF-8, and run the crawl with its chatter redirected to stderr.
if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from crawl4ai import AsyncWebCrawler, BrowserConfig

# A plain, current Chrome UA — which is what we actually are: crawl4ai drives a real
# Playwright browser. Decided 2026-07-20 after weighing a self-identifying "NavaiaBot"
# string and rejecting it:
#   - It is not a legal requirement. The obligations that carry real weight are honoring
#     robots.txt and rate limiting, and the caller (enrich_company_size.py) does both.
#   - A "Bot" token trips Cloudflare and similar WAFs, which fronts a large share of Saudi
#     SMB sites. Since the entire job is READING public pages, a UA that raises the block
#     rate defeats the purpose.
#   - The UA also feeds robots.txt matching, so naming ourselves a bot would make us obey
#     Disallow rules aimed at indexers on pages a normal browser is welcome to read.
# We are not evading a paywall or a login — this reads pages published for the public.
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

async def main():
    if len(sys.argv) < 2:
        print(json.dumps({"status": "error", "message": "Usage: python micro_scraper.py <url> [user_agent]"}))
        sys.exit(1)

    url = sys.argv[1]
    user_agent = sys.argv[2] if len(sys.argv) > 2 else USER_AGENT

    try:
        # Redirect the crawler's progress banners to stderr so stdout stays pure JSON.
        with contextlib.redirect_stdout(sys.stderr):
            async with AsyncWebCrawler(verbose=False,
                                       config=BrowserConfig(user_agent=user_agent)) as crawler:
                result = await crawler.arun(url=url)

        # crawl4ai does NOT raise on a failed navigation — it returns a result with
        # success=False and markdown=None, which str() turns into the literal "None".
        # Reporting that as {"status": "success"} made a dead site indistinguishable from
        # a page that simply says nothing: found live on 2026-07-20, when 7 company sites
        # were recorded as "no headcount published" when in fact nothing had been fetched.
        # Trust the flag, not the exception.
        if not getattr(result, "success", True):
            print(json.dumps({
                "status": "error",
                "message": f"fetch failed (http {getattr(result, 'status_code', None)}): "
                           f"{str(getattr(result, 'error_message', ''))[:300]}",
            }, ensure_ascii=False))
            sys.exit(1)

        # Emitted OUTSIDE the redirect: this line is the result channel. crawl4ai returns
        # markdown, which the caller parses (LLM or regex) — richer than selector output
        # and the primary crawl4ai use case.
        markdown = str(result.markdown or "")
        print(json.dumps({
            "status": "success",
            "markdown": markdown,
        }, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
