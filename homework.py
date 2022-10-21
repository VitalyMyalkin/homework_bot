import os
import sys
import logging
from logging import StreamHandler
from http import HTTPStatus
import time

import requests
import telegram
from dotenv import load_dotenv

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
    except telegram.error.TelegramError:
        raise telegram.error.TelegramError('Бот не смог отправить сообщение!')


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
            raise requests.HTTPError(f'Неудачный запрос! Код ответа сервиса'
                                     f' Домашек: {response.status_code}')
        return response.json()
    except requests.ConnectionError:
        raise requests.ConnectionError('Cбои при запросе к сервису Домашек!')


def check_response(response):
    """Проверка ответа от сервиса Домашек."""
    if not isinstance(response, dict):
        raise TypeError('Ответ от сервиса домашек не словарь')
    if 'current_date' not in response:
        raise KeyError('Oтсутствие ожидаемых ключей '
                       'в ответе от сервиса Домашек: нет даты')
    if 'homeworks' not in response:
        raise KeyError('Oтсутствие ожидаемых ключей '
                       'в ответе от сервиса Домашек: нет домашек')
    if isinstance(response['homeworks'], list):
        return response['homeworks']
    raise TypeError('Домашки получены, но не списком')


def parse_status(homework):
    """Получение статуса конкретной домашки."""
    if not isinstance(homework, dict):
        raise TypeError('Домашка не словарь')
    if 'homework_name' not in homework:
        raise KeyError('Oтсутствие ожидаемых ключей '
                       'в домашке: нет названия работы')
    if 'status' not in homework:
        raise KeyError('Oтсутствие ожидаемых ключей '
                       'в домашке: нет статуса работы')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise KeyError(f'Недокументированный '
                       f'статус домашней работы: {homework_status}')
    verdict = HOMEWORK_STATUSES[homework_status]
    return (f'Изменился статус проверки работы '
            f'"{homework_name}". {verdict}')


def check_tokens():
    """Проверка наличия переменных окружения."""
    return (bool(PRACTICUM_TOKEN)
            and bool(TELEGRAM_TOKEN)
            and bool(TELEGRAM_CHAT_ID))
    # Оставил предыдущее решение: для all() нужны итерируемые объекты,
    # поэтому bool() проходит тесты, а all() - нет.


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
    last_message = ''
    message = ''
    current_timestamp = 0
    while True:
        try:
            response = get_api_answer(current_timestamp)
            if len(check_response(response)) > 0:
                message = parse_status(check_response(response)[0])
            else:
                logging.debug('Новых статусов домашек нет!')
            current_timestamp = int(response['current_date'])
        except telegram.error.TelegramError:
            logger.error('Бот не смог отправить сообщение!')
        except Exception as error:
            message = str(logger.error(f'{error}'))
        finally:
            if last_message != message:
                send_message(bot, message)
                last_message = message
                # решение не кажется удачным: перезаписывать last_message
                # лучше тогда, когда у нас получилось отправить сообщение.
                # Поэтому раньше мы ее перезаписывали в функции, отправляющей
                # сообщения. Глобальные переменные плохо влияют на память?
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
