import os
import sys
import logging
from logging import StreamHandler
from http import HTTPStatus

import time
import requests
import telegram
from dotenv import load_dotenv
from requests import HTTPError

from exceptions import StatusError

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

message = ''
LAST_MESSAGE = ''

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
        global LAST_MESSAGE
        LAST_MESSAGE = message
    except telegram.error.TelegramError:
        raise


def get_api_answer(current_timestamp):
    """Направляет запрос сервису Домашек."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT,
                                headers=HEADERS,
                                params=params
                                )
        if response.status_code != HTTPStatus.OK:
            raise HTTPError
        return response.json()
    except requests.ConnectionError:
        raise


def check_response(response):
    """Проверка ответа от сервиса Домашек."""
    try:
        if isinstance(response['homeworks'], list):
            if response['current_date']:
                return response['homeworks']
            else:
                raise KeyError
        else:
            raise TypeError
    # На случай, если response не словарь
    except TypeError:
        raise
    # На случай, если в response нет нужного ключа
    except KeyError:
        raise


def parse_status(homework):
    """Получение статуса конкретной домашки."""
    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']
        if homework_status not in HOMEWORK_STATUSES:
            raise StatusError
        verdict = HOMEWORK_STATUSES[homework_status]
        return (
                f'Изменился статус проверки работы '
                f'"{homework_name}". {verdict}')
    # На случай, если homework не словарь
    except TypeError:
        raise
    # На случай, если в homework нет нужного ключа
    except KeyError:
        raise


def check_tokens():
    """Проверка наличия переменных окружения."""
    return (bool(PRACTICUM_TOKEN)
            and bool(TELEGRAM_TOKEN)
            and bool(TELEGRAM_CHAT_ID))
    # Оставил предыдущее решение: для all() нужны итерируемые объекты,
    # поэтому bool() проходит тесты, а all() - нет. Либо я неверно
    # понимаю синтаксис all()


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical(
            'Отсутствует обязательная переменная окружения. '
            'Программа принудительно остановлена.')
        raise EnvironmentError(
            'Отсутствует обязательная переменная окружения. '
            'Программа принудительно остановлена.')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 0
    while True:
        try:
            response = get_api_answer(current_timestamp)
            try:
                message = parse_status(check_response(response)[0])
            except IndexError:
                logging.debug('Новых статусов домашек нет!')
            current_timestamp = int(response['current_date'])
        except telegram.error.TelegramError:
            logger.error('Бот не смог отправить сообщение!')
        except HTTPError:
            message = str(logger.error('Cервис Домашек недоступен!'))
        except ConnectionError:
            message = str(logger.error('Cбои при запросе к сервису Домашек!'))
        except TypeError or KeyError:
            message = str(logger.error('Oтсутствие ожидаемых ключей '
                                       'в ответе от сервиса Домашек'))
        except StatusError:
            message = str(logger.error('Недокументированный '
                                       'статус домашней работы'))
        finally:
            if LAST_MESSAGE != message:
                send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
