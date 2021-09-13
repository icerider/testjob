# Общее описание модулей

* db/config.py - конфигурация сессии SQLAlchemy
* db/model.py - модели 
* db/dal.py - Data Access Layer для моделей
* endpoints/helpers.py - вспомогательные функция для преобразования DAL -> Scheme
* endpoints/transaction.py - Endpoints для транзакций
* endpoints/user.py - Endpoints для пользователя
* endpoints/router.py - общий маршрутизатор для transaction и user

* tests/test_api.py - тесты для Endpoints
* tests/test_dal.py - тесты для DAL

* config.py - конфигурация приложения (содержит только URL базы по умолчанию)
* deps.py - зависимости используемые для endpoints (база данных, авторизации(не реализована))
* main.py - центральный модуль запуска приложения
* schemas.py - схемы обмена через HTTP

# Модель 

## User

Таблица содержит редкоизменяемые данные пользователя

## Balance

Таблица содержит балас, изменяемый при каждой транзакции

## Transaction

Таблица содержит прямые транзакции и транзакции переводы, отличие по receiver_id

Статус транзакции определяется по таблице TransactionResolve

Наличие Refund по таблице TransactionRefund

## TransactionResolve

Таблица содержит идентификатор тразакции и решение по ней, отсутствие такой записи
в таблице означает, что транзакция новая. Уникальность идентификатора транзакции
позволяет решить проблему одновременного изменения состояния транзакции.

## TransactionRefund

Таблица содержит идентификатор тразакции и идентификатор связанной с ней транзакции Refund

# Подготовка окружения

`./prepare.sh`

# Запуск тестов

`./test.sh`

# Запуск приложения

```
export SQLALCHEMY_DATABASE_URI=sqlite+aiosqlite:///work.db
./run.sh
```

FASTApi Swagger UI: http://localhost:8000/docs
