import requests
import os
import sys
import time
import telegram
import logging

from logging import StreamHandler
from dotenv import load_dotenv
from requests.exceptions import HTTPError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)
logger.addHandler(StreamHandler(stream=sys.stdout))


def send_message(bot, message):
    """Отправка статуса домашки и логов в мой чат."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message)
        logger.info(f'Сообщение {message} отправлено!')
    except Exception:
        logger.exception(f'Бот не смог отправить сообщение {message}')


def get_api_answer(current_timestamp):
    """Направляет запрос сервису Домашек."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    if requests.get(ENDPOINT,
                    headers=HEADERS,
                    params=params
                    ).status_code != 200:
        message = str(logger.error('Cервис Домашек недоступен'))
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        send_message(bot, message)
        raise HTTPError('Cервис Домашек недоступен')
    else:
        try:
            response = requests.get(ENDPOINT,
                                    headers=HEADERS,
                                    params=params
                                    ).json()
        except Exception:
            message = str(logger.exception('Cбои при запросе к '
                                           'сервису Домашек'))
            response = {}
            bot = telegram.Bot(token=TELEGRAM_TOKEN)
            send_message(bot, message)
    return response


def check_response(response):
    """Проверка ответа от сервиса Домашек."""
    if isinstance(response["homeworks"], list) and response["current_date"]:
        return response["homeworks"]
    else:
        message = str(logger.error('Отсутствие ожидаемых '
                                   'ключей в ответе сервиса'))
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        send_message(bot, message)


def parse_status(homework):
    """Получение статуса конкретной домашки."""
    homework_name = homework["homework_name"]
    homework_status = homework["status"]
    if homework_status not in HOMEWORK_STATUSES:
        message = str(logger.error(
            f'Недокументированный статус '
            f'домашней работы {homework_name}'
            f': {homework_status}'))
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        send_message(bot, message)
        raise ValueError('Cервис Домашек недоступен')
    else:
        verdict = HOMEWORK_STATUSES[homework_status]
        return (
            f'Изменился статус проверки работы '
            f'"{homework_name}". {verdict}')


def check_tokens():
    """Проверка наличия переменных окружения."""
    return (bool(PRACTICUM_TOKEN)
            and bool(TELEGRAM_TOKEN)
            and bool(TELEGRAM_CHAT_ID))


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 0
    while check_tokens():
        try:
            response = get_api_answer(current_timestamp)
            if len(check_response(response)) > 0:
                message = parse_status(check_response(response)[0])
                send_message(bot, message)
            else:
                logging.debug('Новых статусов домашек нет!')
            current_timestamp = int(response["current_date"])
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)
        else:
            return logger.critical(
                'Отсутствует обязательная переменная окружения. '
                'Программа принудительно остановлена.')


if __name__ == '__main__':
    main()
