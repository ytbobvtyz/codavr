# Technical Constraints

## Architecture
- Минимум внешних зависимостей
- Предпочтение стандартной библиотеке Python
- Модульность: каждый компонент можно заменить

## Stack (фиксированный)
- Python 3.10+
- FastAPI
- SQLAlchemy 2.0 (async)
- React + TypeScript

## API Policy
- Только бесплатные API
- OpenRouter с моделями: step-3.5-flash (основная), gpt-3.5-turbo (резерв)
- Никаких платных подписок без явного согласования

## Security
- API ключи только через .env
- Агент не может менять файлы за пределами проекта
- Нет автоматического выполнения destructive операций