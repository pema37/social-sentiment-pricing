import os
import sys
import pytest
import pytest_asyncio
import uuid

# ──────────────────────────────────────────────────────────
# 核心黑科技：在导入业务代码前，拦截并净化所有引擎参数
# ──────────────────────────────────────────────────────────
import sqlalchemy
import sqlalchemy.ext.asyncio
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

# 备份原始方法
orig_create_engine = sqlalchemy.create_engine
orig_create_async_engine = sqlalchemy.ext.asyncio.create_async_engine

def filter_sqlite_args(args, kwargs):
    """剔除 SQLite 不支持的连接池参数"""
    if args and isinstance(args[0], str) and "sqlite" in args[0]:
        kwargs.pop("pool_size", None)
        kwargs.pop("max_overflow", None)
        kwargs.pop("pool_pre_ping", None)
    return args, kwargs

# 同时强行替换同步和异步方法，彻底堵死参数报错的源头
sqlalchemy.create_engine = lambda *a, **k: orig_create_engine(*filter_sqlite_args(a, k)[0], **filter_sqlite_args(a, k)[1])
sqlalchemy.ext.asyncio.create_async_engine = lambda *a, **k: orig_create_async_engine(*filter_sqlite_args(a, k)[0], **filter_sqlite_args(a, k)[1])

# 教会 SQLite 认识 Postgres 专有类型
SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: self.visit_JSON(type_, **kw)
SQLiteTypeCompiler.visit_ARRAY = lambda self, type_, **kw: "TEXT"

# ──────────────────────────────────────────────────────────
# 环境与依赖配置
# ──────────────────────────────────────────────────────────
os.environ["GEMINI_API_KEY"] = "fake"
os.environ["OPENAI_API_KEY"] = "fake"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:" 

# 关键：必须在上面的补丁逻辑之后再导入 app
from httpx import AsyncClient, ASGITransport 
from sqlalchemy import select
from main import app
from db.session import get_session
from models import Product, User 
from api.v1.routes.auth import get_current_user
from core.rate_limit import limiter

# 创建内存数据库工厂
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

async def mock_get_session():
    async with test_session_factory() as session:
        yield session

async def mock_get_current_user():
    # 修复 'str' object has no attribute 'hex'：提供真实的 UUID
    test_uuid = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    return User(id=test_uuid, email="test@example.com")

@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """在内存中生成所有表结构"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Product.metadata.create_all) 
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Product.metadata.drop_all)

@pytest_asyncio.fixture
async def client():
    # 彻底关闭干扰项
    limiter.enabled = False 
    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[get_session] = mock_get_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def db_session():
    async with test_session_factory() as session:
        yield session

@pytest.fixture
def normal_user_token_headers():
    return {"Authorization": "Bearer hackathon-token"}

# ──────────────────────────────────────────────────────────
# TEST: 核心逻辑检查
# ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_import_products_success(client, db_session, normal_user_token_headers):
    payload = {
        "products": [
            {"name": "Final Victory A", "base_price": 10.0, "sku": "VIC-001"},
            {"name": "Final Victory B", "base_price": 20.0, "sku": "VIC-002"}
        ]
    }

    # 执行导入
    response = await client.post("/api/v1/products/import", json=payload, headers=normal_user_token_headers)
    
    # 如果还是 500，这里会捕获详情
    if response.status_code != 201:
        print(f"\n❌ FAILED AGAIN: {response.json()}")

    assert response.status_code == 201
    data = response.json()
    assert data["created"] == 2
    
    # 验证数据持久化
    query = select(Product).where(Product.sku.in_(["VIC-001", "VIC-002"]))
    result = await db_session.execute(query)
    assert len(result.scalars().all()) == 2