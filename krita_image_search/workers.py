import asyncio
from krita_image_search.vendor import aiohttp
from PyQt5.QtCore import QObject, QByteArray, pyqtSignal

class SearchAPIWorker(QObject):
    finished = pyqtSignal() 
    onError = pyqtSignal(str)
    
    fullImageLoaded = pyqtSignal(QByteArray)
    baseUrl = "https://joshapiproxy.fly.dev/api/unsplash"

    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        self.count_images_failed = 0

    def errorMsgFormat(self, msg): 
        return f"<h3 style='color:#ce3531;margin:3px'>Search Failed: {msg}</h3>"    

class ImageSearchWorker(SearchAPIWorker):
    imLoaded = pyqtSignal(QByteArray, str, str)
    queried = pyqtSignal(int, int)

    def __init__(self, query, pageNum, perPage, logger):
        super().__init__(logger)
        self.query = query
        self.pageNum = pageNum
        self.perPage = perPage


    async def getSearchJson(self, session):
        params = {
            "query": self.query,
            "page": self.pageNum,
            "per_page": self.perPage
        }
        try:
            async with session.get(f"{self.baseUrl}/search", params=params) as resp:
                if resp.status == 429:
                    self.onError.emit(super().errorMsgFormat("Too many requests, please try again later"))
                elif resp.status == 200:
                    json = await resp.json()
                    self.queried.emit(self.pageNum, json["total_pages"])
                    return json
                elif resp.status >= 500:
                    self.onError.emit(super().errorMsgFormat("Server Error"))
                return None
        except Exception as e:
            self.logger.error(e)
            self.onError.emit(super().errorMsgFormat("Server Error"))    
            return None
        
    async def getImageTask(self, session, url, fullUrl, download_location, params, lock):
        try:
            async with session.get(url, params=params) as resp:
                data = await resp.read()
                await lock.acquire()
                self.imLoaded.emit(data, fullUrl, download_location)
                lock.release()
        except Exception as e:
            await lock.acquire()
            self.logger.error(e)
            self.count_images_failed += 1
            lock.release()
        
    async def imSearch(self):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            r_json = await self.getSearchJson(session)
            if (r_json is not None):
                tasks = []
                thumbnailParams = {
                    "h": 200,
                    "w": 200,
                    "q": 80,
                    "fit": "crop",
                    "crop": "faces,focalpoint"
                }
                lock = asyncio.Lock()
                for im_result in r_json["results"]:
                    imUrl = im_result["urls"]["raw"]
                    fullUrl = im_result["urls"]["full"]
                    download_location = im_result["links"]["download_location"].replace("https://api.unsplash.com", self.baseUrl)
                    tasks.append(asyncio.create_task(self.getImageTask(session, imUrl, fullUrl, download_location, thumbnailParams, lock)))

                await asyncio.gather(*tasks)
                if self.count_images_failed > 0:
                    self.onError.emit(self.errorMsgFormat(f"Cannot load {self.count_images_failed} image(s)"))

            self.finished.emit()
        
    def run(self):
        asyncio.run(self.imSearch())

class ImageDownloadWorker(SearchAPIWorker):
    def __init__(self, url, download_location, logger):
        super().__init__(logger)
        self.url = url
        self.download_location = download_location

    async def downloadLocation(self, session):
        try:
            async with session.get(self.download_location) as resp:
                if resp.status == 200:
                    return True
                else:
                    return False
        except Exception as e:
            self.logger.error(e)
            return False

    async def download(self):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            downloadSuccess = await self.downloadLocation(session)
            if downloadSuccess:
                try:
                    async with session.get(self.url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            self.fullImageLoaded.emit(data)
                        elif resp.status >= 500:
                            self.onError.emit(super().errorMsgFormat("Server Error"))
                except Exception as e:
                    self.logger.error(e)
                    self.onError.emit(super().errorMsgFormat("Server Error"))
            self.finished.emit()   

    def run(self):
        asyncio.run(self.download())