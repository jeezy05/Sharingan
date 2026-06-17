from sharingan.parse import parse_page
from sharingan.discover import discover_library
from sharingan.fetch import fetch_docs
import asyncio

async def test():
    source = discover_library("zod")
    res = await fetch_docs(source)
    if not res.pages:
        print("No pages fetched")
        return
    page = res.pages[0]
    print(f"Content length: {len(page.content)}")
    parsed = parse_page(page.key, page.content)
    print(f"Word count: {parsed.word_count}")
    print(f"Signatures: {len(parsed.signatures)}")
    print(f"Code blocks: {len(parsed.code_blocks)}")

asyncio.run(test())
