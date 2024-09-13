import time
import asyncio
import httpx
import logging

class MircordBotStats:
    def __init__(self, bot, retry_after: int = 120, update_interval: int = 120):
        
        self.logger = logging.getLogger('MircordBotStats')
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - [MIRCORD] - [%(levelname)s] - %(message)s')
        
        if retry_after <= 0:
            self.logger.error("retry_after должно быть положительным числом. Сброшено до 120!")
            retry_after = 120
        if update_interval <= 0:
            self.logger.error("update_interval должно быть положительным числом. Сброшено до 120!")
            update_interval = 120
        
        self.bot = bot
        self.base_url = "https://mircord.xyz/bot-stats"
        self.headers = {'Authorization': bot.mircord_api_key}
        self.retry_after = retry_after
        self.update_interval = update_interval
        self.last_request_time = 0
        self.running = False
        self.update_task = None

    async def activate(self, update_interval: int = None) -> None:
        if update_interval:
            self.update_interval = update_interval
        if not self.running:
            self.running = True
            self.update_task = asyncio.create_task(self.run_update_loop())
            self.logger.info(f"Асинхронная задача для обновления статистики запущена. Интервал обновления: {self.update_interval} секунд. Интервал повторной попытки при ошибке: {self.retry_after} секунд")

    async def stop(self) -> None:
        if self.running:
            self.running = False
            if self.update_task:
                self.update_task.cancel()
                try:
                    await self.update_task
                except asyncio.CancelledError:
                    self.logger.info("Асинхронная задача для обновления статистики остановлена.")

    async def run_update_loop(self) -> None:
        while self.running:
            await self.send_stats()
            await asyncio.sleep(self.update_interval)

    async def send_stats(self) -> None:
        server_count = len(self.bot.guilds)
        shards = self.bot.shard_count

        if self.last_request_time == 0 or (time.time() - self.last_request_time) >= 30:
            bot_stats = {
                'servers': server_count,
                'shards': shards
            }

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(self.base_url, json=bot_stats, headers=self.headers)

                    if response.status_code == 200:
                        self.logger.info("Статистика успешно обновлена.")
                        self.last_request_time = time.time()
                    else:
                        await self.handle_error(response)

            except httpx.RequestError as e:
                self.logger.error(f"Ошибка при отправке запроса: {e}")
            except Exception as e:
                self.logger.error(f"Неизвестная ошибка: {e}")
        else:
            wait_time = 30 - (time.time() - self.last_request_time)
            self.logger.warning(f"Превышен лимит запросов. Подождите {wait_time:.2f} секунд.")

    async def handle_error(self, response: httpx.Response) -> None:
        status_code = response.status_code
        error_messages = {
            429: "Превышен лимит запросов. Повтор через минуту.",
            401: "Неавторизован. Проверьте ваш API-ключ.",
            403: "Доступ запрещен. Проверьте права доступа или ваш API-ключ.",
            404: "Ресурс не найден. Проверьте URL.",
            500: "Ошибка на сервере. Попробуйте позже.",
            502: "Ошибка шлюза. Попробуйте позже.",
            503: "Сервис временно недоступен. Попробуйте позже.",
            504: "Тайм-аут шлюза. Попробуйте позже.",
            302: "Перенаправление: Запрашиваемый ресурс временно перемещен. Проверьте новый URL в заголовках ответа."
        }

        message = error_messages.get(status_code, f"Неожиданный код ошибки: {status_code}. Проверьте библиотеку.")
        self.logger.error(f"Ошибка при отправке запроса: Код - {status_code} | {message}")

        if status_code == 429:
            await asyncio.sleep(self.retry_after)
            await self.send_stats()

    async def update_now(self) -> None:
        await self.send_stats()

    def get_time_since_last_update(self) -> str:
        elapsed_seconds = time.time() - self.last_request_time
        minutes, seconds = divmod(int(elapsed_seconds), 60)
        return f"{minutes} минут {seconds} секунд"

    def is_running(self) -> bool:
        return self.running

    async def update_interval(self, interval: int) -> None:
        self.update_interval = interval

    async def update_retry_after(self, retry_after: int) -> None:
        self.retry_after = retry_after
