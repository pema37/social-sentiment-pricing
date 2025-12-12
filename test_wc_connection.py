import asyncio
import httpx

async def test():
    store_url = "http://localhost:8888/woostore"
    key = "ck_be353298ed1099319335c606a3b6e275621ea2e4"
    secret = "cs_c834f8f93e78165afbdb87588e89f2f274e92203"
    
    print(f"Testing connection to: {store_url}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{store_url}/wp-json/wc/v3/system_status",
                auth=(key, secret)
            )
            print(f"Status: {response.status_code}")
            print(f"Success! Response length: {len(response.text)}")
        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}")

asyncio.run(test())
