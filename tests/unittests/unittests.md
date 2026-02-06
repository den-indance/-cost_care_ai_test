📝 Задания для тестов GoogleCalendarService
🧪 Unit Tests (без внешних API)
Test Suite 1: Аутентификация (_authenticate)
Test 1.1: test_authenticate_with_existing_valid_token

Цель: Проверить загрузку существующего валидного токена
Setup: Создать mock token.json с валидными credentials
Действие: Инициализировать GoogleCalendarService
Ожидание:

self.creds не None
self.creds.valid == True
Не вызывается flow.run_local_server()



Test 1.2: test_authenticate_with_expired_token_refresh

Цель: Проверить refresh истёкшего токена
Setup: Mock токен с expired=True и валидным refresh_token
Действие: Инициализировать сервис
Ожидание:

Вызван creds.refresh()
Токен сохранён в файл
self.creds.valid == True



Test 1.3: test_authenticate_missing_credentials_file

Цель: Проверить ошибку при отсутствии credentials.json
Setup: Удалить/не создавать credentials.json
Действие: Инициализировать сервис
Ожидание: FileNotFoundError с сообщением о credentials

Test 1.4: test_headless_auth_flow

Цель: Проверить headless OAuth flow
Setup:

Mock InstalledAppFlow
Mock input() для возврата authorization code


Действие: Вызвать _headless_auth()
Ожидание:

flow.authorization_url() вызван с prompt='consent'
flow.fetch_token() вызван с правильным code
Токен сохранён




Test Suite 2: Проверка доступности (check_availability)
Test 2.1: test_check_availability_all_free

Цель: Проверить генерацию слотов когда весь период свободен
Setup:

Mock API response с пустым busy: []
BookingSlot: 9:00-17:00 (8 часов)


Действие: Вызвать check_availability()
Ожидание:

Возвращено 16 слотов (8 часов × 2 слота/час)
Все слоты по 30 минут
Слоты последовательные без пропусков



Test 2.2: test_check_availability_with_busy_periods

Цель: Проверить фильтрацию занятых периодов
Setup:

Busy: 10:00-11:00, 14:00-15:00
BookingSlot: 9:00-17:00


Действие: Вызвать check_availability()
Ожидание:

НЕТ слотов в 10:00-11:00 и 14:00-15:00
Есть слоты 9:00-10:00, 11:00-14:00, 15:00-17:00



Test 2.3: test_check_availability_completely_busy

Цель: Проверить когда весь период занят
Setup:

Busy: 9:00-17:00 (весь период)


Действие: Вызвать check_availability()
Ожидание: Пустой список []

Test 2.4: test_check_availability_api_error

Цель: Проверить обработку ошибок API
Setup: Mock service.freebusy().query() выбрасывает exception
Действие: Вызвать check_availability()
Ожидание: RuntimeError с сообщением "Failed to check availability"

Test 2.5: test_check_availability_timezone_handling

Цель: Проверить корректную обработку timezone
Setup:

BookingSlot с timezone="Europe/Kyiv"
Даты timezone-aware


Действие: Вызвать check_availability()
Ожидание:

API вызван с правильным timeZone: "Europe/Kyiv"
Даты в ISO формате с timezone




Test Suite 3: Бронирование встречи (book_meeting)
Test 3.1: test_book_meeting_success

Цель: Проверить успешное создание встречи
Setup:

Mock API response с event id, htmlLink, status='confirmed'
BookingData с валидными данными


Действие: Вызвать book_meeting()
Ожидание:

Возвращён dict с id, link, status
API вызван с правильным event body
sendUpdates='all'



Test 3.2: test_book_meeting_event_structure

Цель: Проверить структуру создаваемого event
Setup: Mock API, capture вызванные параметры
Действие: Вызвать book_meeting()
Ожидание: Event содержит:

summary: "Meeting with {name}"
description: "Booked via AI Agent"
start.dateTime в ISO формате
start.timeZone = slot.timezone
attendees[0].email = booking email



Test 3.3: test_book_meeting_datetime_serialization

Цель: Проверить что datetime конвертируются в строки
Setup: BookingData с datetime объектами
Действие: Вызвать book_meeting()
Ожидание:

НЕТ ошибки "datetime is not JSON serializable"
dateTime в event — строки (проверить через mock)



Test 3.4: test_book_meeting_api_error

Цель: Проверить обработку ошибок API
Setup: Mock events().insert() выбрасывает exception
Действие: Вызвать book_meeting()
Ожидание: RuntimeError с сообщением "Failed to book meeting"


Test Suite 4: Генерация слотов (_generate_free_slots)
Test 4.1: test_generate_free_slots_default_duration

Цель: Проверить дефолтную длительность слота (30 мин)
Setup: 1 час свободного времени, пустой busy
Действие: Вызвать _generate_free_slots()
Ожидание: 2 слота по 30 минут

Test 4.2: test_generate_free_slots_custom_duration

Цель: Проверить кастомную длительность
Setup: 2 часа, slot_duration_min=60
Действие: Вызвать _generate_free_slots()
Ожидание: 2 слота по 60 минут

Test 4.3: test_generate_free_slots_partial_overlap

Цель: Проверить частичное пересечение с busy
Setup:

Слот 10:00-10:30
Busy 10:15-10:45


Действие: Генерировать слоты
Ожидание: Слот 10:00-10:30 НЕ включён (частичное пересечение)

Test 4.4: test_generate_free_slots_edge_case_exact_boundary

Цель: Проверить граничный случай (слот заканчивается когда busy начинается)
Setup:

Слот 10:00-10:30
Busy 10:30-11:00


Действие: Генерировать слоты
Ожидание: Слот 10:00-10:30 включён (нет пересечения)