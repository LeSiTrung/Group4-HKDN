from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.auth import router as auth_router
from app.api.history import router as history_router
from app.config import Settings
from app.database.connection import Store
from app.security import RequestGate
from app.api.admin import router as admin_router, crawl_job
from app.api.library import router as library_router
from app.api.channels import router as channels_router
from app.services.knowledge import seed, published_rows
from app.services.rag_service import VectorIndex
from app.services.assistant import answer_question
from app.services.llm_service import provider_name
from app.api.catalog import router as catalog_router
from app.services.catalog import seed_books
from app.config import ROOT
import asyncio
import os
from pathlib import Path
from fastapi.staticfiles import StaticFiles

def create_app(data_dir=None, testing=False):
    settings = Settings.load(data_dir, testing)

    @asynccontextmanager
    async def lifespan(app):
        store = Store(settings.data_dir / 'library.sqlite3')
        app.state.store = store
        app.state.db = store.connect
        seed(store.connect, ROOT.parent/'data'/'faq'/'library.json')
        seed_books(store.connect,ROOT.parent/'data'/'faq'/'catalog.json')
        app.state.vectors = VectorIndex(settings)
        app.state.answer = lambda text,history=None: answer_question(app.state,text,history)
        with store.connect() as db:
            db.execute("UPDATE jobs SET status='failed',error='Tiến trình đã dừng trước khi hoàn tất; cần chạy lại tác vụ.' WHERE status IN ('queued','running')")

        async def scheduler():
            interval = float(os.getenv('CRAWL_INTERVAL_HOURS','0'))
            roots = [x.strip() for x in os.getenv('CRAWL_SEEDS','').split(',') if x.strip()]
            if interval<1 or not roots:
                return
            while True:
                await asyncio.sleep(interval*3600)
                for url in roots[:10]:
                    with store.connect() as db:
                        job_id=db.execute('INSERT INTO jobs(url) VALUES (?)',(url,)).lastrowid
                    await asyncio.to_thread(crawl_job,app.state,job_id,url,3)
        task=asyncio.create_task(scheduler()) if not testing else None
        yield
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        app.state.vectors.close()

    app = FastAPI(title='UTH Library Assistant', version='1.0.0', lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(RequestGate, settings=settings)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.origins), allow_credentials=True,
                       allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'], allow_headers=['Content-Type', 'X-Requested-With'])
    app.include_router(auth_router, prefix='/api')
    app.include_router(history_router, prefix='/api')
    app.include_router(chat_router, prefix='/api')
    app.include_router(admin_router, prefix='/api')
    app.include_router(library_router, prefix='/api')
    app.include_router(channels_router, prefix='/api')
    app.include_router(catalog_router,prefix='/api')

    @app.get('/health')
    def health():
        return {'status':'ok','version':'1.0.0','knowledge_count':len(published_rows(app.state.db)),
                'capabilities':{'accounts':True,'history':True,'admin':True,'crawler':True,
                                'vectors':app.state.vectors.status(),'llm_provider':provider_name(),
                                'library_configured':bool(os.getenv('LIBRARY_RENEW_URL')),
                                'messenger_configured':bool(os.getenv('MESSENGER_PAGE_ACCESS_TOKEN')),
                                'zalo_configured':bool(os.getenv('ZALO_ACCESS_TOKEN'))}}

    dist=ROOT.parent/'frontend'/'dist'
    if dist.is_dir():
        app.mount('/',StaticFiles(directory=dist,html=True),name='frontend')

    return app


app = create_app()
