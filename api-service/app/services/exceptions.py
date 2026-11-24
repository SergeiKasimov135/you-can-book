class ServiceError(Exception):
    # Базовая ошибка сервисного слоя
    pass


class NotFoundError(ServiceError):
    # Объект не найден (HTTP 404)
    pass


class AlreadyExistsError(ServiceError):
    # Нарушена уникальность: email, название категории (HTTP 409)
    pass


class BusinessRuleError(ServiceError):
    # Действие запрещено правилами предметной области (HTTP 409/422)
    pass


class PermissionDeniedError(ServiceError):
    # Недостаточно прав (HTTP 403)
    pass
