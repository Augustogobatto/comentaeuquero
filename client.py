import asyncio, sys
import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

URL = "http://127.0.0.1:8765/mcp"
async def main(tok):
    async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {tok}"}, timeout=30) as http:
        async with Client(streamable_http_client(URL, http_client=http)) as c:
            print("tools:", [(t.name, t.annotations and t.annotations.read_only_hint) for t in (await c.list_tools()).tools])
            r = await c.call_tool("search", {"args": {"query": "x", "limit": 2}})
            print("search:", r.is_error, r.structured_content, [b.text for b in r.content])
            r = await c.call_tool("search", {"args": {"query": "x", "bogus": 1}})
            print("bad args:", r.is_error, r.content[0].text[:150])
            r = await c.call_tool("delete_thing", {"thing_id": 13})
            print("ToolError:", r.is_error, r.content[0].text)
            r = await c.call_tool("boom", {})
            print("crash:", r.is_error, r.content[0].text)
            r = await c.call_tool("who", {})
            print("who:", r.structured_content)
            print("prompt:", (await c.get_prompt("review", {"topic": "T"})).messages[0].content.text)
            print("res:", (await c.read_resource("data://config")).contents[0].text, (await c.read_resource("user://7/profile")).contents[0].text)
            print("proto:", getattr(c, "protocol_version", None))
asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "secret"))
